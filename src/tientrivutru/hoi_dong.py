"""The Council: TradingAgents' twelve LLM agents, scored in public like every other oracle here.

This module is the pure half of the server side - no network, no LLM, no import of
TradingAgents. It knows what a verdict row is, which assets are due a sitting, and whether the
next sitting can be afforded.

It deliberately does NOT score anything. Scoring needs prices, and every usable price source
either forbids automated collection (Yahoo's ToS §2) or carries no licence that would let a
public repo publish what is derived from it. So the repo records only what is its own - a
rating, the moment it was written, what it cost - and the trader page fetches prices in the
reader's browser and scores there, the same rule the money page already follows. The scoring
rules live in `site/trader.js`, next to the tests that pin them.

A verdict cannot be re-derived from a seed the way a prophecy can, so being written first is
the only thing that makes it honest. The scoring window opens at the first bar AFTER
committed_at, which is why a late write can only move the window, never choose it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

RATINGS: tuple[str, ...] = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
STATUSES: tuple[str, ...] = ("ok", "review", "skipped_budget", "failed")

# The exact code the Council runs. PyPI's `tradingagents` is a different project (a fork by
# another author, MIT, versioned on its own), so this is installed from git and never by name.
UPSTREAM = "TauricResearch/TradingAgents@2d17df8da1536c121e4d7395ac5a5dcec9e96d6f"

# USD per million tokens (input, output), standard non-batch non-cached rates, each read from
# the provider's own pricing page on PRICES_CHECKED (research branch `research/gia-model`).
# Where a price depends on the hour or ends on a date, the HIGHER figure is used, so the cap
# can only ever be conservative: DeepSeek at its peak-hour rate (off-peak is half), Gemini 3.8
# Flash at the rate that starts 2027-01-01. `gpt-5.6-sol` is left out: its price is a promotion
# "at least through November 21, 2026" with nothing said about after. OpenAI doubles above
# 272K input tokens in one call; a council prompt is far below that.
PRICES_CHECKED = date(2026, 9, 23)
PRICES_MAX_AGE = timedelta(days=90)
PRICES: Mapping[str, tuple[float, float]] = {
    # openai - https://developers.openai.com/api/docs/pricing
    "gpt-6-luna": (0.10, 0.50),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-mini": (0.75, 4.50),
    # google - https://ai.google.dev/gemini-api/docs/pricing
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (1.50, 7.50),
    # deepseek - https://api-docs.deepseek.com/quick_start/pricing
    "deepseek-flash": (0.30, 1.20),
    # anthropic - https://platform.claude.com/docs/en/about-claude/pricing
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (2.00, 10.00),
}
# The first sitting of a model has no history to reserve against, so it is allowed only if the
# month still has at least this much left. Set from the trial run's measured cost (ticket 07).
FIRST_RUN_RESERVE_USD = 0.50


class UnknownModelPrice(KeyError):
    """Raised when a model has no looked-up price, so no cap can be enforced against it."""


@dataclass(frozen=True, slots=True)
class Asset:
    key: str                                  # Yahoo-style symbol, the TradingAgents ticker
    kind: Literal["crypto", "vn_stock"]
    tz: str                                   # exchange timezone: what "today" means for it


ASSETS: Mapping[str, Asset] = {
    a.key: a
    for a in (
        Asset("BTC-USD", "crypto", "UTC"),
        Asset("FPT.VN", "vn_stock", "Asia/Ho_Chi_Minh"),
        Asset("VNM.VN", "vn_stock", "Asia/Ho_Chi_Minh"),
        Asset("VCB.VN", "vn_stock", "Asia/Ho_Chi_Minh"),
    )
}


@dataclass(frozen=True, slots=True)
class Verdict:
    """One sitting of the Council for one asset on one day, written before its window opens.

    Everything here is the repo's own: the rating is model output the provider assigns to us,
    the timestamps and costs are ours. No price, no return and no model prose is stored - see
    the module docstring for why.
    """

    asset: str
    trade_date: date
    committed_at: datetime
    status: str
    rating: str | None = None
    model: Mapping[str, str] | None = None
    upstream: str = UPSTREAM
    usage: Mapping[str, float] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown verdict status {self.status!r}")
        if self.status == "ok" and self.rating not in RATINGS:
            raise ValueError(f"an ok verdict needs one of {RATINGS}, got {self.rating!r}")
        if self.status != "ok" and self.rating is not None:
            raise ValueError(f"a {self.status} verdict carries no rating")
        if self.committed_at.tzinfo is None:
            raise ValueError("committed_at must be timezone-aware - it is the audit trail")
        object.__setattr__(self, "committed_at", self.committed_at.astimezone(UTC))

    @property
    def cost_usd(self) -> float:
        return float((self.usage or {}).get("cost_usd", 0.0))

    @property
    def model_id(self) -> str | None:
        return (self.model or {}).get("deep")

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "trade_date": self.trade_date.isoformat(),
            "committed_at": self.committed_at.isoformat(),
            "status": self.status,
            "rating": self.rating,
            "model": dict(self.model) if self.model is not None else None,
            "upstream": self.upstream,
            "usage": dict(self.usage) if self.usage is not None else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Verdict:
        return cls(
            asset=payload["asset"],
            trade_date=date.fromisoformat(payload["trade_date"]),
            committed_at=datetime.fromisoformat(payload["committed_at"]),
            status=payload["status"],
            rating=payload.get("rating"),
            model=payload.get("model"),
            upstream=payload.get("upstream", UPSTREAM),
            usage=payload.get("usage"),
            error=payload.get("error"),
        )


# ---- the budget ---------------------------------------------------------------------------

def prices_are_fresh(today: date, checked: date = PRICES_CHECKED,
                     max_age: timedelta = PRICES_MAX_AGE) -> bool:
    """Providers change prices without asking. A table older than a quarter is re-read before
    the cap is trusted again, rather than enforced against numbers that may have moved."""
    return today - checked <= max_age


def cost_usd(tokens_in: int, tokens_out: int, model_id: str,
             prices: Mapping[str, tuple[float, float]] = PRICES) -> float:
    if model_id not in prices:
        raise UnknownModelPrice(model_id)
    per_in, per_out = prices[model_id]
    return tokens_in / 1e6 * per_in + tokens_out / 1e6 * per_out


def sitting_cost(tokens_in: int, tokens_out: int, deep: str, quick: str,
                 prices: Mapping[str, tuple[float, float]] = PRICES) -> float:
    """Exact when one model plays both roles. Otherwise every token is priced at the dearer of
    the two rates, per direction: tokens are counted per sitting, not per model, so this is an
    upper bound - which is the side a cap has to err on."""
    for model_id in (deep, quick):
        if model_id not in prices:
            raise UnknownModelPrice(model_id)
    per_in = max(prices[deep][0], prices[quick][0])
    per_out = max(prices[deep][1], prices[quick][1])
    return tokens_in / 1e6 * per_in + tokens_out / 1e6 * per_out


def month_spend(verdicts: Iterable[Verdict], month: str) -> float:
    """Everything burned in a UTC calendar month, failed sittings included - the tokens of a run
    that crashed halfway were still bought."""
    return sum(v.cost_usd for v in verdicts if v.committed_at.strftime("%Y-%m") == month)


def reserve_usd(verdicts: Iterable[Verdict], model_id: str,
                first_run: float = FIRST_RUN_RESERVE_USD) -> float:
    """What the next sitting might cost: the worst of this model's last five real sittings."""
    recent = sorted(
        (v for v in verdicts if v.model_id == model_id and v.status != "skipped_budget"),
        key=lambda v: v.committed_at,
    )[-5:]
    return max((v.cost_usd for v in recent), default=first_run)


def can_afford(verdicts: Sequence[Verdict], cap: float, model_id: str, month: str,
               first_run: float = FIRST_RUN_RESERVE_USD) -> bool:
    return month_spend(verdicts, month) + reserve_usd(verdicts, model_id, first_run) <= cap


# ---- what is due -------------------------------------------------------------------------

def local_date(asset: Asset, now: datetime) -> date:
    return now.astimezone(ZoneInfo(asset.tz)).date()


def due_assets(existing: Iterable[Verdict], now: datetime,
               assets: Mapping[str, Asset] = ASSETS) -> tuple[Asset, ...]:
    """Assets the Council should sit on now.

    Crypto every day; a Vietnamese stock Monday to Friday in Vietnam. Holidays are not known
    here - fetching prices in CI to find out is exactly what the data licences forbid - so a
    holiday sitting simply happens, costs its tokens, and is judged on the next real session,
    since the window opens at the first bar after the write. Wasteful a few days a year; wrong
    never.

    Never an (asset, day) that already has a row, whatever that row says: a skipped or failed
    day stays skipped or failed, it is not retried into a better-looking record.
    """
    taken = {(v.asset, v.trade_date) for v in existing}
    due = []
    for asset in assets.values():
        today = local_date(asset, now)
        if (asset.key, today) in taken:
            continue
        if asset.kind == "vn_stock" and today.weekday() >= 5:
            continue
        due.append(asset)
    return tuple(due)


# ---- what the page receives ----------------------------------------------------------------

def _billing(verdicts: Sequence[Verdict]) -> str | None:
    """How the newest sitting was paid for: 'free', 'paid', or None before the first one."""
    if not verdicts:
        return None
    latest = max(verdicts, key=lambda v: v.committed_at)
    return (latest.usage or {}).get("billing", "paid")


def council_payload(verdicts: Sequence[Verdict], now: datetime) -> dict[str, Any]:
    """The Council's part of site/data.json: every rating with its write time, and the month's
    spend against the cap in force. The trader page scores these itself, with prices it fetches
    in the reader's browser - nothing priced leaves this repo.

    The cap is read from the rows rather than the environment, because two workflows rebuild
    the bundle and only one of them holds the secret.
    """
    month = now.astimezone(UTC).strftime("%Y-%m")
    this_month = [v for v in verdicts if v.committed_at.strftime("%Y-%m") == month]
    caps = [v.usage["cap_usd"] for v in sorted(this_month, key=lambda v: v.committed_at)
            if v.usage and "cap_usd" in v.usage]
    return {
        "upstream": UPSTREAM,
        "month": month,
        "spent_usd": round(month_spend(verdicts, month), 4),
        "cap_usd": caps[-1] if caps else None,
        "stopped": any(v.status == "skipped_budget" for v in this_month),
        "billing": _billing(verdicts),
        "provider": ((max(verdicts, key=lambda v: v.committed_at).model or {}).get("provider")
                     if verdicts else None),
        "verdicts": [
            {"asset": v.asset, "trade_date": v.trade_date.isoformat(),
             "committed_at": v.committed_at.isoformat(), "status": v.status, "rating": v.rating,
             "memory": bool((v.usage or {}).get("memory"))}
            for v in sorted(verdicts, key=lambda v: (v.asset, v.trade_date))
        ],
    }
