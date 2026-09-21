"""The honest layer. Includes a check that it can still detect real bias."""

from __future__ import annotations

import random

import pytest

from conftest import make_draw, random_draw
from tientrivutru import stats
from tientrivutru.games import MEGA645

SAMPLE_DRAWS = 500
SEED = 20260819


@pytest.mark.parametrize(
    "statistic,df,expected_p",
    [
        (3.841459, 1, 0.05),
        (5.991465, 2, 0.05),
        (18.307038, 10, 0.05),
        (2.705543, 1, 0.10),
        (6.634897, 1, 0.01),
    ],
)
def test_chi_square_sf_matches_published_critical_values(statistic, df, expected_p):
    """Validates the hand-rolled incomplete gamma against standard chi-square tables."""
    assert stats.chi_square_sf(statistic, df) == pytest.approx(expected_p, abs=1e-4)


def test_chi_square_sf_bounds():
    assert stats.chi_square_sf(0.0, 44) == 1.0
    assert stats.chi_square_sf(10_000.0, 44) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("bad", [(-1.0, 4), (1.0, 0), (1.0, -3)])
def test_chi_square_sf_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        stats.chi_square_sf(*bad)


def test_frequency_counts_every_main_number():
    draws = [
        make_draw(MEGA645, 1, main=(1, 2, 3, 4, 5, 6)),
        make_draw(MEGA645, 2, main=(1, 2, 3, 40, 41, 42)),
    ]
    freq = stats.frequency(draws, MEGA645)

    assert freq[1] == 2
    assert freq[6] == 1
    assert freq[45] == 0
    assert sum(freq.values()) == 12
    assert set(freq) == set(MEGA645.numbers)


def test_gaps_measure_draws_since_last_appearance():
    draws = [
        make_draw(MEGA645, 1, main=(1, 2, 3, 4, 5, 6)),
        make_draw(MEGA645, 2, main=(7, 8, 9, 10, 11, 12)),
        make_draw(MEGA645, 3, main=(13, 14, 15, 16, 17, 18)),
    ]
    gaps = stats.gaps_since_last(draws, MEGA645)

    assert gaps[13] == 0  # in the most recent draw
    assert gaps[7] == 1
    assert gaps[1] == 2
    assert gaps[45] == 3  # never drawn -> full history length


def test_uniform_random_history_is_not_rejected():
    """Truly uniform data must survive the test - otherwise the test is broken."""
    rng = random.Random(SEED)
    draws = [random_draw(MEGA645, i, rng) for i in range(SAMPLE_DRAWS)]

    result = stats.chi_square_uniform(draws, MEGA645)

    assert result.degrees_of_freedom == MEGA645.pool - 1
    assert result.observations == SAMPLE_DRAWS * MEGA645.pick
    assert 0.0 <= result.p_value <= 1.0
    assert not result.rejects_uniform
    assert "lắc đầu" in stats.verdict(result)


def test_blatant_bias_is_rejected():
    """A rigged history must be caught, or the honest layer is decoration."""
    draws = [make_draw(MEGA645, i, main=(1, 2, 3, 4, 5, 6)) for i in range(200)]

    result = stats.chi_square_uniform(draws, MEGA645)

    assert result.rejects_uniform
    assert result.p_value < 1e-6
    assert "sai lệch đáng kể" in stats.verdict(result)


def test_chi_square_requires_data():
    with pytest.raises(ValueError, match="no draws"):
        stats.chi_square_uniform([], MEGA645)


def test_hottest_and_coldest_are_complementary():
    draws = [make_draw(MEGA645, i, main=(1, 2, 3, 4, 5, 6)) for i in range(10)]

    hot = stats.hottest(draws, MEGA645, n=3)
    cold = stats.coldest(draws, MEGA645, n=3)

    assert [n for n, _ in hot] == [1, 2, 3]
    assert all(count == 10 for _, count in hot)
    assert all(count == 0 for _, count in cold)
