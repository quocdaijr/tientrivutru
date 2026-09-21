"""Boundary validation for the upstream mirror.

Fixtures below are real rows copied from the live mirror on 2026-08-19.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from tientrivutru.games import MEGA645, POWER655
from tientrivutru.models import Draw
from tientrivutru.sources import vietlott_mirror as mirror

# Real upstream rows. Note the 7th number in Power 6/55: it is NOT part of the sorted six.
POWER655_ROW = {"date": "2017-08-01", "id": "00001", "result": [5, 10, 14, 23, 24, 38, 35]}
POWER655_LATEST = {"date": "2026-08-18", "id": "01386", "result": [3, 15, 18, 38, 41, 48, 30]}
MEGA645_ROW = {"date": "2017-10-25", "id": "00198", "result": [12, 17, 23, 25, 34, 38]}


def test_bonus_is_seventh_number():
    """The verified invariant: first six are the sorted main set, the seventh is the bonus."""
    draw = mirror.parse_row(POWER655, POWER655_ROW)

    assert draw.main == (5, 10, 14, 23, 24, 38)
    assert draw.bonus == 35
    assert list(draw.main) == sorted(draw.main)
    # The bonus is deliberately not the largest number - proof it is not just a tail element.
    assert draw.bonus < max(draw.main)


def test_bonus_excluded_from_main_even_when_larger():
    draw = mirror.parse_row(POWER655, POWER655_LATEST)
    assert draw.main == (3, 15, 18, 38, 41, 48)
    assert draw.bonus == 30


def test_mega645_has_no_bonus():
    draw = mirror.parse_row(MEGA645, MEGA645_ROW)
    assert draw.main == (12, 17, 23, 25, 34, 38)
    assert draw.bonus is None
    assert draw.date == date(2017, 10, 25)


def test_draw_id_is_zero_padded():
    assert mirror.parse_row(MEGA645, {**MEGA645_ROW, "id": 198}).draw_id == "00198"


def test_parse_row_rejects_wrong_length():
    """A 6-number row for Power 6/55 means the upstream format changed - fail loudly."""
    with pytest.raises(ValueError, match="expected 7 numbers"):
        mirror.parse_row(POWER655, {**POWER655_ROW, "result": [5, 10, 14, 23, 24, 38]})

    with pytest.raises(ValueError, match="expected 6 numbers"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": [1, 2, 3, 4, 5, 6, 7]})


def test_parse_row_rejects_out_of_range():
    with pytest.raises(ValueError, match="outside 1..45"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": [12, 17, 23, 25, 34, 46]})

    with pytest.raises(ValueError, match="outside 1..45"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": [0, 17, 23, 25, 34, 38]})


def test_parse_row_rejects_unsorted_main():
    """Upstream has always been sorted; if that changes we want to know, not guess."""
    with pytest.raises(ValueError, match="sorted ascending"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": [38, 17, 23, 25, 34, 12]})


def test_parse_row_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicates"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": [12, 12, 23, 25, 34, 38]})


def test_parse_row_rejects_bonus_duplicating_main():
    with pytest.raises(ValueError, match="duplicates a main number"):
        mirror.parse_row(POWER655, {**POWER655_ROW, "result": [5, 10, 14, 23, 24, 38, 24]})


@pytest.mark.parametrize("missing", ["date", "id", "result"])
def test_parse_row_rejects_missing_fields(missing):
    row = {k: v for k, v in MEGA645_ROW.items() if k != missing}
    with pytest.raises(ValueError, match=f"missing '{missing}'"):
        mirror.parse_row(MEGA645, row)


def test_parse_row_rejects_non_list_result():
    with pytest.raises(TypeError, match="must be a list"):
        mirror.parse_row(MEGA645, {**MEGA645_ROW, "result": "12,17,23,25,34,38"})


def test_ingest_maps_power645_filename_to_mega645_game():
    """Upstream names the Mega 6/45 file `power645.jsonl`. That bug stops at the spec."""
    assert MEGA645.mirror_filename == "power645.jsonl"
    assert mirror.mirror_url(MEGA645).endswith("/power645.jsonl")

    draw = mirror.parse_row(MEGA645, MEGA645_ROW)
    assert draw.game == "mega645"
    assert "power645" not in draw.game


def test_parse_jsonl_sorts_and_skips_blank_lines():
    payload = "\n".join(
        [json.dumps(MEGA645_ROW), "", json.dumps({**MEGA645_ROW, "id": "00197"}), "  "]
    )
    draws = mirror.parse_jsonl(MEGA645, payload)
    assert [d.draw_id for d in draws] == ["00197", "00198"]


def test_parse_jsonl_reports_bad_line_number():
    payload = json.dumps(MEGA645_ROW) + "\n{ not json"
    with pytest.raises(ValueError, match="line 2"):
        mirror.parse_jsonl(MEGA645, payload)


def _mega_draw(draw_id: int, day: date) -> Draw:
    return Draw(
        game="mega645",
        draw_id=str(draw_id),
        date=day,
        main=(1, 2, 3, 4, 5, 6),
        source="test",
    )


def test_find_gaps_detects_missing_draw():
    draws = [_mega_draw(i, date(2026, 8, 1)) for i in (1, 2, 4, 5)]
    assert mirror.find_gaps(draws) == ("00003",)


def test_find_gaps_empty_when_contiguous():
    draws = [_mega_draw(i, date(2026, 8, 1)) for i in (1, 2, 3)]
    assert mirror.find_gaps(draws) == ()


def test_find_missing_dates_catches_upstream_lag():
    """Reproduces the real defect: Mega 6/45 skipped Sunday 2026-08-16."""
    draws = [
        _mega_draw(1547, date(2026, 8, 9)),
        _mega_draw(1548, date(2026, 8, 12)),
        _mega_draw(1549, date(2026, 8, 14)),
    ]
    missing = mirror.find_missing_dates(MEGA645, draws, date(2026, 8, 17))

    assert date(2026, 8, 16) in missing
    assert all(d.weekday() in MEGA645.draw_weekdays for d in missing)


def test_find_missing_dates_quiet_when_current():
    draws = [_mega_draw(1549, date(2026, 8, 14))]
    assert mirror.find_missing_dates(MEGA645, draws, date(2026, 8, 15)) == ()


def test_summarise_reports_counts_and_problems():
    draws = [_mega_draw(i, date(2026, 8, 1)) for i in (1, 3)]
    report = mirror.summarise(MEGA645, draws, date(2026, 8, 1))

    assert report["game"] == "mega645"
    assert report["count"] == 2
    assert report["gap_ids"] == ["00002"]
