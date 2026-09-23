"""One sitting of the Council: build the TradingAgents graph, let it argue, write down the result.

This is the only module that touches TradingAgents, and it does so lazily, inside functions.
TradingAgents is not a dependency of this package - it is installed at the pinned commit only
inside the workflow step that runs the Council (`uv run --with ...`) - so the package, the CLI
and the test suite must all import this file without it. The graph and the token counter are
therefore arguments, and the tests pass stand-ins.

Only the rating leaves a sitting. The debate itself routinely quotes Yahoo news, StockTwits,
Reddit and FRED, none of which licenses republication, so the final state is read for its
signal and then dropped with the temporary directory.
"""

from __future__ import annotations

import math
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .hoi_dong import (
    PRICES,
    PRICES_CHECKED,
    RATINGS,
    UPSTREAM,
    Asset,
    Verdict,
    prices_are_fresh,
    sitting_cost,
)
from .models import utc_now

# Long enough to keep a provider's instruction - the first trial run lost Google's behind a
# 200-character cut - and still bounded, because the row is committed to a public repo.
ERROR_CHARS = 500
# Anything an SDK might echo back that looks like a credential. The error text is committed to
# a public repo, so it is scrubbed before it is written rather than trusted not to contain one.
_SECRETISH = re.compile(r"\b(?:sk|key|token|bearer)[-_A-Za-z0-9]{12,}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Model:
    provider: str
    deep: str
    quick: str

    def as_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "deep": self.deep, "quick": self.quick}


ENV_PROVIDER = "TRADINGAGENTS_LLM_PROVIDER"
ENV_DEEP = "TRADINGAGENTS_DEEP_THINK_LLM"
ENV_QUICK = "TRADINGAGENTS_QUICK_THINK_LLM"
ENV_CAP = "HOI_DONG_MONTHLY_CAP_USD"
ENV_BILLING = "HOI_DONG_BILLING"
BILLING_MODES = ("paid", "free")


def council_settings(env: Mapping[str, str], today: date,
                     prices: Mapping[str, tuple[float, float]] = PRICES
                     ) -> tuple[Model | None, float | None, list[str]]:
    """Everything a real sitting needs, or every reason it cannot happen.

    There is no default model and, on a paid key, no default cap. A sitting spends real money,
    and one run on a guessed model against a guessed ceiling is the single thing this command
    must never do - so every missing or suspicious setting is reported, all at once, and nothing
    runs. The model variables are TradingAgents' own, so the same env configures both sides.

    HOI_DONG_BILLING=free is for a key on a project with no billing account - Google's Gemini
    free tier. There is nothing to charge, so there is no money cap to enforce: going past the
    provider's limit is a rate-limit error, and that limit is the cap. The returned cap is then
    None, and no price lookup is needed because nothing will be priced.
    """
    problems: list[str] = []
    billing = (env.get(ENV_BILLING) or "paid").strip().lower()
    if billing not in BILLING_MODES:
        problems.append(f"{ENV_BILLING} must be one of {BILLING_MODES}, got {billing!r}")
        billing = "paid"
    provider = (env.get(ENV_PROVIDER) or "").strip()
    deep = (env.get(ENV_DEEP) or "").strip()
    quick = (env.get(ENV_QUICK) or "").strip() or deep
    if not provider:
        problems.append(f"{ENV_PROVIDER} is not set")
    if not deep:
        problems.append(f"{ENV_DEEP} is not set")
    if billing == "free":
        if problems:
            return None, None, problems
        return Model(provider, deep, quick), None, []

    for model_id in {deep, quick} - {""}:
        if model_id not in prices:
            problems.append(f"no looked-up price for model {model_id!r} in hoi_dong.PRICES")
    if not prices_are_fresh(today):
        problems.append(f"PRICES were read on {PRICES_CHECKED}; re-read them before trusting a cap")

    cap: float | None = None
    raw = env.get(ENV_CAP)
    if raw is None or not raw.strip():
        problems.append(f"{ENV_CAP} is not set")
    else:
        try:
            cap = float(raw)
        except ValueError:
            cap = None
        if cap is None or not math.isfinite(cap) or cap <= 0:
            problems.append(f"{ENV_CAP} must be a positive number of dollars, got {raw!r}")
            cap = None

    if problems:
        return None, None, problems
    return Model(provider, deep, quick), cap, []


def council_config(base: Mapping[str, Any], model: Model, workdir: Path) -> dict[str, Any]:
    """TradingAgents' config for one sitting.

    Memory, logs and cache all go under a throwaway directory: the Council does not remember
    past verdicts (ticket 09 may change that), and nothing it writes may land where a commit
    could pick it up. `temperature` is deliberately not touched - a non-default value is an HTTP
    400 on Claude Sonnet 5 and Opus 5 and makes Gemini 3 prone to looping (research 03).
    """
    cfg = dict(base)
    cfg.update(
        llm_provider=model.provider,
        deep_think_llm=model.deep,
        quick_think_llm=model.quick,
        memory_log_path=str(workdir / "memory" / "trading_memory.md"),
        results_dir=str(workdir / "logs"),
        data_cache_dir=str(workdir / "cache"),
        checkpoint_enabled=False,
    )
    return cfg


def _default_base_config() -> dict[str, Any]:
    from tradingagents.default_config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.copy()


def _default_graph(config: dict[str, Any], callbacks: list) -> Any:
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph(debug=False, config=config, callbacks=callbacks)


def _token_counter() -> Any:
    """A langchain callback handler, built inside a function so langchain_core is imported only
    when a real sitting happens. Counts the same things as upstream's cli StatsCallbackHandler."""
    import threading

    from langchain_core.callbacks import BaseCallbackHandler

    class TokenCounter(BaseCallbackHandler):
        def __init__(self) -> None:
            super().__init__()
            self._lock = threading.Lock()
            self._stats = {"llm_calls": 0, "tokens_in": 0, "tokens_out": 0}

        def on_chat_model_start(self, *args: Any, **kwargs: Any) -> None:
            with self._lock:
                self._stats["llm_calls"] += 1

        def on_llm_start(self, *args: Any, **kwargs: Any) -> None:
            with self._lock:
                self._stats["llm_calls"] += 1

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            try:
                message = response.generations[0][0].message
            except (AttributeError, IndexError, TypeError):
                return
            usage = getattr(message, "usage_metadata", None) or {}
            with self._lock:
                self._stats["tokens_in"] += usage.get("input_tokens", 0)
                self._stats["tokens_out"] += usage.get("output_tokens", 0)

        def stats(self) -> dict[str, int]:
            with self._lock:
                return dict(self._stats)

    return TokenCounter()


def _error_text(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = _SECRETISH.sub("[redacted]", text)
    return text if len(text) <= ERROR_CHARS else text[: ERROR_CHARS - 1] + "…"


def _usage(stats: Mapping[str, int], model: Model,
           prices: Mapping[str, tuple[float, float]] | None) -> dict[str, Any]:
    """prices=None is the free tier: nothing is billed, so the cost is 0 - but the tokens are
    kept, because they are what would be billed if the project ever turned billing on."""
    usage: dict[str, Any] = {
        "llm_calls": stats["llm_calls"],
        "tokens_in": stats["tokens_in"],
        "tokens_out": stats["tokens_out"],
    }
    if prices is None:
        return {**usage, "cost_usd": 0.0, "billing": "free"}
    return {**usage, "billing": "paid",
            "cost_usd": sitting_cost(stats["tokens_in"], stats["tokens_out"], model.deep,
                                     model.quick, prices=prices)}


def run_verdict(
    asset: Asset,
    trade_date: date,
    *,
    model: Model,
    graph_factory: Callable[[dict, list], Any] | None = None,
    counter_factory: Callable[[], Any] | None = None,
    base_config: Callable[[], Mapping[str, Any]] | None = None,
    prices: Mapping[str, tuple[float, float]] | None = PRICES,
    now: Callable[[], datetime] = utc_now,
) -> Verdict:
    """One sitting. Always returns a Verdict - a crash is a 'failed' row that still carries the
    tokens it burned, because they were bought whether or not an answer came back.

    committed_at is read once, after the sitting: it is when the rating became known, and the
    scoring window opens at the first bar after it.
    """
    graph_factory = graph_factory or _default_graph
    counter = (counter_factory or _token_counter)()
    asset_type = "crypto" if asset.kind == "crypto" else "stock"
    common = {"asset": asset.key, "trade_date": trade_date, "model": model.as_dict(),
              "upstream": UPSTREAM}

    with tempfile.TemporaryDirectory(prefix="hoi-dong-") as tmp:
        config = council_config((base_config or _default_base_config)(), model, Path(tmp))
        try:
            graph = graph_factory(config, [counter])
            _state, signal = graph.propagate(asset.key, trade_date.isoformat(),
                                             asset_type=asset_type)
        except Exception as exc:  # noqa: BLE001 - every failure must become a row, not a crash
            return Verdict(committed_at=now(), status="failed",
                           usage=_usage(counter.stats(), model, prices),
                           error=_error_text(exc), **common)

    readable = signal in RATINGS
    return Verdict(
        committed_at=now(),
        status="ok" if readable else "review",
        rating=signal if readable else None,
        usage=_usage(counter.stats(), model, prices),
        **common,
    )
