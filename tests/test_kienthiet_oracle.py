"""Thầy phán một vé. The ticket must be reproducible forever and cost nothing elsewhere.

The second half of this file is the blast-radius check. Adding a lottery should not move
a single mega645 or power655 prophecy, so those tests pin the shared oracle's version, its
signal fields and a concrete committed prophecy against change.
"""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru import kienthiet_oracle as ko
from tientrivutru import oracle, store
from tientrivutru.games import MEGA645, POWER655
from tientrivutru.sources.kienthiet import Board
from tientrivutru.sources.vibes import CosmicSignals
from tientrivutru.store import ProphecyConflict

DAY = date(2026, 8, 27)
BOARD_TIERS = (
    ("db", ("510332",)),
    ("g1", ("89516",)),
    ("g2", ("44895",)),
    ("g3", ("52640", "02439")),
    ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
    ("g5", ("1635",)),
    ("g6", ("9670", "9023", "3404")),
    ("g7", ("516",)),
    ("g8", ("54",)),
)


def board(day: date, province: str = "an-giang", special: str = "510332") -> Board:
    return Board(
        date=day,
        region="mn",
        province=province,
        tiers=(("db", (special,)), *BOARD_TIERS[1:]),
    )


# --- determinism --------------------------------------------------------------------


def test_same_inputs_give_the_same_ve_forever(loud_signals):
    first = ko.prophesy("an-giang", DAY, loud_signals)
    second = ko.prophesy("an-giang", DAY, loud_signals)

    assert first.ve == second.ve
    assert first.seed == second.seed


def test_a_ve_is_always_six_digits_including_leading_zeros(loud_signals):
    for day in (date(2026, 8, d) for d in range(1, 29)):
        ve = ko.prophesy("an-giang", day, loud_signals).ve
        assert len(ve) == 6
        assert ve.isdigit()


def test_the_province_changes_the_seed(loud_signals):
    here = ko.prophesy("an-giang", DAY, loud_signals)
    there = ko.prophesy("tay-ninh", DAY, loud_signals)

    assert here.seed != there.seed


def test_the_date_changes_the_seed(loud_signals):
    assert (
        ko.prophesy("an-giang", DAY, loud_signals).seed
        != ko.prophesy("an-giang", date(2026, 9, 3), loud_signals).seed
    )


def test_karma_changes_the_seed(loud_signals):
    plain = ko.prophesy("an-giang", DAY, loud_signals)
    burdened = ko.prophesy("an-giang", DAY, loud_signals, karma="510332")

    assert plain.seed != burdened.seed
    assert burdened.karma == "510332"


def test_silent_signals_still_produce_a_ve(quiet_signals):
    """A dead price API must never stop the đài from being phán."""
    assert len(ko.prophesy("an-giang", DAY, quiet_signals).ve) == 6


def test_the_version_is_part_of_the_seed(loud_signals, monkeypatch):
    before = ko.prophesy("an-giang", DAY, loud_signals).seed
    monkeypatch.setattr(ko, "KIENTHIET_ORACLE_VERSION", "9.9.9")
    assert ko.make_seed("an-giang", DAY, loud_signals, None) != before


def test_an_unknown_dai_is_refused(loud_signals):
    with pytest.raises(KeyError, match="quang-đông"):
        ko.prophesy("quang-đông", DAY, loud_signals)


# --- the weighting ------------------------------------------------------------------


def test_no_digit_is_ever_impossible(loud_signals):
    field = ko.cursed_digits(loud_signals, karma="000000")
    for column in field.weights:
        assert set(column) == set(range(10))
        assert all(weight > 0 for weight in column.values())


def test_karma_only_punishes_the_position_the_digit_stood_in(loud_signals):
    plain = ko.cursed_digits(loud_signals, karma=None)
    burdened = ko.cursed_digits(loud_signals, karma="510332")

    assert burdened.weights[0][5] < plain.weights[0][5]
    assert burdened.weights[1][5] == plain.weights[1][5]


def test_every_boost_explains_itself(loud_signals):
    field = ko.cursed_digits(loud_signals, karma="510332")
    assert len(field.reasons) >= 5
    assert any("510332" in reason for reason in field.reasons)


def test_the_sermon_never_promises_a_win(loud_signals):
    forbidden = ("chắc chắn trúng", "cam kết", "bao trúng", "trúng 100")
    for day in (date(2026, 8, d) for d in range(1, 29)):
        sermon = ko.prophesy("an-giang", day, loud_signals).sermon.lower()
        assert not any(word in sermon for word in forbidden)


# --- karma lookup -------------------------------------------------------------------


def test_karma_is_the_dai_s_own_previous_special():
    boards = [
        board(date(2026, 8, 13), "an-giang", "111111"),
        board(date(2026, 8, 20), "an-giang", "222222"),
        board(date(2026, 8, 21), "tay-ninh", "999999"),
    ]
    assert ko.latest_special_before(boards, "an-giang", DAY) == "222222"


def test_karma_ignores_boards_from_the_future():
    boards = [board(date(2026, 9, 3), "an-giang", "333333")]
    assert ko.latest_special_before(boards, "an-giang", DAY) is None


def test_a_dai_with_no_history_has_no_karma():
    assert ko.latest_special_before([], "an-giang", DAY) is None


# --- mien bac is not prophesiable ---------------------------------------------------


def test_mien_bac_is_refused_with_a_reason(loud_signals):
    with pytest.raises(ValueError, match="ký hiệu"):
        ko.prophesy("mien-bac", DAY, loud_signals)


# --- storage ------------------------------------------------------------------------


def test_a_ve_round_trips_through_storage(loud_signals):
    committed = ko.prophesy("an-giang", DAY, loud_signals, karma="510332")
    store.append_ve(committed)

    (restored,) = store.read_ve("an-giang")
    assert restored == committed


def test_a_ve_cannot_be_written_twice(loud_signals):
    store.append_ve(ko.prophesy("an-giang", DAY, loud_signals))
    with pytest.raises(ProphecyConflict, match="append-only"):
        store.append_ve(ko.prophesy("an-giang", DAY, loud_signals))


def test_a_settled_day_cannot_be_prophesied(loud_signals):
    store.write_boards("mn", [board(DAY)])
    with pytest.raises(ProphecyConflict, match="ăn gian"):
        store.append_ve(ko.prophesy("an-giang", DAY, loud_signals))


def test_two_dai_on_the_same_day_are_both_welcome(loud_signals):
    store.append_ve(ko.prophesy("an-giang", DAY, loud_signals))
    store.append_ve(ko.prophesy("tay-ninh", DAY, loud_signals))

    assert len(store.read_ve()) == 2


# --- blast radius on the existing games ---------------------------------------------


def test_the_shared_oracle_version_did_not_move():
    """Bumping it would rewrite every future mega645 and power655 prophecy."""
    assert oracle.ORACLE_VERSION == "1.3.0"


def test_cosmic_signals_gained_no_field_for_kien_thiet():
    assert set(CosmicSignals().as_dict()) == {
        "btc_usd",
        "hanoi_temp_c",
        "lunar_day",
        "lunar_month",
        "zodiac",
        "day_can_chi",
        "xsmb_special",
    }


@pytest.mark.parametrize("spec", (MEGA645, POWER655), ids=lambda s: s.key)
def test_existing_game_prophecies_are_unchanged(spec, loud_signals):
    """Recorded from oracle.py, games.py, models.py and vibes.py at the commit that
    added kiến thiết, none of which this change touches. If these move, something in the
    shared oracle moved with them and every future prophecy moved too.
    """
    expected = {
        "mega645": ("bd5bc4b3", (3, 4, 5, 16, 18, 20, 31, 32, 40, 41, 42, 44)),
        "power655": ("fb217e1d", (7, 8, 9, 16, 20, 26, 30, 32, 35, 36, 48, 51)),
    }[spec.key]
    prophecy = oracle.prophesy(spec, "01600", date(2026, 9, 1), loud_signals)

    assert prophecy.seed[:8] == expected[0]
    assert prophecy.numbers == expected[1]
