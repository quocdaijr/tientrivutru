"""Xổ số kiến thiết: one prize board per đài per day, three regions.

Markup fixtures are byte-for-byte from minhngoc.net.vn, trimmed to the result table.
They were chosen to pin the three things that break a naive parser:

  * An Giang 2026-08-20 has SEVEN fourth-prize numbers. The GitHub mirror everyone
    reaches for first (t-k-minh/XSMienNam-Analysis) stores only four and silently
    drops 32217, 57371 and 15096.
  * Phú Yên 2010-01-04 has a FIVE-digit special. Miền Nam / Miền Trung only moved to
    six digits around 2011, so asserting six breaks every board before that.
  * Miền Bắc 2005-10-01 is a different board entirely: 27 slots, no eighth prize.
"""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru.sources import kienthiet as kt

# --- minhngoc /getkqxs/an-giang/20-08-2026.js, result table only ---------------------
AN_GIANG_2026 = (
    '<table class="bkqtinhmiennam_mini" width="100%"><tbody>'
    '<tr><td nowrap class="thu">Thứ năm</td>'
    '<td class="ngay">Loại v&eacute;: AG-8K3</td></tr>'
    '<tr><td nowrap class="giaidbl"> Giải ĐB</td><td class="giaidb">510332</td></tr>'
    '<tr><td nowrap class="giai1l">Giải nhất</td><td class="giai1">89516</td></tr>'
    '<tr><td nowrap class="giai2l">Giải nh&igrave;</td><td class="giai2">44895</td></tr>'
    '<tr><td nowrap class="giai3l">Giải ba</td>'
    '<td class="giai3">52640 - 02439</td></tr>'
    '<tr><td nowrap class="giai4l">Giải tư</td>'
    '<td class="giai4">90111 - 32541 - 20491 - 71417 - 32217 - 57371 - 15096</td></tr>'
    '<tr><td nowrap class="giai5l">Giải năm</td><td class="giai5">1635</td></tr>'
    '<tr><td nowrap class="giai6l">Giải s&aacute;u</td>'
    '<td class="giai6">9670 - 9023 - 3404</td></tr>'
    '<tr><td nowrap class="giai7l">Giải bảy</td><td class="giai7">516</td></tr>'
    '<tr><td nowrap class="giai8l">Giải tám</td><td class="giai8">54</td></tr>'
    "</tbody></table>"
)

# --- minhngoc /getkqxs/phu-yen/04-01-2010.js: the five-digit-special era -------------
PHU_YEN_2010 = (
    '<table class="bkqtinhmiennam_mini" width="100%"><tbody>'
    '<tr><td nowrap class="thu">Thứ hai</td><td class="ngay">Ngày: 04/01/2010</td></tr>'
    '<tr><td nowrap class="giaidbl"> Giải ĐB</td><td class="giaidb">06278</td></tr>'
    '<tr><td nowrap class="giai1l">Giải nhất</td><td class="giai1">47799</td></tr>'
    '<tr><td nowrap class="giai2l">Giải nh&igrave;</td><td class="giai2">38708</td></tr>'
    '<tr><td nowrap class="giai3l">Giải ba</td>'
    '<td class="giai3">00869 - 78166</td></tr>'
    '<tr><td nowrap class="giai4l">Giải tư</td>'
    '<td class="giai4">81235 - 28759 - 45957 - 05798 - 66327 - 06512 - 01635</td></tr>'
    '<tr><td nowrap class="giai5l">Giải năm</td><td class="giai5">5732</td></tr>'
    '<tr><td nowrap class="giai6l">Giải s&aacute;u</td>'
    '<td class="giai6">4741 - 6924 - 5321</td></tr>'
    '<tr><td nowrap class="giai7l">Giải bảy</td><td class="giai7">604</td></tr>'
    '<tr><td nowrap class="giai8l">Giải tám</td><td class="giai8">14</td></tr>'
    "</tbody></table>"
)

# --- minhngoc /getkqxs/mien-bac/01-10-2005.js: the oldest row we hold ----------------
# This is the same draw as the first line of data/xsmb.jsonl, which is why it is here:
# tests/test_kienthiet_migration.py replays the whole file against boards like this one.
MIEN_BAC_2005 = (
    '<table class="bkqtinhmienbac_mini" width="100%"><tbody>'
    '<tr><td class="thu" >Thứ bảy</td><td class="ngay">Ng&agrave;y: 01/10/2005 </td></tr>'
    '<tr><td nowrap class="giaidbl">Giải ĐB</td><td class="giaidb">34584</td></tr>'
    '<tr><td nowrap class="giai1l">Giải nhất</td><td class="giai1">16876</td></tr>'
    '<tr><td nowrap class="giai2l">Giải nh&igrave;</td>'
    '<td class="giai2">34885 - 65037</td></tr>'
    '<tr><td nowrap class="giai3l">Giải ba</td>'
    '<td class="giai3">44442 - 95464 - 14795 - 94080 - 18983 - 22006</td></tr>'
    '<tr><td nowrap class="giai4l">Giải tư</td>'
    '<td class="giai4">4979 - 4293 - 2502 - 4395</td></tr>'
    '<tr><td nowrap class="giai5l">Giải năm</td>'
    '<td class="giai5">4240 - 3439 - 3988 - 5912 - 3636 - 5423</td></tr>'
    '<tr><td nowrap class="giai6l">Giải s&aacute;u</td>'
    '<td class="giai6">729 - 272 - 278</td></tr>'
    '<tr><td nowrap class="giai7l">Giải bảy</td>'
    '<td class="giai7">12 - 25 - 78 - 70</td></tr>'
    "</tbody></table>"
)


def an_giang() -> kt.Board:
    return kt.parse_board(AN_GIANG_2026, province="an-giang", on=date(2026, 8, 20))


def mien_bac() -> kt.Board:
    return kt.parse_board(MIEN_BAC_2005, province="mien-bac", on=date(2005, 10, 1))


# --- registry -----------------------------------------------------------------------


def test_every_province_belongs_to_a_known_region():
    for slug, province in kt.PROVINCES.items():
        assert province.region in kt.REGIONS, slug


def test_the_three_regions_have_the_board_sizes_the_rules_say():
    assert kt.REGIONS["mn"].slots == 18
    assert kt.REGIONS["mt"].slots == 18
    assert kt.REGIONS["mb"].slots == 27


def test_only_the_south_and_centre_are_prophesiable():
    """Miền Bắc tickets carry a ký hiệu and the prize table changed twice. No ROI, no phán."""
    assert kt.REGIONS["mn"].prophesiable
    assert kt.REGIONS["mt"].prophesiable
    assert not kt.REGIONS["mb"].prophesiable


def test_south_and_centre_hold_twenty_one_and_fourteen_dai():
    south = [s for s, p in kt.PROVINCES.items() if p.region == "mn"]
    centre = [s for s, p in kt.PROVINCES.items() if p.region == "mt"]
    assert len(south) == 21
    assert len(centre) == 14


# --- parsing ------------------------------------------------------------------------


def test_parses_a_real_mn_board_with_seven_fourth_prizes():
    """The exact numbers the popular GitHub mirror truncates away."""
    board = an_giang()

    assert board.region == "mn"
    assert board.province == "an-giang"
    assert board.date == date(2026, 8, 20)
    assert board.special == "510332"
    assert dict(board.tiers)["g4"] == (
        "90111",
        "32541",
        "20491",
        "71417",
        "32217",
        "57371",
        "15096",
    )
    assert len(board.numbers) == 18


def test_parses_a_real_mb_board_with_twenty_seven_slots():
    board = mien_bac()

    assert board.region == "mb"
    assert board.special == "34584"
    assert len(board.numbers) == 27
    assert dict(board.tiers)["g7"] == ("12", "25", "78", "70")
    assert "g8" not in dict(board.tiers)


def test_five_digit_special_before_2011_is_legal():
    """Miền Nam / Miền Trung specials were five digits until roughly 2011."""
    board = kt.parse_board(PHU_YEN_2010, province="phu-yen", on=date(2010, 1, 4))

    assert board.region == "mt"
    assert board.special == "06278"
    assert len(board.numbers) == 18


def test_leading_zeros_survive_parsing():
    """02439 must never become 2439. The whole ticket match depends on width."""
    assert "02439" in an_giang().numbers


def test_reads_the_ticket_type_when_the_page_carries_one():
    assert an_giang().ticket_type == "AG-8K3"
    assert mien_bac().ticket_type is None


def test_rejects_an_unknown_province():
    with pytest.raises(KeyError, match="quang-đông"):
        kt.parse_board(AN_GIANG_2026, province="quang-đông", on=date(2026, 8, 20))


def test_rejects_a_board_missing_a_tier():
    broken = AN_GIANG_2026.replace('<td class="giai7">516</td>', "<td></td>")
    with pytest.raises(ValueError, match="g7"):
        kt.parse_board(broken, province="an-giang", on=date(2026, 8, 20))


def test_rejects_a_truncated_fourth_prize():
    """Exactly the shape of the mirror's bug, refused at the boundary."""
    broken = AN_GIANG_2026.replace(" - 32217 - 57371 - 15096", "")
    with pytest.raises(ValueError, match="g4"):
        kt.parse_board(broken, province="an-giang", on=date(2026, 8, 20))


def test_rejects_a_number_of_the_wrong_width():
    broken = AN_GIANG_2026.replace(">516<", ">5160<")
    with pytest.raises(ValueError, match="g7"):
        kt.parse_board(broken, province="an-giang", on=date(2026, 8, 20))


def test_label_cells_are_not_mistaken_for_values():
    """`giaidbl` is the label column; only `giaidb` carries the number."""
    assert "giaidbl" in AN_GIANG_2026
    assert an_giang().special == "510332"


# --- derived views ------------------------------------------------------------------


def test_tails_are_the_last_two_digits_of_every_slot():
    board = an_giang()

    assert len(board.tails) == 18
    assert board.tails[0] == 32  # 510332
    assert board.tails[-1] == 54  # giải tám, already two digits


def test_zero_is_a_legal_tail():
    """00 is a number. Anything that treats a falsy tail as missing is broken."""
    board = kt.parse_board(
        AN_GIANG_2026.replace(">54<", ">00<"), province="an-giang", on=date(2026, 8, 20)
    )
    assert 0 in board.tails


def test_repeats_within_one_board_are_legal():
    board = kt.parse_board(
        AN_GIANG_2026.replace(">1635<", ">9670<"), province="an-giang", on=date(2026, 8, 20)
    )
    assert board.tails.count(70) == 2


def test_numbers_follow_the_printed_board_order():
    assert an_giang().numbers[0] == "510332"
    assert an_giang().numbers[1] == "89516"
    assert an_giang().numbers[-1] == "54"


# --- serialisation ------------------------------------------------------------------


def test_round_trips_through_a_dict():
    board = an_giang()
    assert kt.Board.from_dict(board.to_dict()) == board


def test_serialised_form_keeps_numbers_as_strings():
    payload = an_giang().to_dict()
    assert payload["tiers"][3] == ["g3", ["52640", "02439"]]
    assert payload["province"] == "an-giang"
    assert payload["source"] == kt.SOURCE_LABEL


# --- urls ---------------------------------------------------------------------------


def test_board_url_uses_the_vietnamese_date_order():
    assert kt.board_url("an-giang", date(2026, 8, 20)).endswith("/an-giang/20-08-2026.js")


def test_board_url_without_a_date_asks_for_the_latest():
    assert kt.board_url("an-giang", None).endswith("/an-giang.js")


def test_week_url_is_per_region():
    assert kt.week_url("mn", date(2026, 8, 20)).endswith("/mien-nam/20-08-2026.html")


# --- statistics ---------------------------------------------------------------------


def test_frequency_covers_every_tail_and_sums_to_observations():
    counts = kt.frequency([an_giang(), mien_bac()])

    assert set(counts) == set(range(100))
    assert sum(counts.values()) == 18 + 27


def test_chi_square_uses_ninety_nine_degrees_of_freedom():
    result = kt.chi_square_uniform([an_giang()] * 40)
    assert result.degrees_of_freedom == 99


def test_chi_square_requires_data():
    with pytest.raises(ValueError, match="no boards"):
        kt.chi_square_uniform([])


def test_blatant_bias_is_detected():
    """Forty identical boards is not a fair lottery, and the test must say so."""
    assert kt.chi_square_uniform([an_giang()] * 40).rejects_uniform


def test_summarise_reports_the_span_and_the_dai_count():
    report = kt.summarise([an_giang(), mien_bac()])

    assert report["count"] == 2
    assert report["first_date"] == "2005-10-01"
    assert report["last_date"] == "2026-08-20"
    assert report["observations"] == 45
    assert report["provinces"] == 2


# --- weekly pages -------------------------------------------------------------------
# The backfill path: one request returns a whole week of a region. The scaffolding below
# is the real minhngoc structure - `box_kqxs` per day, `rightcl` per đài, the province
# named only by its link - wrapped around the same board tables used above.

WEEK_MN = (
    '<div class="box_kqxs"><span class="tngay">Ngày: '
    '<a href="/ket-qua-xo-so/20-08-2026.html">20/08/2026</a></span>'
    '<table class="rightcl"><tbody><tr><td class="tinh">'
    '<a href="/xo-so-mien-nam/an-giang.html" title="Xổ Số An Giang">An Giang</a></td></tr>'
    f"{AN_GIANG_2026}</tbody></table>"
    '<table class="rightcl"><tbody><tr><td class="tinh">'
    '<a href="/xo-so-mien-trung/phu-yen.html" title="Xổ Số Phú Yên">Phú Yên</a></td></tr>'
    f"{PHU_YEN_2010}</tbody></table>"
    "</div>"
    '<div class="box_kqxs"><span class="tngay">Ngày: '
    '<a href="/ket-qua-xo-so/13-08-2026.html">13/08/2026</a></span>'
    '<table class="rightcl"><tbody><tr><td class="tinh">'
    '<a href="/xo-so-mien-nam/an-giang.html" title="Xổ Số An Giang">An Giang</a></td></tr>'
    f"{AN_GIANG_2026}</tbody></table></div>"
)

# Miền Bắc has one đài, so its day blocks carry no province link at all.
WEEK_MB = (
    '<div class="box_kqxs"><span class="tngay">Ngày: '
    '<a href="/ket-qua-xo-so/01-10-2005.html">01/10/2005</a></span>'
    f"{MIEN_BAC_2005}</div>"
)


def test_week_page_yields_one_board_per_dai_per_day():
    boards = kt.parse_region_week(WEEK_MN, region="mn")

    assert [(b.date.isoformat(), b.province) for b in boards] == [
        ("2026-08-13", "an-giang"),
        ("2026-08-20", "an-giang"),
    ]


def test_week_page_ignores_dai_from_a_different_region():
    """The southern and central pages cross-link each other. Only ours is ours."""
    assert kt.parse_region_week(WEEK_MN, region="mt") == (
        kt.parse_board(PHU_YEN_2010, province="phu-yen", on=date(2026, 8, 20)),
    )


def test_week_page_dates_come_from_the_day_block_not_the_board():
    """Phú Yên's own table says 04/01/2010; the page it is embedded in says otherwise."""
    assert "04/01/2010" in PHU_YEN_2010
    assert kt.parse_region_week(WEEK_MN, region="mt")[0].date == date(2026, 8, 20)


def test_single_dai_region_needs_no_province_link():
    boards = kt.parse_region_week(WEEK_MB, region="mb")

    assert len(boards) == 1
    assert boards[0].province == "mien-bac"
    assert boards[0].special == "34584"


def test_week_page_rejects_an_unknown_region():
    with pytest.raises(KeyError, match="mien-tay"):
        kt.parse_region_week(WEEK_MN, region="mien-tay")


# --- the đài calendar ---------------------------------------------------------------
# Derived from history rather than hardcoded: provinces do change their day, and a
# hardcoded table would go stale silently instead of following the data.


def _week_of(day: date, names: tuple[str, ...]) -> list[kt.Board]:
    return [kt.parse_board(AN_GIANG_2026, province=n, on=day) for n in names]


def test_schedule_reads_the_dai_calendar_off_recent_history():
    boards = _week_of(date(2026, 8, 20), ("an-giang", "binh-thuan", "tay-ninh"))
    boards += _week_of(date(2026, 8, 21), ("binh-duong", "tra-vinh", "vinh-long"))

    calendar = kt.schedule_from(boards)

    assert calendar[3] == ("an-giang", "binh-thuan", "tay-ninh")  # Thursday
    assert calendar[4] == ("binh-duong", "tra-vinh", "vinh-long")  # Friday


def test_dai_on_answers_for_a_future_day_of_the_same_weekday():
    boards = _week_of(date(2026, 8, 20), ("an-giang", "tay-ninh"))
    assert kt.dai_on(boards, date(2026, 9, 3)) == ("an-giang", "tay-ninh")


def test_a_dai_that_moved_day_is_forgotten_on_the_old_one():
    old = _week_of(date(2026, 1, 8), ("an-giang",))
    new = _week_of(date(2026, 8, 21), ("an-giang",))

    calendar = kt.schedule_from(old + new)

    assert calendar.get(3) is None
    assert calendar[4] == ("an-giang",)


def test_an_empty_archive_has_no_calendar():
    assert kt.schedule_from([]) == {}
    assert kt.dai_on([], date(2026, 8, 20)) == ()


def test_next_draw_date_finds_the_dai_s_own_weekday():
    boards = _week_of(date(2026, 8, 20), ("an-giang",))
    assert kt.next_draw_date(boards, "an-giang", on=date(2026, 8, 25)) == date(2026, 8, 27)


def test_next_draw_date_skips_a_day_the_dai_already_drew():
    """Today's board is already in. Phán is for the kỳ after it, not that one."""
    boards = _week_of(date(2026, 8, 20), ("an-giang",)) + _week_of(
        date(2026, 8, 27), ("an-giang",)
    )
    assert kt.next_draw_date(boards, "an-giang", on=date(2026, 8, 27)) == date(2026, 9, 3)


def test_next_draw_date_returns_today_when_today_is_the_day():
    boards = _week_of(date(2026, 8, 20), ("an-giang",))
    assert kt.next_draw_date(boards, "an-giang", on=date(2026, 8, 27)) == date(2026, 8, 27)


def test_a_dai_with_no_calendar_has_no_next_draw():
    assert kt.next_draw_date([], "an-giang", on=date(2026, 8, 25)) is None


# --- days nobody drew ---------------------------------------------------------------
# minhngoc marks Tết by printing "Tết" where the đặc biệt goes and a bare 0 in every
# other prize cell. Taking those zeros at face value would file 27 fake 00s per holiday
# into the frequency table - a quieter and worse failure than a gap.

TET_2008 = (
    '<table class="bkqtinhmienbac"><tbody>'
    '<tr><td class="thu">Thứ năm</td><td class="ngay">Ngày: 07/02/2008</td></tr>'
    '<tr><td class="giaidbl">Giải ĐB</td><td class="giaidb"><div>Tết</div></td></tr>'
    '<tr><td class="giai1l">Giải nhất</td><td class="giai1"><div>0</div></td></tr>'
    '<tr><td class="giai2l">Giải nhì</td><td class="giai2"><div>0</div><div>0</div></td></tr>'
    '<tr><td class="giai3l">Giải ba</td><td class="giai3">'
    "<div>0</div><div>0</div><div>0</div><div>0</div><div>0</div><div>0</div></td></tr>"
    '<tr><td class="giai4l">Giải tư</td><td class="giai4">'
    "<div>0</div><div>0</div><div>0</div><div>0</div></td></tr>"
    '<tr><td class="giai5l">Giải năm</td><td class="giai5">'
    "<div>0</div><div>0</div><div>0</div><div>0</div><div>0</div><div>0</div></td></tr>"
    '<tr><td class="giai6l">Giải sáu</td><td class="giai6">'
    "<div>0</div><div>0</div><div>0</div></td></tr>"
    '<tr><td class="giai7l">Giải bảy</td><td class="giai7">'
    "<div>0</div><div>0</div><div>0</div><div>0</div></td></tr>"
    "</tbody></table>"
)


def test_a_tet_day_is_refused_not_read_as_twenty_seven_zeros():
    with pytest.raises(kt.NoDraw, match="không quay"):
        kt.parse_board(TET_2008, province="mien-bac", on=date(2008, 2, 7))


def test_a_tet_day_costs_the_holiday_not_the_whole_week():
    """One 'Tết' cell used to abort the page and lose the other six days with it."""
    page = (
        '<div class="box_kqxs"><span class="tngay">Ngày: '
        '<a href="/ket-qua-xo-so/07-02-2008.html">07/02/2008</a></span>'
        f"{TET_2008}</div>"
        '<div class="box_kqxs"><span class="tngay">Ngày: '
        '<a href="/ket-qua-xo-so/08-02-2008.html">08/02/2008</a></span>'
        f"{MIEN_BAC_2005}</div>"
    )
    skipped: list[tuple[date, str]] = []

    boards = kt.parse_region_week(
        page, region="mb", on_no_draw=lambda day, slug, why: skipped.append((day, slug))
    )

    assert [b.date for b in boards] == [date(2008, 2, 8)]
    assert skipped == [(date(2008, 2, 7), "mien-bac")]


def test_a_no_draw_day_is_reported_not_swallowed():
    """Silence would look identical to a network gap. It is not the same thing."""
    page = (
        '<div class="box_kqxs"><span class="tngay">Ngày: '
        '<a href="/ket-qua-xo-so/07-02-2008.html">07/02/2008</a></span>'
        f"{TET_2008}</div>"
    )
    assert kt.parse_region_week(page, region="mb") == ()


def test_a_genuinely_broken_board_still_raises_loudly():
    """A missing tier is corruption, not a holiday, and must not be mistaken for one."""
    broken = AN_GIANG_2026.replace('<td class="giai7">516</td>', "<td></td>")
    with pytest.raises(ValueError) as caught:
        kt.parse_board(broken, province="an-giang", on=date(2026, 8, 20))
    assert not isinstance(caught.value, kt.NoDraw)
