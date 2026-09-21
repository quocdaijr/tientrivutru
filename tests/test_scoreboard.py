"""Scoring, and the anti-delusion tests.

The most important test in this file is test_roi_is_a_loss_on_random_prophecies: if
someone "improves" the oracle into positive territory, the bug is here, not in their
genius.
"""

from __future__ import annotations

import random

import pytest

from conftest import ALL_GAMES, make_draw, make_prophecy, random_draw, random_prophecy
from tientrivutru import scoreboard, wheel
from tientrivutru.games import MEGA645, POWER655

BACKTEST_DRAWS = 400
BACKTEST_SEED = 20260819


def test_score_counts_hits():
    prophecy = make_prophecy(MEGA645, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(MEGA645, 1, main=(1, 2, 3, 40, 41, 42))

    row = scoreboard.score_one(MEGA645, prophecy, draw)
    assert row.hits == 3
    assert row.payout_vnd == 2_520_000
    assert row.cost_vnd == 9_240_000


def test_score_detects_bonus_hit():
    prophecy = make_prophecy(POWER655, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(POWER655, 1, main=(1, 2, 3, 4, 5, 50), bonus=11)

    row = scoreboard.score_one(POWER655, prophecy, draw)
    assert row.hits == 5
    assert row.bonus_hit is True
    assert row.prize_counts["jackpot2"] == 1
    assert row.won_jackpot is True


def test_bonus_outside_wheel_is_not_a_hit():
    prophecy = make_prophecy(POWER655, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(POWER655, 1, main=(1, 2, 3, 4, 5, 50), bonus=55)

    row = scoreboard.score_one(POWER655, prophecy, draw)
    assert row.bonus_hit is False
    assert row.prize_counts["jackpot2"] == 0


def test_perfect_prophecy_wins_jackpot():
    prophecy = make_prophecy(MEGA645, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(MEGA645, 1, main=(1, 2, 3, 4, 5, 6))

    row = scoreboard.score_one(MEGA645, prophecy, draw)
    assert row.hits == 6
    assert row.prize_counts["jackpot"] == 1
    assert row.payout_vnd > 12_000_000_000


def test_score_rejects_mismatched_draw():
    with pytest.raises(ValueError, match="prophecy targets draw"):
        scoreboard.score_one(MEGA645, make_prophecy(MEGA645, 1), make_draw(MEGA645, 2))


def test_score_rejects_mismatched_game():
    with pytest.raises(ValueError, match="cannot score"):
        scoreboard.score_one(MEGA645, make_prophecy(MEGA645, 1), make_draw(POWER655, 1))


def test_only_settled_draws_are_scored():
    """A prophecy without a result must not appear, in either direction."""
    prophecies = [make_prophecy(MEGA645, i) for i in (1, 2, 3)]
    draws = [make_draw(MEGA645, 1), make_draw(MEGA645, 2)]

    score = scoreboard.build(MEGA645, prophecies, draws)
    assert score.draws_scored == 2


def test_unprophesied_draws_are_not_scored():
    draws = [make_draw(MEGA645, i) for i in (1, 2)]
    score = scoreboard.build(MEGA645, [make_prophecy(MEGA645, 1)], draws)
    assert score.draws_scored == 1


def test_empty_scoreboard_is_neutral():
    score = scoreboard.build(MEGA645, [], [])
    assert score.draws_scored == 0
    assert score.roi == 0.0
    assert score.best_draw is None
    assert score.hits_per_draw_expected == pytest.approx(1.6)


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_hit_rate_matches_expectation_on_random_input(spec):
    """Random prophecies against random draws must land on the hypergeometric mean."""
    rng = random.Random(BACKTEST_SEED)
    prophecies = [random_prophecy(spec, i, rng) for i in range(BACKTEST_DRAWS)]
    draws = [random_draw(spec, i, rng) for i in range(BACKTEST_DRAWS)]

    score = scoreboard.build(spec, prophecies, draws)
    expected = spec.expected_hits()
    # Standard error of the mean over 400 draws; 4 sigma keeps this from flaking.
    tolerance = 4 * (expected**0.5) / (BACKTEST_DRAWS**0.5)

    assert score.draws_scored == BACKTEST_DRAWS
    assert score.hits_per_draw_actual == pytest.approx(expected, abs=tolerance)


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_roi_is_a_loss_on_random_prophecies(spec):
    """No jackpot means a heavy loss. A positive ROI here means a scoring bug."""
    rng = random.Random(BACKTEST_SEED)
    prophecies = [random_prophecy(spec, i, rng) for i in range(BACKTEST_DRAWS)]
    draws = [random_draw(spec, i, rng) for i in range(BACKTEST_DRAWS)]

    score = scoreboard.build(spec, prophecies, draws)

    if score.jackpot_hits:
        pytest.skip(f"{spec.key}: seed happened to hit {score.jackpot_hits} jackpot(s)")

    assert score.paper_burned_vnd == BACKTEST_DRAWS * 9_240_000
    assert -1.0 <= score.roi < -0.5
    # And it must sit near the theoretical no-jackpot bound rather than wander off.
    assert score.roi == pytest.approx(wheel.expected_roi(spec, include_jackpot=False), abs=0.25)


def test_one_jackpot_flips_roi_but_not_the_jackpot_free_figure():
    """The real backtest result: a single jackpot in ~1350 draws turned ROI positive
    while the hit rate stayed exactly at chance. The jackpot-free ROI must stay honest.
    """
    losers = 200
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in range(losers + 1)]
    draws = [make_draw(MEGA645, i, main=(20, 21, 22, 23, 24, 25)) for i in range(losers)]
    draws.append(make_draw(MEGA645, losers, main=(1, 2, 3, 4, 5, 6)))  # the lucky one

    score = scoreboard.build(MEGA645, prophecies, draws)

    assert score.jackpot_hits == 1
    assert score.roi > 0, "12 billion dong on a 1.86 billion stake is a paper profit"
    # Strip the jackpot and the same history is a heavy loss. The 6-hit draw still
    # pays 439.5M in fixed tiers, so this is a loss, not a total wipeout.
    assert score.roi_excluding_jackpot < -0.5
    assert score.roi - score.roi_excluding_jackpot > 5.0, "one jackpot dominates the story"
    assert score.paper_won_excluding_jackpot_vnd < score.paper_won_vnd


def test_jackpot_free_payout_excludes_only_jackpot_tiers():
    prophecy = make_prophecy(POWER655, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(POWER655, 1, main=(1, 2, 3, 4, 5, 6), bonus=7)

    row = scoreboard.score_one(POWER655, prophecy, draw)

    assert row.prize_counts["jackpot1"] == 1
    assert row.payout_excluding_jackpot_vnd < row.payout_vnd
    # The fixed tiers survive untouched.
    expected_fixed = wheel.payout_vnd(
        POWER655, {t: row.prize_counts[t] for t in ("first", "second", "third")}
    )
    assert row.payout_excluding_jackpot_vnd == expected_fixed


def test_roi_excluding_jackpot_equals_roi_when_no_jackpot():
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in (1, 2)]
    draws = [make_draw(MEGA645, i, main=(1, 2, 3, 40, 41, 42)) for i in (1, 2)]

    score = scoreboard.build(MEGA645, prophecies, draws)
    assert score.roi == pytest.approx(score.roi_excluding_jackpot)


def test_best_draw_is_the_highest_hit_count():
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in (1, 2)]
    draws = [
        make_draw(MEGA645, 1, main=(1, 2, 40, 41, 42, 43)),
        make_draw(MEGA645, 2, main=(1, 2, 3, 4, 42, 43)),
    ]

    score = scoreboard.build(MEGA645, prophecies, draws)
    assert score.best_draw.draw_id == "00002"
    assert score.best_draw.hits == 4


def test_totals_accumulate_across_draws():
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in (1, 2)]
    draws = [make_draw(MEGA645, i, main=(1, 2, 3, 40, 41, 42)) for i in (1, 2)]

    score = scoreboard.build(MEGA645, prophecies, draws)
    assert score.hits_total == 6
    assert score.prize_counts_total["third"] == 168
    assert score.paper_won_vnd == 2 * 2_520_000
    assert score.paper_burned_vnd == 2 * 9_240_000


def test_as_json_is_serialisable_and_carries_disclaimer():
    import json

    scores = scoreboard.build_all(
        [make_prophecy(MEGA645, 1)], {"mega645": [make_draw(MEGA645, 1)]}
    )
    payload = scoreboard.as_json(scores)
    text = json.dumps(payload, ensure_ascii=False)

    assert "disclaimer" in payload
    assert "mega645" in payload["per_game"]
    assert json.loads(text)["per_game"]["mega645"]["draws_scored"] == 1
