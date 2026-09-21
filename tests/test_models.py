"""Record validation and the game specs themselves."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import ALL_GAMES, make_draw, make_prophecy
from tientrivutru.games import (
    MEGA645,
    POWER655,
    WHEEL_SIZE,
    draw_days_between,
    get_game,
    is_draw_day,
    next_draw_date,
)
from tientrivutru.models import Draw, Prophecy, normalise_draw_id


@pytest.mark.parametrize("spec", ALL_GAMES, ids=lambda s: s.key)
def test_spec_shape(spec):
    assert spec.pick == 6
    assert spec.unit_price_vnd == 10_000
    assert len(spec.draw_weekdays) == 3
    assert spec.result_length == 6 + (1 if spec.has_bonus else 0)
    assert list(spec.numbers) == list(range(1, spec.pool + 1))


def test_only_power655_has_a_bonus():
    assert POWER655.has_bonus
    assert not MEGA645.has_bonus


def test_prize_tiers_match_published_structure():
    assert POWER655.prizes == {"first": 40_000_000, "second": 500_000, "third": 50_000}
    assert MEGA645.prizes == {"first": 10_000_000, "second": 300_000, "third": 30_000}
    assert POWER655.jackpot_floor["jackpot2"] == 3_000_000_000
    assert MEGA645.jackpot_floor["jackpot"] == 12_000_000_000


def test_draw_schedules_are_the_published_ones():
    """Power 6/55 draws Tue/Thu/Sat; Mega 6/45 draws Wed/Fri/Sun."""
    assert is_draw_day(POWER655, date(2026, 8, 18))  # Tuesday
    assert not is_draw_day(POWER655, date(2026, 8, 19))  # Wednesday
    assert is_draw_day(MEGA645, date(2026, 8, 19))
    assert not is_draw_day(MEGA645, date(2026, 8, 18))


def test_next_draw_date():
    wednesday = date(2026, 8, 19)
    assert next_draw_date(MEGA645, wednesday) == wednesday
    assert next_draw_date(MEGA645, wednesday, inclusive=False) == date(2026, 8, 21)
    assert next_draw_date(POWER655, wednesday) == date(2026, 8, 20)


def test_draw_days_between_is_inclusive():
    days = draw_days_between(MEGA645, date(2026, 8, 14), date(2026, 8, 19))
    assert days == (date(2026, 8, 14), date(2026, 8, 16), date(2026, 8, 19))
    assert draw_days_between(MEGA645, date(2026, 8, 19), date(2026, 8, 14)) == ()


def test_expected_hits():
    assert MEGA645.expected_hits() == pytest.approx(6 * 12 / 45)
    assert POWER655.expected_hits() == pytest.approx(6 * 12 / 55)


def test_get_game_rejects_unknown():
    with pytest.raises(KeyError, match="Unknown game"):
        get_game("vietlott_keno")


@pytest.mark.parametrize("raw,expected", [("1", "00001"), (1386, "01386"), ("01386", "01386")])
def test_normalise_draw_id(raw, expected):
    assert normalise_draw_id(raw) == expected


def test_normalise_draw_id_rejects_non_digits():
    with pytest.raises(ValueError, match="must be digits"):
        normalise_draw_id("ky-1386")


def test_draw_requires_bonus_for_power655():
    with pytest.raises(ValueError, match="bonus number is required"):
        Draw(game="power655", draw_id="1", date=date(2026, 8, 18), main=(1, 2, 3, 4, 5, 6))


def test_draw_rejects_bonus_for_mega645():
    with pytest.raises(ValueError, match="no bonus number"):
        Draw(
            game="mega645",
            draw_id="1",
            date=date(2026, 8, 19),
            main=(1, 2, 3, 4, 5, 6),
            bonus=7,
        )


def test_draw_rejects_wrong_main_count():
    with pytest.raises(ValueError, match="expected 6 main numbers"):
        Draw(game="mega645", draw_id="1", date=date(2026, 8, 19), main=(1, 2, 3))


def test_draw_rejects_bool_disguised_as_int():
    with pytest.raises(TypeError, match="must contain ints"):
        Draw(game="mega645", draw_id="1", date=date(2026, 8, 19), main=(True, 2, 3, 4, 5, 6))


def test_draw_is_immutable():
    draw = make_draw(MEGA645, 1)
    with pytest.raises(AttributeError):
        draw.main = (9, 9, 9, 9, 9, 9)


def test_draw_dict_round_trip():
    original = make_draw(POWER655, 1386, main=(3, 15, 18, 38, 41, 48), bonus=30)
    assert Draw.from_dict(original.to_dict()) == original


def test_prophecy_requires_exactly_twelve_numbers():
    with pytest.raises(ValueError, match=f"exactly {WHEEL_SIZE} numbers"):
        make_prophecy(MEGA645, 1, numbers=tuple(range(1, 12)))


def test_prophecy_rejects_out_of_range_number():
    with pytest.raises(ValueError, match="outside 1..45"):
        make_prophecy(MEGA645, 1, numbers=(*range(1, 12), 46))


def test_prophecy_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicates"):
        make_prophecy(MEGA645, 1, numbers=(1, 1, *range(2, 12)))


def test_prophecy_requires_a_seed():
    with pytest.raises(ValueError, match="seed must not be empty"):
        Prophecy(
            game="mega645",
            draw_id="1",
            draw_date=date(2026, 8, 19),
            numbers=tuple(range(1, 13)),
            seed="",
            signals={},
            sermon={},
            oracle_version="1.0.0",
            created_at=__import__("tientrivutru.models", fromlist=["utc_now"]).utc_now(),
        )


def test_prophecy_signals_are_read_only():
    prophecy = make_prophecy(MEGA645, 1)
    with pytest.raises(TypeError):
        prophecy.signals["btc_usd"] = 1


def test_prophecy_dict_round_trip():
    original = make_prophecy(MEGA645, 1550)
    assert Prophecy.from_dict(original.to_dict()).numbers == original.numbers
