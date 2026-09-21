"""Thầy phán vé số: one six-digit ticket per đài per kỳ, and nothing more.

One ticket, not twelve. A person walking past a vé số seller buys one, so that is what
gets committed and scored - 10,000đ in, whatever the board says out. The arithmetic on
that bet is exact and published in `kienthiet_prizes`: ROI −50%, forever.

Determinism is the constraint, as it is in `oracle`. Same đài, same day, same signals in,
byte-identical ticket out. The ticket is written to data/ve.jsonl before the đài draws
and never afterwards, which is the only reason the Bảng Phong Thần means anything.

This module keeps its OWN version string and never touches `CosmicSignals`. Folding a new
signal into the shared oracle would change every future mega645 and power655 prophecy for
the sake of a feature that has nothing to do with them; tests/test_kienthiet_oracle.py
pins that this did not happen.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from .kienthiet_prizes import TICKET_DIGITS
from .models import utc_now
from .oracle import GENERIC_SERMONS, digit_root
from .sources.kienthiet import PROVINCES, REGIONS, Board, get_province
from .sources.vibes import CosmicSignals

KIENTHIET_ORACLE_VERSION = "1.0.0"
"""Part of every seed. Changing a weight or a signal here changes future tickets only -
tickets already committed keep the version that produced them.
"""

DIGITS = tuple(range(10))
SEED_BITS = 16

BOOST_NUMEROLOGY = 1.6
BOOST_BTC = 1.9
BOOST_TEMPERATURE = 1.7
BOOST_LUNAR = 1.5
BOOST_ZODIAC = 1.4
PENALTY_KARMA = 0.5

KIENTHIET_SERMONS = (
    "Vé này thầy nhìn là thấy có căn. Con ra đại lý hỏi đi.",
    "Một vé thôi. Tham là mất lộc.",
    "Con cầm tờ này, đừng gấp làm tư.",
    "Đài này thầy theo lâu rồi, nó có nết.",
    "Thầy phán một vé, không phán hai. Hai là tham.",
    "Số này về hay không thì thầy vẫn ngồi đây.",
)


@dataclass(frozen=True, slots=True)
class CursedDigits:
    """Per-position weights over 0..9, plus the excuses that produced them."""

    weights: tuple[Mapping[int, float], ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VeProphecy:
    """One committed ticket for one đài on one day."""

    province: str
    region: str
    draw_date: date
    ve: str
    seed: str
    signals: Mapping[str, Any]
    sermon: str
    reasons: tuple[str, ...]
    karma: str | None
    oracle_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if len(self.ve) != TICKET_DIGITS or not self.ve.isdigit():
            raise ValueError(f"a vé is {TICKET_DIGITS} digits, got {self.ve!r}")
        if PROVINCES[self.province].region != self.region:
            raise ValueError(f"{self.province} is not in {self.region}")
        if not REGIONS[self.region].prophesiable:
            raise ValueError(f"{REGIONS[self.region].display} không phán vé được")

    @property
    def key(self) -> tuple[date, str]:
        return (self.draw_date, self.province)

    @property
    def display(self) -> str:
        return PROVINCES[self.province].display

    def to_dict(self) -> dict[str, Any]:
        return {
            "province": self.province,
            "region": self.region,
            "draw_date": self.draw_date.isoformat(),
            "ve": self.ve,
            "seed": self.seed,
            "signals": dict(self.signals),
            "sermon": self.sermon,
            "reasons": list(self.reasons),
            "karma": self.karma,
            "oracle_version": self.oracle_version,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> VeProphecy:
        return cls(
            province=str(payload["province"]),
            region=str(payload["region"]),
            draw_date=date.fromisoformat(str(payload["draw_date"])),
            ve=str(payload["ve"]),
            seed=str(payload["seed"]),
            signals=dict(payload.get("signals") or {}),
            sermon=str(payload.get("sermon", "")),
            reasons=tuple(payload.get("reasons") or ()),
            karma=str(payload["karma"]) if payload.get("karma") else None,
            oracle_version=str(payload["oracle_version"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )


def make_seed(
    province: str, draw_date: date, signals: CosmicSignals, karma: str | None
) -> str:
    """The audit trail. Same inputs in, same hex digest out, forever."""
    get_province(province)
    canonical = "|".join(
        (
            KIENTHIET_ORACLE_VERSION,
            "kienthiet",
            province,
            draw_date.isoformat(),
            signals.canonical(),
            karma or "-",
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def latest_special_before(
    boards: Sequence[Board], province: str, before: date
) -> str | None:
    """The đài's own previous giải đặc biệt - its nghiệp báo, and nobody else's."""
    past = [b for b in boards if b.province == province and b.date < before]
    if not past:
        return None
    return max(past, key=lambda b: b.date).special


def cursed_digits(signals: CosmicSignals, karma: str | None) -> CursedDigits:
    """Weight each of the six positions over 0..9. No weight ever reaches zero."""
    weights = [dict.fromkeys(DIGITS, 1.0) for _ in range(TICKET_DIGITS)]
    reasons: list[str] = []

    def boost_everywhere(digit: int, factor: float, why: str) -> None:
        for column in weights:
            column[digit % 10] *= factor
        reasons.append(why)

    root = digit_root(int(signals.lunar_day or 0) + int(signals.lunar_month or 0))
    boost_everywhere(
        root, BOOST_NUMEROLOGY, f"Số gốc hôm nay là {root}. Thầy tính rồi, con khỏi tính lại."
    )

    if signals.btc_usd is not None:
        boost_everywhere(
            signals.btc_usd,
            BOOST_BTC,
            f"Bitcoin ${signals.btc_usd:,}, đuôi {signals.btc_usd % 10}. Tây nó cũng theo thầy.",
        )

    if signals.hanoi_temp_c is not None:
        boost_everywhere(
            signals.hanoi_temp_c,
            BOOST_TEMPERATURE,
            f"Hà Nội {signals.hanoi_temp_c}°C. Trời nóng thì số nó phải nóng theo.",
        )

    if signals.lunar_day is not None:
        boost_everywhere(
            signals.lunar_day,
            BOOST_LUNAR,
            f"Mùng {signals.lunar_day} âm. Ngày nào số nấy, thầy không đổi được.",
        )

    if signals.zodiac:
        boost_everywhere(
            len(signals.zodiac),
            BOOST_ZODIAC,
            f"Năm {signals.zodiac}. Con giáp nó cũng có số của nó.",
        )

    if karma:
        # Position by position, not digit by digit: the đài just printed this number,
        # so each digit is tired exactly where it stood.
        for position, digit in enumerate(karma[-TICKET_DIGITS:]):
            weights[position][int(digit)] *= PENALTY_KARMA
        reasons.append(f"Kỳ trước đài này về {karma}. Trả nghiệp xong rồi, cho nó nghỉ.")

    return CursedDigits(
        weights=tuple(MappingProxyType(column) for column in weights),
        reasons=tuple(reasons),
    )


def _weighted_digit(rng: random.Random, column: Mapping[int, float]) -> int:
    """Deterministic weighted pick over 0..9, iterated in sorted order."""
    total = sum(column.values())
    target = rng.random() * total
    cumulative = 0.0
    for digit in sorted(column):
        cumulative += column[digit]
        if cumulative >= target:
            return digit
    return max(column)  # floating-point tail


def prophesy(
    province: str,
    draw_date: date,
    signals: CosmicSignals,
    *,
    karma: str | None = None,
) -> VeProphecy:
    """Commit to one ticket for one đài on one unfinished day."""
    known = get_province(province)
    if not REGIONS[known.region].prophesiable:
        raise ValueError(
            f"{REGIONS[known.region].display} không phán vé được — "
            "vé có ký hiệu và cơ cấu giải đổi hai lần, không tính ROI trung thực được."
        )

    seed = make_seed(province, draw_date, signals, karma)
    field = cursed_digits(signals, karma)

    rng = random.Random(int(seed[:SEED_BITS], 16))
    ve = "".join(str(_weighted_digit(rng, column)) for column in field.weights)

    sermon_rng = random.Random(int(seed[SEED_BITS : SEED_BITS * 2], 16))
    sermon = sermon_rng.choice(KIENTHIET_SERMONS + GENERIC_SERMONS)

    return VeProphecy(
        province=province,
        region=known.region,
        draw_date=draw_date,
        ve=ve,
        seed=seed,
        signals=signals.as_dict(),
        sermon=sermon,
        reasons=field.reasons,
        karma=karma,
        oracle_version=KIENTHIET_ORACLE_VERSION,
        created_at=utc_now(),
    )
