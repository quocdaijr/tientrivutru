"""Gold and crypto prices. Real money, still zero predictive value.

Same contract as `vibes`: every fetch degrades to None (or an empty tuple) rather than
raising, because a price board is commentary and must never be able to take a pulse down.

**The unit is the whole problem with Vietnamese gold.** PNJ publishes thousands of dong
per *chỉ*; people talk in dong per *lượng*; and a lượng is ten chỉ. That puts a wrong
answer exactly one factor of ten from a right one, and 15 million a lượng looks no less
plausible than 150 million to anyone not holding the bar. So the conversion lives here,
once, with the factor named - and the tests pin it from both ends: against the figure
webgia.com publishes in plain dong, and against world spot converted independently.

The world price is fetched for one reason: to show the domestic premium. That is the
honest number in this module - how much more a lượng costs in Vietnam than the metal is
worth anywhere else - and it is the only thing here that says anything at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import requests

PNJ_URL = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price"
WORLD_GOLD_URL = "https://api.gold-api.com/price/XAU"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
FETCH_TIMEOUT = 10

CHI_PER_LUONG = 10
"""One lượng (tael) is ten chỉ. This is the factor everything else here hangs on."""
PNJ_UNIT_VND = 1_000
"""PNJ quotes in thousands of dong per chỉ: `giaban: 15060` is 15,060,000 đ/chỉ."""
GRAMS_PER_LUONG = 37.5
GRAMS_PER_TROY_OUNCE = 31.1034768

COINS = (
    ("bitcoin", "BTC", "Bitcoin"),
    ("ethereum", "ETH", "Ethereum"),
    ("solana", "SOL", "Solana"),
)
GOLD_SYMBOL = "XAU"


@dataclass(frozen=True, slots=True)
class GoldQuote:
    """One product on a dealer's board, stored in dong per chỉ - the published unit."""

    code: str
    label: str
    buy_vnd_per_chi: int
    sell_vnd_per_chi: int

    @property
    def buy_vnd_per_luong(self) -> int:
        return self.buy_vnd_per_chi * CHI_PER_LUONG

    @property
    def sell_vnd_per_luong(self) -> int:
        return self.sell_vnd_per_chi * CHI_PER_LUONG

    @property
    def spread_vnd_per_luong(self) -> int:
        """What a buyer loses the instant they buy: the dealer sells high and buys back low."""
        return self.sell_vnd_per_luong - self.buy_vnd_per_luong

    @property
    def spread_pct(self) -> float:
        return self.spread_vnd_per_luong / self.sell_vnd_per_luong * 100


@dataclass(frozen=True, slots=True)
class GoldBoard:
    """A dealer's board as read at one moment."""

    quotes: tuple[GoldQuote, ...]
    branch: str | None = None
    updated_at: str | None = None

    def by_code(self, code: str) -> GoldQuote | None:
        return next((q for q in self.quotes if q.code == code), None)


@dataclass(frozen=True, slots=True)
class CoinQuote:
    symbol: str
    name: str
    usd: float
    vnd: float
    change_24h_pct: float | None = None


def _positive_number(value: Any) -> float | None:
    """A price, or None. Rejects bools, strings and anything <= 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def _gold_quote(row: Any) -> GoldQuote | None:
    """One board row, or None if it is not usable. Never raises on shape."""
    if not isinstance(row, Mapping):
        return None
    sell = _positive_number(row.get("giaban"))
    buy = _positive_number(row.get("giamua"))
    code = row.get("masp")
    if sell is None or buy is None or not isinstance(code, str):
        return None
    return GoldQuote(
        code=code,
        label=str(row.get("tensp") or code),
        buy_vnd_per_chi=int(buy * PNJ_UNIT_VND),
        sell_vnd_per_chi=int(sell * PNJ_UNIT_VND),
    )


def fetch_gold_board(*, timeout: int = FETCH_TIMEOUT) -> GoldBoard | None:
    """The PNJ board, or None if it is unreachable or unparseable.

    A 403 lands here as None, which is not hypothetical: vietlott.vn answers a laptop
    with 200 and a GitHub runner with 403, and this module has no reason to assume its
    own upstream is treated any better.
    """
    try:
        response = requests.get(PNJ_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(payload, Mapping):
        return None
    rows = payload.get("data")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None

    quotes = tuple(q for q in (_gold_quote(row) for row in rows) if q is not None)
    if not quotes:
        return None
    branch = payload.get("chinhanh")
    updated = payload.get("updateDate")
    return GoldBoard(
        quotes=quotes,
        branch=branch if isinstance(branch, str) else None,
        updated_at=updated if isinstance(updated, str) else None,
    )


def fetch_world_gold_usd_per_oz(*, timeout: int = FETCH_TIMEOUT) -> float | None:
    """Spot gold in USD per troy ounce, or None.

    Checks the symbol it got back. The same host serves silver at a fiftieth of the
    price, and a silver figure printed as gold would be a plausible wrong number - which
    is worse than no number at all.
    """
    try:
        response = requests.get(WORLD_GOLD_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(payload, Mapping) or payload.get("symbol") != GOLD_SYMBOL:
        return None
    return _positive_number(payload.get("price"))


def world_gold_vnd_per_luong(usd_per_oz: float, *, usd_vnd: float) -> float:
    """Spot gold priced the way Vietnam quotes it. Pure arithmetic, no network."""
    return usd_per_oz / GRAMS_PER_TROY_OUNCE * GRAMS_PER_LUONG * usd_vnd


def fetch_coins(*, timeout: int = FETCH_TIMEOUT) -> tuple[CoinQuote, ...]:
    """The tracked coins in USD and VND, or an empty tuple.

    Both currencies come from one request so the implied exchange rate below describes a
    single moment rather than two rates read at two times.
    """
    try:
        response = requests.get(
            COINGECKO_URL,
            params={
                "ids": ",".join(key for key, _, _ in COINS),
                "vs_currencies": "usd,vnd",
                "include_24hr_change": "true",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return ()

    if not isinstance(payload, Mapping):
        return ()

    quotes = []
    for key, symbol, name in COINS:
        row = payload.get(key)
        if not isinstance(row, Mapping):
            continue
        usd = _positive_number(row.get("usd"))
        vnd = _positive_number(row.get("vnd"))
        if usd is None or vnd is None:
            continue
        change = row.get("usd_24h_change")
        quotes.append(
            CoinQuote(
                symbol=symbol,
                name=name,
                usd=usd,
                vnd=vnd,
                change_24h_pct=(
                    float(change)
                    if isinstance(change, (int, float)) and not isinstance(change, bool)
                    else None
                ),
            )
        )
    return tuple(quotes)


def implied_usd_vnd(coins: Sequence[CoinQuote]) -> float | None:
    """USD/VND as the price source itself implies it, from any coin quoted in both.

    Not a bank rate and never labelled as one. It is the rate that makes the premium
    arithmetic internally consistent, which is the only claim being made.
    """
    for coin in coins:
        if coin.usd > 0 and coin.vnd > 0:
            return coin.vnd / coin.usd
    return None
