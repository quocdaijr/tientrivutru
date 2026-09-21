"""Fallback crawler. Page fixtures are the real vietlott.vn markup from 2026-08-19."""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru.games import MEGA645, POWER655, POWERBALL
from tientrivutru.sources import vietlott_live as live

# Trimmed to the two regions the parser reads, byte-for-byte from the live pages.
POWER655_PAGE = """
<div class="chitietketqua_title"><h4>Kết quả quay số mở thưởng POWER 6/55</h4>
<h5>Kỳ quay thưởng <b>#01386</b> ngày <b>18/08/2026</b></h5></div>
<div class="day_so_ket_qua_v2"><span class="bong_tron small">03</span>
<span class="bong_tron small">15</span><span class="bong_tron small">18</span>
<span class="bong_tron small">38</span><span class="bong_tron small">41</span>
<span class="bong_tron small">48</span><i>|</i>
<span class="bong_tron small no-margin-right active">30</span></div>
"""

# This is the draw the mirror was missing.
MEGA645_PAGE = """
<div class="chitietketqua_title"><H5>Kỳ quay thưởng <b>#01550</b> ngày <b>16/08/2026</b></H5></div>
<div class="day_so_ket_qua_v2"><span class="bong_tron">06</span><span class="bong_tron">07</span>
<span class="bong_tron">15</span><span class="bong_tron">19</span><span class="bong_tron">36</span>
<span class="bong_tron no-margin-right">41</span></div>
"""


def test_parses_power655_and_separates_the_bonus():
    draw = live.parse_page(POWER655, POWER655_PAGE)

    assert draw.draw_id == "01386"
    assert draw.date == date(2026, 8, 18)
    assert draw.main == (3, 15, 18, 38, 41, 48)
    assert draw.bonus == 30
    assert draw.source == "live:vietlott.vn"


def test_parses_the_draw_the_mirror_was_missing():
    """Mega 6/45 #01550 (Sun 2026-08-16) is absent upstream but present here."""
    draw = live.parse_page(MEGA645, MEGA645_PAGE)

    assert draw.draw_id == "01550"
    assert draw.date == date(2026, 8, 16)
    assert draw.main == (6, 7, 15, 19, 36, 41)
    assert draw.bonus is None


def test_handles_uppercase_h5_tag():
    """The Mega page uses <H5>, the Power page uses <h5>."""
    assert "H5" in MEGA645_PAGE
    assert live.parse_page(MEGA645, MEGA645_PAGE).draw_id == "01550"


def test_url_requires_the_html_suffix():
    """Without .html Cloudflare serves an error page instead of results."""
    assert live.page_url(POWER655).endswith("/655.html")
    assert live.page_url(MEGA645).endswith("/645.html")


def test_url_rejects_games_without_a_vietlott_page():
    with pytest.raises(live.LiveFetchError, match="Vietlott only"):
        live.page_url(POWERBALL)


def test_missing_title_fails_loudly():
    page = '<div class="day_so_ket_qua_v2"><span class="bong_tron">06</span></div>'
    with pytest.raises(live.LiveFetchError, match="draw title"):
        live.parse_page(MEGA645, page)


def test_missing_result_block_fails_loudly():
    page = "<h5>Kỳ quay thưởng <b>#01550</b> ngày <b>16/08/2026</b></h5>"
    with pytest.raises(live.LiveFetchError, match="result block"):
        live.parse_page(MEGA645, page)


def test_wrong_number_count_fails_loudly():
    """A layout change must not yield a plausible-but-wrong draw."""
    page = MEGA645_PAGE.replace('<span class="bong_tron">06</span>', "")
    with pytest.raises(live.LiveFetchError, match="expected 6 numbers"):
        live.parse_page(MEGA645, page)


def test_power655_page_needs_seven_numbers():
    page = POWER655_PAGE.replace(
        '<span class="bong_tron small no-margin-right active">30</span>', ""
    )
    with pytest.raises(live.LiveFetchError, match="expected 7 numbers"):
        live.parse_page(POWER655, page)


def test_browser_user_agent_is_sent():
    """The default requests agent gets a Cloudflare block; a browser UA does not."""
    assert "Mozilla" in live.BROWSER_HEADERS["User-Agent"]
