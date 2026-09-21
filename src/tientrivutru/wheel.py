"""The combinatorics of bao 12 - playing all C(12,6) = 924 combinations.

This module is the only place that knows how a wheel converts "k of my numbers
were drawn" into money. Everything downstream (scoreboard, ROI, the humiliation
counter) reads from here, so it is exact closed-form arithmetic, never simulation.

Let k = |wheel and main|, b = 1 if the bonus number sits inside the wheel.
The number of my combinations matching exactly j main numbers is

    N(j) = C(k, j) * C(wheel - k, pick - j)

which sums to C(wheel, pick) by Vandermonde's identity - asserted in tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import comb
from types import MappingProxyType

from .games import WHEEL_SIZE, GameSpec

FIXED_TIERS = ("first", "second", "third")


def total_combinations(spec: GameSpec, wheel: int = WHEEL_SIZE) -> int:
    """How many tickets a wheel of `wheel` numbers actually buys."""
    return comb(wheel, spec.pick)


def wheel_cost_vnd(spec: GameSpec, wheel: int = WHEEL_SIZE) -> int:
    """Cost of covering the whole wheel for one draw."""
    return total_combinations(spec, wheel) * spec.unit_price_vnd


def match_distribution(spec: GameSpec, k: int, wheel: int = WHEEL_SIZE) -> tuple[int, ...]:
    """N(j) for j = 0..pick: how many of my combinations match exactly j main numbers."""
    _validate_k(spec, k, wheel)
    return tuple(comb(k, j) * comb(wheel - k, spec.pick - j) for j in range(spec.pick + 1))


def prize_counts(
    spec: GameSpec, k: int, bonus_hit: bool = False, wheel: int = WHEEL_SIZE
) -> Mapping[str, int]:
    """How many combinations win each prize tier, given k hits and whether the bonus landed.

    Only the highest tier per ticket counts, which the tier partition below respects:
    a 5-main combination is either Jackpot 2 (it also carries the bonus) or First,
    never both.
    """
    _validate_k(spec, k, wheel)
    b = 1 if bonus_hit else 0
    if b and not spec.has_bonus:
        raise ValueError(f"{spec.key} has no bonus number, so bonus_hit cannot be True")
    if b and k >= wheel:
        raise ValueError(
            f"bonus cannot be in the wheel: all {wheel} slots are main hits (k={k})"
        )

    misses = wheel - k
    five = comb(k, spec.pick - 1)

    if spec.has_bonus:
        counts = {
            "jackpot1": comb(k, spec.pick),
            "jackpot2": five * b,
            # 5 main + a sixth number that is NOT the bonus
            "first": five * (misses - b),
            "second": comb(k, spec.pick - 2) * comb(misses, 2),
            "third": comb(k, spec.pick - 3) * comb(misses, 3),
        }
    else:
        counts = {
            "jackpot": comb(k, spec.pick),
            "first": five * comb(misses, 1),
            "second": comb(k, spec.pick - 2) * comb(misses, 2),
            "third": comb(k, spec.pick - 3) * comb(misses, 3),
        }
    return MappingProxyType(counts)


def payout_vnd(
    spec: GameSpec,
    counts: Mapping[str, int],
    *,
    jackpots: Mapping[str, int] | None = None,
) -> int:
    """Total winnings for a set of prize counts.

    Jackpots default to their published floor. Real jackpots roll over and are
    usually larger, so this is a deliberate lower bound on winnings - it makes the
    ROI verdict pessimistic rather than flattering.
    """
    values = dict(spec.jackpot_floor)
    if jackpots:
        unknown = set(jackpots) - set(values)
        if unknown:
            raise ValueError(f"{spec.key} has no jackpot tier(s): {sorted(unknown)}")
        values.update(jackpots)
    values.update(spec.prizes)

    total = 0
    for tier, n in counts.items():
        if n < 0:
            raise ValueError(f"negative prize count for {tier}: {n}")
        if tier not in values:
            raise ValueError(f"unknown prize tier {tier!r} for {spec.key}")
        total += n * values[tier]
    return total


def hit_probability(spec: GameSpec, k: int, wheel: int = WHEEL_SIZE) -> float:
    """P(exactly k of my `wheel` numbers are among the `pick` drawn).

    Hypergeometric: the wheel is the success set, the draw is the sample.
    """
    _validate_k(spec, k, wheel)
    return (
        comb(wheel, k) * comb(spec.pool - wheel, spec.pick - k) / comb(spec.pool, spec.pick)
    )


def expected_payout_vnd(
    spec: GameSpec, *, wheel: int = WHEEL_SIZE, include_jackpot: bool = True
) -> float:
    """Expected winnings per draw for a wheel bet - the honest number."""
    total = 0.0
    for k in range(spec.pick + 1):
        counts = dict(prize_counts(spec, k, bonus_hit=False, wheel=wheel))
        if not include_jackpot:
            counts = {t: n for t, n in counts.items() if t in FIXED_TIERS}
        total += hit_probability(spec, k, wheel) * payout_vnd(spec, counts)
    return total


def expected_roi(spec: GameSpec, *, wheel: int = WHEEL_SIZE, include_jackpot: bool = True) -> float:
    """Expected return on investment. Always negative. That is the whole point."""
    cost = wheel_cost_vnd(spec, wheel)
    return expected_payout_vnd(spec, wheel=wheel, include_jackpot=include_jackpot) / cost - 1.0


def _validate_k(spec: GameSpec, k: int, wheel: int) -> None:
    if wheel < spec.pick:
        raise ValueError(f"wheel of {wheel} cannot cover {spec.pick} picks")
    if wheel > spec.pool:
        raise ValueError(f"wheel of {wheel} exceeds pool of {spec.pool}")
    if not 0 <= k <= spec.pick:
        raise ValueError(f"k must be within 0..{spec.pick}, got {k}")
    if k > wheel:
        raise ValueError(f"k={k} cannot exceed wheel size {wheel}")
