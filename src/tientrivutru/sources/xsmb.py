"""Xổ số kiến thiết Miền Bắc (XSMB), from khiemdoan/vietnam-lottery-xsmb-analysis.

Source: https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis (MIT, 147 stars,
refreshed by a GitHub Action after each draw). Verified live on 2026-08-19:
`data/xsmb-2-digits.csv` holds 7526 draws from 2005-10-01 to 2026-08-18.

XSMB deliberately does NOT reuse the Draw model, because it violates every invariant
Draw enforces:

  * 27 prize slots per day, not a pick-6
  * the value space is 00..99, so ZERO is a legal value (Draw requires 1..pool)
  * repeats within a single day are normal (2026-08-17 drew 14 twice and 00 twice)

Forcing it into Draw would mean loosening validation for every other game, so it gets
its own small record instead. XSMB therefore never produces a prophecy - it feeds the
honest layer, and it feeds the oracle as a cosmic signal.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

import requests

from .. import stats

MIRROR_URL = (
    "https://raw.githubusercontent.com/khiemdoan/"
    "vietnam-lottery-xsmb-analysis/main/data/xsmb-2-digits.csv"
)
SOURCE_LABEL = "mirror:khiemdoan/vietnam-lottery-xsmb-analysis"
DEFAULT_TIMEOUT = 60

DIGIT_SPACE = 100
"""XSMB two-digit values run 00..99 inclusive - one hundred outcomes, including zero."""

PRIZE_SLOTS = 27
"""Prize columns per draw: special + 1st + 2x2nd + 6x3rd + 4x4th + 6x5th + 3x6th + 4x7th."""

DATE_COLUMN = "date"
SPECIAL_COLUMN = "special"


@dataclass(frozen=True, slots=True)
class XsmbDraw:
    """One day of XSMB results, as last-two-digit values."""

    date: date
    special: int
    prizes: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "prizes", tuple(self.prizes))
        if len(self.prizes) != PRIZE_SLOTS:
            raise ValueError(
                f"XSMB {self.date}: expected {PRIZE_SLOTS} prize slots, got {len(self.prizes)}"
            )
        for value in self.prizes:
            if not 0 <= value < DIGIT_SPACE:
                raise ValueError(f"XSMB {self.date}: value {value} outside 00..99")
        if self.special != self.prizes[0]:
            raise ValueError(
                f"XSMB {self.date}: special {self.special} must be the first prize slot"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.date.isoformat(),
            "special": self.special,
            "prizes": list(self.prizes),
            "source": SOURCE_LABEL,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> XsmbDraw:
        return cls(
            date=date.fromisoformat(str(payload["date"])),
            special=int(payload["special"]),  # type: ignore[arg-type]
            prizes=tuple(int(v) for v in payload["prizes"]),  # type: ignore[union-attr]
        )


def parse_row(row: Mapping[str, str]) -> XsmbDraw:
    """Turn one CSV row into a validated XsmbDraw."""
    if DATE_COLUMN not in row:
        raise ValueError(f"XSMB row missing {DATE_COLUMN!r}: {row}")
    values = [v for k, v in row.items() if k != DATE_COLUMN and v not in (None, "")]
    if len(values) != PRIZE_SLOTS:
        raise ValueError(
            f"XSMB {row[DATE_COLUMN]}: expected {PRIZE_SLOTS} prize values, got {len(values)}"
        )
    prizes = tuple(int(v) for v in values)
    return XsmbDraw(
        date=date.fromisoformat(row[DATE_COLUMN].strip()),
        special=prizes[0],
        prizes=prizes,
    )


def parse_csv(text: str) -> tuple[XsmbDraw, ...]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("XSMB mirror CSV is empty")
    draws = [parse_row(row) for row in rows]
    return tuple(sorted(draws, key=lambda d: d.date))


def fetch_text(*, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(MIRROR_URL, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_draws(*, timeout: int = DEFAULT_TIMEOUT) -> tuple[XsmbDraw, ...]:
    return parse_csv(fetch_text(timeout=timeout))


def frequency(draws: Sequence[XsmbDraw]) -> Mapping[int, int]:
    """How often each 00..99 value appeared across every prize slot."""
    counts = dict.fromkeys(range(DIGIT_SPACE), 0)
    for draw in draws:
        for value in draw.prizes:
            counts[value] += 1
    return MappingProxyType(counts)


def chi_square_uniform(draws: Sequence[XsmbDraw]) -> stats.ChiSquareResult:
    """Test H0: all 100 two-digit values are equally likely.

    Reuses the incomplete-gamma implementation in `stats` rather than duplicating it.
    """
    if not draws:
        raise ValueError("cannot test uniformity with no draws")
    counts = frequency(draws)
    observations = sum(counts.values())
    expected = observations / DIGIT_SPACE
    statistic = sum((count - expected) ** 2 / expected for count in counts.values())
    df = DIGIT_SPACE - 1
    return stats.ChiSquareResult(
        statistic=statistic,
        degrees_of_freedom=df,
        p_value=stats.chi_square_sf(statistic, df),
        observations=observations,
    )


def latest_special(draws: Sequence[XsmbDraw]) -> int | None:
    """The most recent special-prize value, used as a cosmic signal. None if no data."""
    if not draws:
        return None
    return max(draws, key=lambda d: d.date).special


def summarise(draws: Sequence[XsmbDraw]) -> dict[str, object]:
    return {
        "count": len(draws),
        "first_date": min(d.date for d in draws).isoformat() if draws else None,
        "last_date": max(d.date for d in draws).isoformat() if draws else None,
        "observations": len(draws) * PRIZE_SLOTS,
    }
