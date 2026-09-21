"""The wheel maths. If anything here is wrong, every money figure downstream is a lie."""

from __future__ import annotations

from math import comb, isclose

import pytest

from conftest import ALL_GAMES
from tientrivutru import wheel
from tientrivutru.games import MEGA645, POWER655, WHEEL_SIZE

TOTAL_COMBINATIONS = 924
WHEEL_COST_VND = 9_240_000


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_bao_12_buys_924_tickets_for_9_24m(spec):
    assert wheel.total_combinations(spec) == TOTAL_COMBINATIONS
    assert wheel.wheel_cost_vnd(spec) == WHEEL_COST_VND


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
@pytest.mark.parametrize("k", range(7))
def test_wheel_counts_sum_to_924(spec, k):
    """Vandermonde: the match distribution must partition all 924 combinations."""
    assert sum(wheel.match_distribution(spec, k)) == TOTAL_COMBINATIONS


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
@pytest.mark.parametrize("k", range(7))
def test_prize_counts_never_exceed_match_distribution(spec, k):
    """Every winning combination must be a real combination, counted once."""
    counts = wheel.prize_counts(spec, k, bonus_hit=False)
    distribution = wheel.match_distribution(spec, k)
    winners = sum(counts.values())
    assert winners == sum(distribution[3:]), f"k={k}: tier partition lost combinations"


def test_wheel_k6_wins_exactly_one_jackpot():
    assert wheel.prize_counts(MEGA645, 6)["jackpot"] == 1
    assert wheel.prize_counts(POWER655, 6)["jackpot1"] == 1


def test_wheel_jackpot2_requires_bonus():
    """Power 6/55 Jackpot 2 needs 5 main numbers AND the bonus."""
    without = wheel.prize_counts(POWER655, 5, bonus_hit=False)
    with_bonus = wheel.prize_counts(POWER655, 5, bonus_hit=True)

    assert without["jackpot2"] == 0
    assert with_bonus["jackpot2"] == 1
    # The bonus combination is promoted out of first prize, not invented.
    assert with_bonus["first"] == without["first"] - 1
    assert sum(with_bonus.values()) == sum(without.values())


def test_bonus_hit_rejected_for_game_without_bonus():
    with pytest.raises(ValueError, match="no bonus number"):
        wheel.prize_counts(MEGA645, 5, bonus_hit=True)


def test_wheel_k3_payout_is_2_520_000_for_mega645():
    """Hitting 3 of 6 pays 84 x 30,000d - still a 72.7% loss on the 9.24M stake."""
    counts = wheel.prize_counts(MEGA645, 3)
    assert counts == {"jackpot": 0, "first": 0, "second": 0, "third": 84}
    payout = wheel.payout_vnd(MEGA645, counts)
    assert payout == 2_520_000
    assert payout < WHEEL_COST_VND


def test_wheel_k3_payout_is_4_200_000_for_power655():
    counts = wheel.prize_counts(POWER655, 3)
    assert counts["third"] == 84
    assert wheel.payout_vnd(POWER655, counts) == 4_200_000


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_hit_probabilities_sum_to_one(spec):
    total = sum(wheel.hit_probability(spec, k) for k in range(spec.pick + 1))
    assert isclose(total, 1.0, abs_tol=1e-12)


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_expected_hits_matches_hypergeometric_mean(spec):
    """E[hits] must equal pick * wheel / pool exactly."""
    weighted = sum(k * wheel.hit_probability(spec, k) for k in range(spec.pick + 1))
    assert isclose(weighted, spec.expected_hits(), abs_tol=1e-9)
    assert isclose(spec.expected_hits(), spec.pick * WHEEL_SIZE / spec.pool)


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_expected_roi_is_negative_with_and_without_jackpot(spec):
    """The house edge is not optional. Both bounds must be losses."""
    with_jackpot = wheel.expected_roi(spec)
    without_jackpot = wheel.expected_roi(spec, include_jackpot=False)

    assert -1.0 < with_jackpot < 0.0, f"{spec.key}: ROI {with_jackpot} is not a loss"
    assert -1.0 < without_jackpot < with_jackpot
    # Jackpots at their published floor still leave a brutal edge.
    assert with_jackpot < -0.5


def test_expected_roi_reference_values():
    """Pins the headline numbers so a refactor cannot quietly flatter the odds."""
    assert wheel.expected_roi(MEGA645) == pytest.approx(-0.7157, abs=5e-4)
    assert wheel.expected_roi(MEGA645, include_jackpot=False) == pytest.approx(-0.8630, abs=5e-4)
    assert wheel.expected_roi(POWER655) == pytest.approx(-0.7620, abs=5e-4)
    assert wheel.expected_roi(POWER655, include_jackpot=False) == pytest.approx(-0.8655, abs=5e-4)


def test_jackpot_probability_matches_combinatorics():
    """P(all 6) for a 12-number wheel is C(12,6) / C(pool,6)."""
    assert wheel.hit_probability(MEGA645, 6) == pytest.approx(
        comb(12, 6) / comb(45, 6), rel=1e-12
    )


@pytest.mark.parametrize("bad_k", [-1, 7, 99])
def test_invalid_k_rejected(bad_k):
    with pytest.raises(ValueError):
        wheel.prize_counts(MEGA645, bad_k)


def test_unknown_prize_tier_rejected():
    with pytest.raises(ValueError, match="unknown prize tier"):
        wheel.payout_vnd(MEGA645, {"giai_tuong_tuong": 1})


def test_jackpot_override_must_name_a_real_tier():
    with pytest.raises(ValueError, match="no jackpot tier"):
        wheel.payout_vnd(MEGA645, {"jackpot": 1}, jackpots={"jackpot2": 1})


def test_jackpot_override_is_respected():
    counts = wheel.prize_counts(MEGA645, 6)
    floor = wheel.payout_vnd(MEGA645, counts)
    rolled_over = wheel.payout_vnd(MEGA645, counts, jackpots={"jackpot": 100_000_000_000})
    assert rolled_over > floor
