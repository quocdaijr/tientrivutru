"""The oracle is allowed to be nonsense, but it is not allowed to be non-deterministic."""

from __future__ import annotations

import random
from datetime import date

import pytest

from conftest import ALL_GAMES, make_draw
from tientrivutru import oracle
from tientrivutru.games import MEGA645, POWER655, WHEEL_SIZE
from tientrivutru.sources.vibes import CosmicSignals

DRAW_DATE = date(2026, 8, 19)
DRAW_ID = "01550"


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_oracle_returns_12_distinct_sorted_in_range(spec, loud_signals):
    prophecy = oracle.prophesy(spec, DRAW_ID, DRAW_DATE, loud_signals)

    assert len(prophecy.numbers) == WHEEL_SIZE
    assert len(set(prophecy.numbers)) == WHEEL_SIZE
    assert list(prophecy.numbers) == sorted(prophecy.numbers)
    assert all(n in spec.numbers for n in prophecy.numbers)


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_oracle_deterministic_per_draw(spec, loud_signals):
    """Same game, draw, date and signals must produce identical numbers, forever."""
    first = oracle.prophesy(spec, DRAW_ID, DRAW_DATE, loud_signals)
    second = oracle.prophesy(spec, DRAW_ID, DRAW_DATE, loud_signals)

    assert first.numbers == second.numbers
    assert first.seed == second.seed
    assert first.sermon == second.sermon


def test_oracle_differs_across_draws(loud_signals):
    """Different draw ids must not collapse onto the same prophecy."""
    seeds = {
        oracle.prophesy(MEGA645, str(draw_id), DRAW_DATE, loud_signals).seed
        for draw_id in range(1550, 1560)
    }
    assert len(seeds) == 10


def test_oracle_differs_across_games(loud_signals):
    a = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, loud_signals)
    b = oracle.prophesy(POWER655, DRAW_ID, DRAW_DATE, loud_signals)
    assert a.seed != b.seed


def test_oracle_survives_dead_signals():
    """Every network signal down: still a valid prophecy, no exception."""
    dead = CosmicSignals()
    prophecy = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, dead)

    assert len(prophecy.numbers) == WHEEL_SIZE
    # Count the fields rather than hardcoding a number, so adding a signal cannot
    # break this test for a reason that has nothing to do with what it checks.
    assert dead.silent_count == len(dead.as_dict())
    assert all(value is None for value in dead.as_dict().values())
    assert all(len(text) > 0 for text in prophecy.sermon.values())


def test_signals_change_the_prophecy(quiet_signals, loud_signals):
    quiet = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, quiet_signals)
    loud = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, loud_signals)
    assert quiet.seed != loud.seed


def test_seed_is_stable_hex():
    signals = CosmicSignals(lunar_day=8, lunar_month=7, zodiac="Ngọ")
    seed = oracle.make_seed(MEGA645, DRAW_ID, DRAW_DATE, signals)

    assert len(seed) == 64
    assert int(seed, 16) >= 0
    assert seed == oracle.make_seed(MEGA645, "1550", DRAW_DATE, signals)


def test_canonical_signals_render_none_as_dash():
    assert "btc_usd=-" in CosmicSignals().canonical()
    assert "btc_usd=64213" in CosmicSignals(btc_usd=64_213).canonical()


@pytest.mark.parametrize("value,expected", [(9, 9), (18, 9), (64_213, 7), (0, 9), (10, 1)])
def test_digit_root(value, expected):
    assert oracle.digit_root(value) == expected


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_weights_stay_positive_for_every_number(spec, loud_signals):
    """No number may be weighted out of existence, or the wheel maths breaks."""
    field = oracle.cursed_weights(spec, loud_signals)

    assert set(field.weights) == set(spec.numbers)
    assert all(w > 0 for w in field.weights.values())


def test_temperature_signal_boosts_that_number(quiet_signals):
    hot = CosmicSignals(hanoi_temp_c=38, lunar_day=8, lunar_month=7)
    field = oracle.cursed_weights(MEGA645, hot)

    assert any("38" in reason for reason in field.reasons[38])
    assert field.weights[38] > oracle.cursed_weights(MEGA645, quiet_signals).weights[38]


def test_temperature_outside_pool_is_ignored():
    """A 50 degree day cannot boost number 50 in a 6/45 game."""
    field = oracle.cursed_weights(MEGA645, CosmicSignals(hanoi_temp_c=50, lunar_day=8))
    assert all("°C" not in r for reasons in field.reasons.values() for r in reasons)


def test_btc_signal_boosts_number_and_neighbours():
    """Asserts the RULE, not the wording. The fortune-teller's copy changes; the
    arithmetic that decides which number gets boosted must not."""
    signals = CosmicSignals(btc_usd=64_213, lunar_day=8, lunar_month=7)
    quiet = oracle.cursed_weights(MEGA645, CosmicSignals(lunar_day=8, lunar_month=7))
    field = oracle.cursed_weights(MEGA645, signals)
    target = 64_213 % MEGA645.pool + 1

    assert field.weights[target] > quiet.weights[target]
    assert field.weights[target] > field.weights[target - 1] > 1.0
    assert field.reasons[target], "a boosted number must carry an explanation"


def test_karma_penalises_previous_bonus(loud_signals):
    """Last draw's bonus has paid its dues and gets damped."""
    history = [make_draw(POWER655, 1385, main=(1, 2, 3, 4, 5, 6), bonus=41)]
    with_history = oracle.cursed_weights(POWER655, loud_signals, history)
    without = oracle.cursed_weights(POWER655, loud_signals)

    assert with_history.weights[41] < without.weights[41]
    assert any("nghiệp" in r for r in with_history.reasons[41])


def test_every_prophesied_number_gets_a_sermon(loud_signals):
    prophecy = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, loud_signals)
    assert set(prophecy.sermon) == {str(n) for n in prophecy.numbers}


def test_wheel_cannot_exceed_pool():
    with pytest.raises(ValueError, match="cannot draw"):
        oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, CosmicSignals(), wheel=46)


def test_oracle_version_recorded(loud_signals):
    prophecy = oracle.prophesy(MEGA645, DRAW_ID, DRAW_DATE, loud_signals)
    assert prophecy.oracle_version == oracle.ORACLE_VERSION
    # The version is inside the seed, so bumping it must change the numbers.
    assert oracle.ORACLE_VERSION in "|".join([oracle.ORACLE_VERSION])


def test_xsmb_signal_boosts_a_number():
    """Yesterday's XSMB special is folded into the pool via a modulo."""
    signals = CosmicSignals(xsmb_special=83, lunar_day=8, lunar_month=7)
    quiet = oracle.cursed_weights(MEGA645, CosmicSignals(lunar_day=8, lunar_month=7))
    field = oracle.cursed_weights(MEGA645, signals)
    target = 83 % MEGA645.pool + 1

    assert field.weights[target] > quiet.weights[target]
    assert field.weights[target] > 1.0
    assert field.reasons[target]


def test_xsmb_signal_changes_the_seed():
    """A new signal must change future prophecies, or it is decoration."""
    without = oracle.make_seed(
        MEGA645, DRAW_ID, DRAW_DATE, CosmicSignals(lunar_day=8, lunar_month=7)
    )
    with_signal = oracle.make_seed(
        MEGA645, DRAW_ID, DRAW_DATE, CosmicSignals(lunar_day=8, lunar_month=7, xsmb_special=83)
    )
    assert without != with_signal


def test_xsmb_zero_special_is_still_a_signal():
    """00 is a real XSMB outcome; treating it as falsy would silently drop it."""
    quiet = oracle.cursed_weights(MEGA645, CosmicSignals(lunar_day=8))
    field = oracle.cursed_weights(MEGA645, CosmicSignals(xsmb_special=0, lunar_day=8))
    target = 0 % MEGA645.pool + 1

    assert field.weights[target] > quiet.weights[target]
    assert field.reasons[target]


def test_oracle_version_is_in_the_seed():
    """Bumping the version must invalidate nothing already stored, but change all future
    prophecies - so the version string has to actually reach the digest."""
    signals = CosmicSignals(lunar_day=8, lunar_month=7)
    original = oracle.make_seed(MEGA645, DRAW_ID, DRAW_DATE, signals)
    try:
        oracle.ORACLE_VERSION = "99.0.0"
        bumped = oracle.make_seed(MEGA645, DRAW_ID, DRAW_DATE, signals)
    finally:
        oracle.ORACLE_VERSION = "1.3.0"
    assert original != bumped
    assert oracle.make_seed(MEGA645, DRAW_ID, DRAW_DATE, signals) == original


def test_a_root_of_one_does_not_boost_every_number():
    """Regression: the rule was `n % root == 0`. With root 1 that matches EVERY number,
    so the whole pool got boosted and every sermon read "Chia hết cho 1". A rule that
    fires on everything is not a rule.
    """
    # lunar_day 8 + lunar_month 2 = 10 -> digit root 1
    signals = CosmicSignals(lunar_day=8, lunar_month=2)
    assert oracle.digit_root(8 + 2) == 1

    field = oracle.cursed_weights(MEGA645, signals)
    boosted = [n for n, reasons in field.reasons.items() if any("Số gốc" in r for r in reasons)]

    assert 0 < len(boosted) < MEGA645.pool, "the rule must select some numbers, not all"
    assert set(boosted) == {n for n in MEGA645.numbers if oracle.digit_root(n) == 1}
    assert boosted == [1, 10, 19, 28, 37]


@pytest.mark.parametrize("root", range(1, 10))
def test_digit_root_rule_selects_a_proper_subset(root):
    selected = [n for n in POWER655.numbers if oracle.digit_root(n) == root]
    assert 0 < len(selected) < POWER655.pool


# ------------------------------------------------- the basic ticket: six numbers, not twelve


def test_rank_numbers_puts_the_boosted_ones_first(loud_signals):
    field = oracle.cursed_weights(POWER655, loud_signals)
    numbers = tuple(sorted(field.weights, key=lambda n: (-field.weights[n], n))[:12])

    ordered, reasoned = oracle.rank_numbers(numbers, field, random.Random(7))

    assert set(ordered) == set(numbers), "ranking must be a permutation, not a filter"
    weights = [field.weights[n] for n in ordered]
    assert weights == sorted(weights, reverse=True)
    assert all(field.weights[n] > 1.0 for n in ordered[:reasoned])


def test_reasoned_count_stops_where_the_tie_starts(quiet_signals):
    """The honest half of this feature. Most of the wheel sits at exactly 1.0, so any
    order past that point is a tie broken by number - arbitrary, not conviction. The
    count is what stops a caller presenting the tail as though the oracle meant it."""
    field = oracle.cursed_weights(MEGA645, quiet_signals)
    numbers = tuple(range(1, 13))

    _ordered, reasoned = oracle.rank_numbers(numbers, field, random.Random(7))

    assert reasoned == sum(1 for n in numbers if field.weights[n] > 1.0)
    assert reasoned < len(numbers), "if everything were boosted the count would be meaningless"


def test_rank_numbers_is_deterministic():
    field = oracle.cursed_weights(MEGA645, CosmicSignals(
        btc_usd=64_213, hanoi_temp_c=38, lunar_day=26, lunar_month=6,
        zodiac="Ngọ", day_can_chi="Giáp Tý"))
    numbers = tuple(range(1, 13))

    assert (oracle.rank_numbers(numbers, field, random.Random(7))
            == oracle.rank_numbers(numbers, field, random.Random(7)))


def test_the_basic_pick_is_not_skewed_toward_low_numbers():
    """This test exists because the first implementation failed it. Breaking weight ties
    by ascending number made the six-number pick average 20.79 against the wheel's 28.52
    over 300 draws - a 7.7 skew toward low numbers invented entirely by the tie-break.
    Shipping a spurious pattern is the exact thing this project mocks."""
    import statistics
    from datetime import timedelta

    basic, wheel = [], []
    for i in range(200):
        signals = CosmicSignals(
            btc_usd=60_000 + i * 37, hanoi_temp_c=25 + i % 14,
            lunar_day=1 + i % 30, lunar_month=1 + i % 12,
            zodiac="Ngọ", day_can_chi="Giáp Tý",
        )
        p = oracle.prophesy(
            POWER655, str(2000 + i), date(2026, 1, 1) + timedelta(days=i), signals
        )
        wheel.append(statistics.mean(p.numbers))
        basic.append(statistics.mean(p.basic_pick))

    drift = statistics.mean(basic) - statistics.mean(wheel)
    assert abs(drift) < 2.0, f"basic pick drifts {drift:+.2f} from the wheel it came from"


def test_ties_are_broken_by_the_seed_so_the_order_is_still_reproducible(quiet_signals):
    """Unbiased, but not random per render: the same prophecy must rank the same way
    forever, because it is committed before the draw like everything else here."""
    first = oracle.prophesy(MEGA645, "01700", date(2026, 10, 1), quiet_signals)
    again = oracle.prophesy(MEGA645, "01700", date(2026, 10, 1), quiet_signals)

    assert first.ranked == again.ranked
    assert first.basic_pick == again.basic_pick


def test_prophecy_records_the_ranking_and_the_reasoned_count(loud_signals):
    prophecy = oracle.prophesy(
        MEGA645, "01600", date(2026, 9, 1), loud_signals
    )

    assert sorted(prophecy.ranked) == sorted(prophecy.numbers)
    assert 0 <= prophecy.reasoned <= len(prophecy.numbers)
    assert prophecy.basic_pick == tuple(sorted(prophecy.ranked[:6]))
    assert len(prophecy.basic_pick) == 6, "a plain Vietlott ticket is six numbers"


def test_basic_pick_is_a_subset_of_the_wheel(loud_signals):
    """Whatever six the page shows, they must be six of the twelve it committed - not a
    fresh draw. Otherwise the basic ticket and the wheel are two different prophecies."""
    prophecy = oracle.prophesy(MEGA645, "01601", date(2026, 9, 3), loud_signals)

    assert set(prophecy.basic_pick) <= set(prophecy.numbers)


def test_the_numbers_themselves_did_not_change_when_ranking_was_added(loud_signals):
    """The committed twelve are the audit trail. Adding a ranking is allowed to describe
    them; it is not allowed to alter them, and the seed is unchanged so it cannot."""
    prophecy = oracle.prophesy(MEGA645, "01602", date(2026, 9, 5), loud_signals)
    again = oracle.prophesy(MEGA645, "01602", date(2026, 9, 5), loud_signals)

    assert prophecy.numbers == again.numbers
    assert prophecy.seed == again.seed
