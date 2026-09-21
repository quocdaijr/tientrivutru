"""The cursed layer: twelve numbers, delivered with total confidence and zero basis.

Determinism is the one serious engineering constraint here. Given the same game,
draw id, draw date and signals, this module must return byte-identical numbers
forever, because prophecies are committed before the draw and scored after it. If
the oracle could drift, the scoreboard would be meaningless.

Everything else in this file is theatre.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from .games import WHEEL_SIZE, GameSpec
from .models import Draw, Prophecy, normalise_draw_id, utc_now
from .sources.vibes import CosmicSignals

ORACLE_VERSION = "1.3.0"
"""1.1.0 added the XSMB signal; 1.2.0 fixed the digit-root rule; 1.3.0 changed the voice.

The version is part of the seed, so changing signals or weights changes every future
prophecy. Prophecies already committed keep the version that produced them, and the
scoreboard can therefore never be flattered by a later 'improvement'.
"""

BOOST_NUMEROLOGY = 1.6
BOOST_BTC = 2.0
BOOST_BTC_NEIGHBOUR = 1.4
BOOST_TEMPERATURE = 1.8
BOOST_LUNAR = 1.5
BOOST_XSMB = 1.7
PENALTY_KARMA = 0.45
SEED_BITS = 16

GENERIC_SERMONS = (
    "Con đừng hỏi nhiều. Thầy nhìn là biết.",
    "Số này thầy giữ lâu rồi, nay cho con.",
    "Thầy không giải thích. Giải thích là mất thiêng.",
    "Con cứ ghi đi, đúng sai tính sau.",
    "Nó im im vậy thôi chứ nó có căn.",
    "Thầy không lấy tiền của con đâu. Đánh đi.",
    "Số này hợp vía con, thầy cảm được.",
    "Đêm qua thầy nằm mơ thấy nó.",
    "Con tin thầy một lần đi, có mất gì đâu.",
    "Thầy chỉ nói một lần thôi đấy.",
    "Số này thầy không cho ai, chỉ cho con.",
    "Nhìn mặt con là thầy biết con hợp số này.",
    "Cái này là lộc, không phải may.",
    "Trúng là phúc nhà con. Trượt là do con đi ngang qua đám ma.",
    "Thầy nói trước: đừng khoe với ai.",
    "Số này nặng vía, con cầm cho chắc.",
    "Thầy thấy nó rung rung, là nó muốn về với con.",
    "Con hỏi vì sao thì thầy chịu. Nhưng cứ đánh.",
    "Thầy ngồi đây ba mươi năm rồi, con nghĩ mà xem.",
    "Số đẹp thế này mà con còn phân vân à?",
)
"""The fortune-teller never says the numbers will win. That sentence is what the
scam sites say, and saying it would turn a joke into the thing it is mocking."""


@dataclass(frozen=True, slots=True)
class CursedField:
    """Per-number weights plus the excuses that produced them."""

    weights: Mapping[int, float]
    reasons: Mapping[int, tuple[str, ...]]


def make_seed(
    spec: GameSpec, draw_id: str, draw_date: date, signals: CosmicSignals
) -> str:
    """The audit trail. Same inputs in, same hex digest out, forever."""
    canonical = "|".join(
        (
            ORACLE_VERSION,
            spec.key,
            normalise_draw_id(draw_id),
            draw_date.isoformat(),
            signals.canonical(),
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def digit_root(value: int) -> int:
    """Repeated digit sum, 1..9. Numerology's favourite operation."""
    n = abs(value)
    while n > 9:
        n = sum(int(ch) for ch in str(n))
    return n or 9


def cursed_weights(
    spec: GameSpec, signals: CosmicSignals, history: Sequence[Draw] = ()
) -> CursedField:
    """Build the weighting the oracle draws from. Never returns a zero weight."""
    weights = dict.fromkeys(spec.numbers, 1.0)
    reasons: dict[int, list[str]] = {n: [] for n in spec.numbers}

    def boost(n: int, factor: float, why: str) -> None:
        if n in weights:
            weights[n] *= factor
            reasons[n].append(why)

    # Digit-root equality, NOT divisibility: a root of 1 divides every number in the
    # pool, so "chia hết cho 1" would fire on all of them and stop being a rule at all.
    date_root = digit_root(int(signals.lunar_day or 0) + int(signals.lunar_month or 0))
    for n in spec.numbers:
        if digit_root(n) == date_root:
            boost(n, BOOST_NUMEROLOGY, f"Số gốc {date_root}. Thầy tính rồi, con khỏi tính lại.")

    if signals.btc_usd is not None:
        target = signals.btc_usd % spec.pool + 1
        boost(
            target,
            BOOST_BTC,
            f"Giá bitcoin ${signals.btc_usd:,} chia ra dư đúng nó. "
            "Tây nó cũng phải theo thầy.",
        )
        for neighbour in (target - 1, target + 1):
            boost(
                neighbour,
                BOOST_BTC_NEIGHBOUR,
                f"Nằm sát số bitcoin ({target}), hưởng lộc lây. Con hiểu chứ?",
            )

    if signals.hanoi_temp_c is not None and signals.hanoi_temp_c in spec.numbers:
        boost(
            signals.hanoi_temp_c,
            BOOST_TEMPERATURE,
            f"Hà Nội {signals.hanoi_temp_c}°C. Trời nóng thế này thì số nó phải nóng theo.",
        )

    if signals.lunar_day is not None and signals.lunar_day in spec.numbers:
        boost(
            signals.lunar_day,
            BOOST_LUNAR,
            f"Hôm nay mùng {signals.lunar_day} âm. Ngày nào số nấy, thầy không đổi được.",
        )

    if signals.xsmb_special is not None:
        target = signals.xsmb_special % spec.pool + 1
        boost(
            target,
            BOOST_XSMB,
            f"Giải đặc biệt hôm qua về {signals.xsmb_special:02d}. Thầy quy nó về đây cho con.",
        )

    if history:
        latest = max(history, key=lambda d: d.draw_id)
        if latest.bonus is not None and latest.bonus in weights:
            weights[latest.bonus] *= PENALTY_KARMA
            reasons[latest.bonus].append(
                f"Số này vừa làm phụ kỳ #{latest.draw_id}, trả nghiệp xong rồi. Cho nó nghỉ."
            )

    if any(w <= 0 for w in weights.values()):
        raise AssertionError("cursed weights must stay positive so every number keeps a chance")

    return CursedField(
        weights=MappingProxyType(weights),
        reasons=MappingProxyType({n: tuple(r) for n, r in reasons.items()}),
    )


def _weighted_sample(
    rng: random.Random, weights: Mapping[int, float], count: int
) -> tuple[int, ...]:
    """Deterministic weighted draw without replacement.

    Iteration is over sorted keys so the result depends only on the seed, never on
    dict construction order.
    """
    if count > len(weights):
        raise ValueError(f"cannot draw {count} distinct numbers from {len(weights)}")
    remaining = dict(weights)
    chosen: list[int] = []
    for _ in range(count):
        total = sum(remaining.values())
        target = rng.random() * total
        cumulative = 0.0
        picked = None
        for n in sorted(remaining):
            cumulative += remaining[n]
            if cumulative >= target:
                picked = n
                break
        if picked is None:  # floating-point tail; take the largest remaining key
            picked = max(remaining)
        chosen.append(picked)
        del remaining[picked]
    return tuple(sorted(chosen))


def sermon_for(
    n: int, field: CursedField, rng: random.Random
) -> str:
    """One confidently invented line explaining a number nobody can explain."""
    reasons = field.reasons.get(n, ())
    if reasons:
        return reasons[0]
    return rng.choice(GENERIC_SERMONS)


def rank_numbers(
    numbers: Sequence[int], field: CursedField, rng: random.Random
) -> tuple[tuple[int, ...], int]:
    """Order the wheel by the oracle's own weight, plus how many actually earned a place.

    The second return value is the honest half. A field commonly boosts one to three of
    the twelve and leaves the rest at exactly 1.0, so any order past that point is a tie -
    arbitrary, not conviction. Returning the count is what stops a caller presenting the
    tail as though the oracle meant it.

    Ties are broken by `rng`, not by number, and that was a measured decision rather than
    a stylistic one. Sorting ties ascending made the six-number pick average 20.79 against
    the wheel's 28.52 over 300 draws - a 7.7 skew toward low numbers, produced entirely by
    the tie-break. Shipping a spurious pattern is the exact thing this project exists to
    mock, so the tie is drawn from the prophecy's own seed: reproducible for a given
    prophecy, unbiased across them.
    """
    order = list(numbers)
    rng.shuffle(order)
    ordered = tuple(sorted(order, key=lambda n: -field.weights.get(n, 1.0)))
    reasoned = sum(1 for n in ordered if field.weights.get(n, 1.0) > 1.0)
    return ordered, reasoned


def prophesy(
    spec: GameSpec,
    draw_id: str,
    draw_date: date,
    signals: CosmicSignals,
    history: Sequence[Draw] = (),
    *,
    wheel: int = WHEEL_SIZE,
) -> Prophecy:
    """Commit to `wheel` numbers for one specific unfinished draw."""
    seed = make_seed(spec, draw_id, draw_date, signals)
    field = cursed_weights(spec, signals, history)

    rng = random.Random(int(seed[:SEED_BITS], 16))
    numbers = _weighted_sample(rng, field.weights, wheel)

    sermon_rng = random.Random(int(seed[SEED_BITS : SEED_BITS * 2], 16))
    sermon = {str(n): sermon_for(n, field, sermon_rng) for n in numbers}

    # Describes the committed numbers; never alters them. The seed and the sample above
    # are untouched, so adding this cannot change a single prophecy already on record.
    # A third slice of the seed, so the tie-break cannot disturb the sample or the sermons.
    tie_rng = random.Random(int(seed[SEED_BITS * 2 : SEED_BITS * 3], 16))
    ranked, reasoned = rank_numbers(numbers, field, tie_rng)

    return Prophecy(
        game=spec.key,
        draw_id=draw_id,
        draw_date=draw_date,
        numbers=numbers,
        seed=seed,
        signals=signals.as_dict(),
        sermon=sermon,
        oracle_version=ORACLE_VERSION,
        created_at=utc_now(),
        ranked=ranked,
        reasoned=reasoned,
    )
