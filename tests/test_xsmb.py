"""XSMB source. It deliberately does not use the Draw model - these tests pin why."""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru import store
from tientrivutru.sources import xsmb

HEADER = (
    "date,special,prize1,prize2_1,prize2_2,prize3_1,prize3_2,prize3_3,prize3_4,prize3_5,"
    "prize3_6,prize4_1,prize4_2,prize4_3,prize4_4,prize5_1,prize5_2,prize5_3,prize5_4,"
    "prize5_5,prize5_6,prize6_1,prize6_2,prize6_3,prize7_1,prize7_2,prize7_3,prize7_4"
)
# Real rows. 2026-08-17 is notable: 14 appears twice and 0 appears twice.
ROW_WITH_REPEATS = (
    "2026-08-17,39,0,12,54,60,17,41,83,90,35,55,14,74,14,"
    "27,45,26,0,48,70,44,87,80,89,61,76,71"
)
ROW_LATEST = (
    "2026-08-18,83,49,65,66,33,29,77,51,69,53,85,35,42,86,"
    "62,16,76,99,34,74,73,82,54,51,4,92,13"
)
CSV = f"{HEADER}\n{ROW_WITH_REPEATS}\n{ROW_LATEST}\n"


def test_parses_real_rows():
    draws = xsmb.parse_csv(CSV)

    assert len(draws) == 2
    assert draws[0].date == date(2026, 8, 17)
    assert draws[0].special == 39
    assert len(draws[0].prizes) == xsmb.PRIZE_SLOTS == 27


def test_zero_is_a_legal_value():
    """00 is a real XSMB outcome, which is exactly why Draw's 1..pool rule cannot apply."""
    draws = xsmb.parse_csv(CSV)
    assert 0 in draws[0].prizes


def test_repeats_within_one_draw_are_legal():
    """Draw forbids duplicates; XSMB draws them routinely."""
    prizes = xsmb.parse_csv(CSV)[0].prizes
    assert prizes.count(14) == 2
    assert prizes.count(0) == 2
    assert len(set(prizes)) < len(prizes)


def test_digit_space_is_one_hundred_values():
    assert xsmb.DIGIT_SPACE == 100


def test_rejects_value_outside_digit_space():
    with pytest.raises(ValueError, match="outside 00..99"):
        xsmb.XsmbDraw(date=date(2026, 8, 17), special=100, prizes=(100,) + (1,) * 26)


def test_rejects_wrong_slot_count():
    with pytest.raises(ValueError, match="expected 27 prize slots"):
        xsmb.XsmbDraw(date=date(2026, 8, 17), special=1, prizes=(1, 2, 3))


def test_special_must_be_the_first_slot():
    with pytest.raises(ValueError, match="must be the first prize slot"):
        xsmb.XsmbDraw(date=date(2026, 8, 17), special=7, prizes=(1,) * 27)


def test_rejects_row_with_missing_values():
    broken = f"{HEADER}\n2026-08-17,39,0,12\n"
    with pytest.raises(ValueError, match="expected 27 prize values"):
        xsmb.parse_csv(broken)


def test_rejects_empty_csv():
    with pytest.raises(ValueError, match="empty"):
        xsmb.parse_csv(f"{HEADER}\n")


def test_draws_are_sorted_by_date():
    reversed_csv = f"{HEADER}\n{ROW_LATEST}\n{ROW_WITH_REPEATS}\n"
    draws = xsmb.parse_csv(reversed_csv)
    assert draws[0].date < draws[1].date


def test_frequency_covers_every_value_and_sums_to_observations():
    draws = xsmb.parse_csv(CSV)
    freq = xsmb.frequency(draws)

    assert len(freq) == 100
    assert set(freq) == set(range(100))
    assert sum(freq.values()) == len(draws) * xsmb.PRIZE_SLOTS


def test_chi_square_uses_ninety_nine_degrees_of_freedom():
    result = xsmb.chi_square_uniform(xsmb.parse_csv(CSV))
    assert result.degrees_of_freedom == 99
    assert result.observations == 54


def test_chi_square_requires_data():
    with pytest.raises(ValueError, match="no draws"):
        xsmb.chi_square_uniform([])


def test_blatant_bias_is_detected():
    rigged = [xsmb.XsmbDraw(date=date(2020, 1, 1), special=7, prizes=(7,) * 27)]
    result = xsmb.chi_square_uniform(rigged * 1)
    assert result.rejects_uniform


def test_latest_special_takes_the_newest_date():
    assert xsmb.latest_special(xsmb.parse_csv(CSV)) == 83
    assert xsmb.latest_special([]) is None


def test_store_round_trip():
    draws = xsmb.parse_csv(CSV)
    assert store.write_xsmb(draws) == 2
    assert store.read_xsmb() == draws
    assert store.latest_xsmb_special() == 83


def test_store_rejects_duplicate_dates():
    draws = xsmb.parse_csv(CSV)
    with pytest.raises(ValueError, match="duplicate XSMB dates"):
        store.write_xsmb([draws[0], draws[0]])


def test_missing_xsmb_file_degrades_to_none():
    """A missing XSMB file must silence the signal, not break the oracle."""
    assert store.read_xsmb() == ()
    assert store.latest_xsmb_special() is None
