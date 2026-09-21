"""Core immutable records. Every one validates itself at construction.

Nothing untrusted gets past __post_init__: upstream JSON, cosmic signal APIs and
hand-edited JSONL all funnel through here, and all of them fail loudly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any

from .games import BASIC_PICK, WHEEL_SIZE, GameSpec, get_game

DRAW_ID_WIDTH = 5


def normalise_draw_id(raw: str | int) -> str:
    """Canonical draw id: zero-padded digits, e.g. 1386 -> '01386'."""
    text = str(raw).strip()
    if not text.isdigit():
        raise ValueError(f"draw_id must be digits, got {raw!r}")
    return text.zfill(DRAW_ID_WIDTH)


def _check_numbers(numbers: tuple[int, ...], spec: GameSpec, label: str) -> None:
    for n in numbers:
        if not isinstance(n, int) or isinstance(n, bool):
            raise TypeError(f"{label} must contain ints, got {n!r}")
        if n not in spec.numbers:
            raise ValueError(f"{label} value {n} outside 1..{spec.pool} for {spec.key}")
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"{label} contains duplicates: {numbers}")
    if list(numbers) != sorted(numbers):
        raise ValueError(f"{label} must be sorted ascending, got {numbers}")


@dataclass(frozen=True, slots=True)
class Draw:
    """One completed draw. Identity is (game, draw_id)."""

    game: str
    draw_id: str
    date: date
    main: tuple[int, ...]
    bonus: int | None = None
    source: str = "unknown"

    def __post_init__(self) -> None:
        spec = get_game(self.game)
        object.__setattr__(self, "draw_id", normalise_draw_id(self.draw_id))
        object.__setattr__(self, "main", tuple(self.main))

        if len(self.main) != spec.pick:
            raise ValueError(
                f"{spec.key} draw {self.draw_id}: expected {spec.pick} main numbers, "
                f"got {len(self.main)} ({self.main})"
            )
        _check_numbers(self.main, spec, "main")

        if spec.has_bonus:
            if self.bonus is None:
                raise ValueError(f"{spec.key} draw {self.draw_id}: bonus number is required")
            if self.bonus not in spec.bonus_numbers:
                raise ValueError(
                    f"{spec.key} draw {self.draw_id}: bonus {self.bonus} outside "
                    f"1..{spec.bonus_pool or spec.pool}"
                )
            # Only a bonus drawn from the main pool is forbidden from repeating one.
            # Powerball's red ball comes from its own pool, so 7 white + red 7 is legal.
            if spec.bonus_shares_main_pool and self.bonus in self.main:
                raise ValueError(
                    f"{spec.key} draw {self.draw_id}: bonus {self.bonus} duplicates a main number"
                )
        elif self.bonus is not None:
            raise ValueError(f"{spec.key} has no bonus number, got {self.bonus}")

    @property
    def spec(self) -> GameSpec:
        return get_game(self.game)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "draw_id": self.draw_id,
            "date": self.date.isoformat(),
            "main": list(self.main),
            "bonus": self.bonus,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Draw:
        return cls(
            game=payload["game"],
            draw_id=payload["draw_id"],
            date=date.fromisoformat(payload["date"]),
            main=tuple(payload["main"]),
            bonus=payload.get("bonus"),
            source=payload.get("source", "unknown"),
        )


@dataclass(frozen=True, slots=True)
class Prophecy:
    """Twelve numbers committed to a specific unfinished draw, before it happens.

    Twelve is the record; six is a reading of it. `basic_pick` names the six a plain
    ticket would carry, ordered by the oracle's own weight - it is not a second prophecy
    and never draws a number the twelve do not already contain.
    """

    game: str
    draw_id: str
    draw_date: date
    numbers: tuple[int, ...]
    seed: str
    signals: Mapping[str, Any]
    sermon: Mapping[str, str]
    oracle_version: str
    created_at: datetime
    # The same numbers ordered by the oracle's own weight, and how many of them actually
    # earned that place. Optional, because prophecies committed before this existed do not
    # have it and rewriting them is exactly what append-only forbids. A caller that finds
    # it empty must say so rather than invent an order.
    ranked: tuple[int, ...] = ()
    reasoned: int = 0

    def __post_init__(self) -> None:
        spec = get_game(self.game)
        object.__setattr__(self, "draw_id", normalise_draw_id(self.draw_id))
        object.__setattr__(self, "numbers", tuple(self.numbers))
        object.__setattr__(self, "ranked", tuple(self.ranked))
        object.__setattr__(self, "signals", MappingProxyType(dict(self.signals)))
        object.__setattr__(self, "sermon", MappingProxyType(dict(self.sermon)))

        if len(self.numbers) != WHEEL_SIZE:
            raise ValueError(
                f"a prophecy must name exactly {WHEEL_SIZE} numbers, got {len(self.numbers)}"
            )
        _check_numbers(self.numbers, spec, "numbers")
        if not self.seed:
            raise ValueError("prophecy seed must not be empty - it is the audit trail")

        if self.ranked:
            if sorted(self.ranked) != sorted(self.numbers):
                raise ValueError(
                    "ranked must be a permutation of numbers - a ranking that adds or "
                    "drops a number is describing a different prophecy"
                )
            if not 0 <= self.reasoned <= len(self.numbers):
                raise ValueError(
                    f"reasoned must be 0..{len(self.numbers)}, got {self.reasoned}"
                )
        elif self.reasoned:
            raise ValueError("reasoned is meaningless without a ranking")

    @property
    def spec(self) -> GameSpec:
        return get_game(self.game)

    @property
    def key(self) -> tuple[str, str]:
        return (self.game, self.draw_id)

    @property
    def basic_pick(self) -> tuple[int, ...]:
        """Six of the twelve, for the plain ticket most people actually buy.

        Sorted for reading; the order that decided them is `ranked`. Empty when there is
        no ranking, because picking six of twelve at that point would be a coin toss the
        page would then have to pass off as a choice.
        """
        if not self.ranked:
            return ()
        return tuple(sorted(self.ranked[:BASIC_PICK]))

    @property
    def basic_reasoned(self) -> int:
        """How many of `basic_pick` had an actual reason. The rest are the tie."""
        return min(self.reasoned, BASIC_PICK) if self.ranked else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "draw_id": self.draw_id,
            "draw_date": self.draw_date.isoformat(),
            "numbers": list(self.numbers),
            "seed": self.seed,
            "signals": dict(self.signals),
            "sermon": dict(self.sermon),
            "oracle_version": self.oracle_version,
            "created_at": self.created_at.isoformat(),
            "ranked": list(self.ranked),
            "reasoned": self.reasoned,
            "basic_pick": list(self.basic_pick),
            "basic_reasoned": self.basic_reasoned,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Prophecy:
        return cls(
            game=payload["game"],
            draw_id=payload["draw_id"],
            draw_date=date.fromisoformat(payload["draw_date"]),
            numbers=tuple(payload["numbers"]),
            seed=payload["seed"],
            signals=payload.get("signals", {}),
            sermon=payload.get("sermon", {}),
            ranked=tuple(payload.get("ranked", ())),
            reasoned=payload.get("reasoned", 0),
            oracle_version=payload["oracle_version"],
            created_at=datetime.fromisoformat(payload["created_at"]),
        )


def utc_now() -> datetime:
    """Timezone-aware now, second precision - stable enough for an audit trail."""
    return datetime.now(UTC).replace(microsecond=0)


__all__ = ["Draw", "Prophecy", "normalise_draw_id", "replace", "utc_now"]
