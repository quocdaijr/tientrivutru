"""Cosmic signals: real numbers, imaginary relevance.

Every network signal degrades to None rather than raising. A dead price API must
never stop the pipeline - and a None signal is honest about the fact that the moon
was not consulted today.

Predictive value of everything in this module: zero. That is not a bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from ..lunar import to_lunar

BTC_URL = "https://api.coingecko.com/api/v3/simple/price"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
HANOI_LAT, HANOI_LON = 21.0285, 105.8542
SIGNAL_TIMEOUT = 10


@dataclass(frozen=True, slots=True)
class CosmicSignals:
    """A snapshot of what the universe was doing. None means 'the universe declined'."""

    btc_usd: int | None = None
    hanoi_temp_c: int | None = None
    lunar_day: int | None = None
    lunar_month: int | None = None
    zodiac: str | None = None
    day_can_chi: str | None = None
    # XSMB's special prize (00..99). Supplied by the caller from stored data rather
    # than fetched here: the XSMB mirror is a 670KB CSV and gather() must stay cheap.
    xsmb_special: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "btc_usd": self.btc_usd,
            "hanoi_temp_c": self.hanoi_temp_c,
            "lunar_day": self.lunar_day,
            "lunar_month": self.lunar_month,
            "zodiac": self.zodiac,
            "day_can_chi": self.day_can_chi,
            "xsmb_special": self.xsmb_special,
        }

    def canonical(self) -> str:
        """Stable string form, fed into the oracle seed. None renders as '-'."""
        items = sorted(self.as_dict().items())
        return "|".join(f"{k}={'-' if v is None else v}" for k, v in items)

    @property
    def silent_count(self) -> int:
        return sum(1 for v in self.as_dict().values() if v is None)


def fetch_btc_usd(*, timeout: int = SIGNAL_TIMEOUT) -> int | None:
    """Bitcoin price in USD, rounded to whole dollars. None if the market is unreachable."""
    try:
        response = requests.get(
            BTC_URL,
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=timeout,
        )
        response.raise_for_status()
        return int(round(float(response.json()["bitcoin"]["usd"])))
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def fetch_hanoi_temp_c(*, timeout: int = SIGNAL_TIMEOUT) -> int | None:
    """Current temperature in Hanoi, whole degrees Celsius. None if unreachable."""
    try:
        response = requests.get(
            WEATHER_URL,
            params={
                "latitude": HANOI_LAT,
                "longitude": HANOI_LON,
                "current": "temperature_2m",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return int(round(float(response.json()["current"]["temperature_2m"])))
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None


def gather(
    when: date, *, allow_network: bool = True, xsmb_special: int | None = None
) -> CosmicSignals:
    """Collect every signal for a given day.

    The lunar signals are computed offline and are therefore always present; the
    market and the weather are best-effort. `xsmb_special` is passed in by the caller
    because reading it means loading a large CSV that the caller already has on disk.
    """
    moon = to_lunar(when)
    return CosmicSignals(
        btc_usd=fetch_btc_usd() if allow_network else None,
        hanoi_temp_c=fetch_hanoi_temp_c() if allow_network else None,
        lunar_day=moon.day,
        lunar_month=moon.month,
        zodiac=moon.zodiac,
        day_can_chi=moon.day_can_chi,
        xsmb_special=xsmb_special,
    )
