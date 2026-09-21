"""The honest layer: what the data actually says, which is almost nothing.

Chi-square is computed without scipy - a regularised incomplete gamma function is
about thirty lines and keeps the dependency list thin enough to run anywhere.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .games import GameSpec
from .models import Draw

MAX_ITERATIONS = 500
EPSILON = 3.0e-12
TINY = 1.0e-300
SIGNIFICANCE = 0.05


@dataclass(frozen=True, slots=True)
class ChiSquareResult:
    statistic: float
    degrees_of_freedom: int
    p_value: float
    observations: int

    @property
    def rejects_uniform(self) -> bool:
        """True if we can reject 'every number is equally likely' at p < 0.05."""
        return self.p_value < SIGNIFICANCE


def _lower_gamma_series(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x) via its series expansion."""
    total = 1.0 / a
    term = total
    for n in range(1, MAX_ITERATIONS):
        term *= x / (a + n)
        total += term
        if abs(term) < abs(total) * EPSILON:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _upper_gamma_fraction(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) via the Lentz continued fraction."""
    b = x + 1.0 - a
    c = 1.0 / TINY
    d = 1.0 / b
    h = d
    for i in range(1, MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < TINY:
            d = TINY
        c = b + an / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPSILON:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def chi_square_sf(statistic: float, degrees_of_freedom: int) -> float:
    """P(X > statistic) for a chi-square distribution - the p-value."""
    if degrees_of_freedom <= 0:
        raise ValueError(f"degrees_of_freedom must be positive, got {degrees_of_freedom}")
    if statistic < 0:
        raise ValueError(f"chi-square statistic cannot be negative, got {statistic}")
    if statistic == 0:
        return 1.0
    a = degrees_of_freedom / 2.0
    x = statistic / 2.0
    if x < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _lower_gamma_series(a, x)))
    return max(0.0, min(1.0, _upper_gamma_fraction(a, x)))


def frequency(draws: Sequence[Draw], spec: GameSpec) -> Mapping[int, int]:
    """How often each number appeared among the main numbers."""
    counts = dict.fromkeys(spec.numbers, 0)
    for draw in draws:
        for n in draw.main:
            counts[n] += 1
    return MappingProxyType(counts)


def gaps_since_last(draws: Sequence[Draw], spec: GameSpec) -> Mapping[int, int]:
    """Draws elapsed since each number last appeared.

    A number never drawn gets the full history length. This is descriptive only:
    a large gap predicts precisely nothing about the next draw.
    """
    ordered = sorted(draws, key=lambda d: d.draw_id)
    total = len(ordered)
    last_seen: dict[int, int] = {}
    for index, draw in enumerate(ordered):
        for n in draw.main:
            last_seen[n] = index
    return MappingProxyType(
        {n: total - 1 - last_seen[n] if n in last_seen else total for n in spec.numbers}
    )


def chi_square_uniform(draws: Sequence[Draw], spec: GameSpec) -> ChiSquareResult:
    """Test H0: every number in the pool is equally likely."""
    if not draws:
        raise ValueError("cannot test uniformity with no draws")
    counts = frequency(draws, spec)
    observations = len(draws) * spec.pick
    expected = observations / spec.pool
    statistic = sum((count - expected) ** 2 / expected for count in counts.values())
    df = spec.pool - 1
    return ChiSquareResult(
        statistic=statistic,
        degrees_of_freedom=df,
        p_value=chi_square_sf(statistic, df),
        observations=observations,
    )


def verdict(result: ChiSquareResult) -> str:
    """Plain-language conclusion. Almost always the disappointing one."""
    if result.rejects_uniform:
        return (
            f"p = {result.p_value:.4f} < 0.05. Về mặt kỹ thuật đây là sai lệch đáng kể — "
            "nhưng trước khi mở sâm banh, hãy nhớ: test nào làm đủ nhiều lần cũng sẽ "
            "có lần báo động nhầm."
        )
    return (
        f"p = {result.p_value:.4f} > 0.05. Không có số nào nóng. Không có số nào lạnh. "
        "Toàn bộ ngành thống kê vừa nhìn anh và lắc đầu."
    )


def hottest(draws: Sequence[Draw], spec: GameSpec, n: int = 5) -> tuple[tuple[int, int], ...]:
    """The n most-drawn numbers. Displayed purely so the chi-square can debunk it."""
    counts = frequency(draws, spec)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return tuple(ranked[:n])


def coldest(draws: Sequence[Draw], spec: GameSpec, n: int = 5) -> tuple[tuple[int, int], ...]:
    counts = frequency(draws, spec)
    ranked = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    return tuple(ranked[:n])
