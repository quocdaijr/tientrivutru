"""Game specifications for the lotteries this oracle desecrates.

Every number here is verified against official sources, not vibes:
  Power 6/55 - https://vietlott.vn/vi/choi/power-6-55/gioi-thieu-san-pham-power-655
  Mega 6/45  - https://vietlott.vn/vi/choi/mega-6-45/gioi-thieu-san-pham-6-45
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType

WHEEL_SIZE = 12
BASIC_PICK = 6
"""A plain Vietlott ticket - "Cơ bản" in the app - is six numbers for 10,000d.

Bao 12 is a real product: Vietlott sells eleven bao sizes (5, 7, 8, 9, 10, 11, 12, 13, 14,
15, 18), so the wheel arithmetic elsewhere is correct for it. But most people buy the basic
ticket, and handing somebody twelve numbers for a six-number slip is not an answer.
"""
"""How many numbers a prophecy commits to (bao 12)."""

DAYS_IN_WEEK = 7


@dataclass(frozen=True, slots=True)
class GameSpec:
    """Immutable description of one lottery game."""

    key: str
    display: str
    pool: int
    pick: int
    has_bonus: bool
    draw_weekdays: tuple[int, ...]
    unit_price_vnd: int
    prizes: Mapping[str, int]
    jackpot_floor: Mapping[str, int]
    mirror_filename: str
    # Powerball's red ball and Mega Millions' gold ball are drawn from a SEPARATE
    # pool, so they may legitimately repeat a main number. Power 6/55's số phụ comes
    # from the same pool and may not. None means "same pool as the main numbers".
    bonus_pool: int | None = None
    # Bao 12 is a Vietlott product. US games are carried for statistics only - no
    # prophecy, no wheel, no scoreboard - so the honest layer can show that they are
    # every bit as random as Vietlott.
    wheel_playable: bool = True

    @property
    def numbers(self) -> range:
        """The legal main-number range, 1..pool inclusive."""
        return range(1, self.pool + 1)

    @property
    def bonus_numbers(self) -> range:
        """The legal bonus range, which may be a different pool from the main numbers."""
        return range(1, (self.bonus_pool or self.pool) + 1)

    @property
    def bonus_shares_main_pool(self) -> bool:
        return self.has_bonus and self.bonus_pool is None

    @property
    def result_length(self) -> int:
        """How many numbers a raw upstream `result` array must carry."""
        return self.pick + (1 if self.has_bonus else 0)

    def expected_hits(self, wheel_size: int = WHEEL_SIZE) -> float:
        """Hits per draw expected by pure chance - the bar the oracle fails to clear."""
        return self.pick * wheel_size / self.pool


POWER655 = GameSpec(
    key="power655",
    display="Power 6/55",
    pool=55,
    pick=6,
    has_bonus=True,
    draw_weekdays=(1, 3, 5),  # Tue / Thu / Sat
    unit_price_vnd=10_000,
    prizes=MappingProxyType({"first": 40_000_000, "second": 500_000, "third": 50_000}),
    jackpot_floor=MappingProxyType({"jackpot1": 30_000_000_000, "jackpot2": 3_000_000_000}),
    mirror_filename="power655.jsonl",
)

MEGA645 = GameSpec(
    key="mega645",
    display="Mega 6/45",
    pool=45,
    pick=6,
    has_bonus=False,
    draw_weekdays=(2, 4, 6),  # Wed / Fri / Sun
    unit_price_vnd=10_000,
    prizes=MappingProxyType({"first": 10_000_000, "second": 300_000, "third": 30_000}),
    jackpot_floor=MappingProxyType({"jackpot": 12_000_000_000}),
    # Upstream names this file `power645.jsonl` even though it holds Mega 6/45 data.
    # This attribute is the ONLY place that bug is allowed to exist.
    mirror_filename="power645.jsonl",
)

# US games: statistics only. Prize tables are deliberately empty because we never
# price a wheel for them - see `wheel_playable`.
POWERBALL = GameSpec(
    key="powerball",
    display="Powerball (US)",
    pool=69,
    pick=5,
    has_bonus=True,
    draw_weekdays=(0, 2, 5),  # Mon / Wed / Sat
    unit_price_vnd=0,
    prizes=MappingProxyType({}),
    jackpot_floor=MappingProxyType({}),
    mirror_filename="powerball.csv",
    bonus_pool=26,
    wheel_playable=False,
)

MEGAMILLIONS = GameSpec(
    key="megamillions",
    display="Mega Millions (US)",
    pool=70,
    pick=5,
    has_bonus=True,
    draw_weekdays=(1, 4),  # Tue / Fri
    unit_price_vnd=0,
    prizes=MappingProxyType({}),
    jackpot_floor=MappingProxyType({}),
    mirror_filename="megamillions.csv",
    bonus_pool=25,
    wheel_playable=False,
)

GAMES: Mapping[str, GameSpec] = MappingProxyType(
    {
        POWER655.key: POWER655,
        MEGA645.key: MEGA645,
        POWERBALL.key: POWERBALL,
        MEGAMILLIONS.key: MEGAMILLIONS,
    }
)

PROPHECY_GAMES: Mapping[str, GameSpec] = MappingProxyType(
    {key: spec for key, spec in GAMES.items() if spec.wheel_playable}
)


def get_game(key: str) -> GameSpec:
    """Look up a game by key, failing loudly on typos."""
    try:
        return GAMES[key]
    except KeyError:
        known = ", ".join(sorted(GAMES))
        raise KeyError(f"Unknown game {key!r}. Known games: {known}") from None


def is_draw_day(spec: GameSpec, day: date) -> bool:
    """Does `spec` draw on `day`?"""
    return day.weekday() in spec.draw_weekdays


def next_draw_date(spec: GameSpec, after: date, *, inclusive: bool = True) -> date:
    """The first draw day on or after `after` (strictly after, when inclusive=False)."""
    start = 0 if inclusive else 1
    for offset in range(start, start + DAYS_IN_WEEK):
        candidate = after + timedelta(days=offset)
        if is_draw_day(spec, candidate):
            return candidate
    raise AssertionError(f"{spec.key} has no draw weekday within a week - bad spec")


def draw_days_between(spec: GameSpec, start: date, end: date) -> tuple[date, ...]:
    """Every day in [start, end] on which `spec` should have drawn."""
    if end < start:
        return ()
    span = (end - start).days + 1
    days = (start + timedelta(days=offset) for offset in range(span))
    return tuple(day for day in days if is_draw_day(spec, day))
