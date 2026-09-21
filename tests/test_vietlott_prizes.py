"""Jackpot and prize tiers. Fixtures are the real vietlott.vn markup from 2026-08-20.

The one thing these tests exist to protect: a jackpot figure is money, on a page that
promises none of its numbers lie. A layout change must raise, never return a plausible
wrong amount, and never silently return a stale one.
"""

from __future__ import annotations

import pytest

from tientrivutru.games import MEGA645, POWER655
from tientrivutru.sources import vietlott_prizes as prizes

# Trimmed to the two regions the parser reads, byte-for-byte from the live pages.
POWER655_PAGE = """
<div class="gt_jackpot"><div class="row">
<div class="col-md-5"><h5>Giá trị Jackpot 1</h5></div>
<div class="col-md-7"><div class="so_tien"><h3>34.897.731.150</h3><p>VNĐ</p></div></div>
<div class="col-md-5"><h5>Giá trị Jackpot 2</h5></div>
<div class="col-md-7"><div class="so_tien"><h3>3.544.192.350</h3><p>VNĐ</p></div></div>
</div></div><!-- /gt_jackpot -->
<table class="table table-hover"><thead><tr><th>Giải thưởng</th><th>Kết quả</th>
<th class="text-right">Số lượng giải</th><th class="text-right">Giá trị giải (đồng)</th>
</tr></thead><tbody>
<tr><td>Jackpot 1</td><td class="color_red" nowrap><b>O O O O O O</b></td>
<td class="text-right">0</td><td class="color_red text-right"><b>34.897.731.150</b></td></tr>
<tr><td>Jackpot 2</td>
<td class="color_red" nowrap><b>O O O O O | <span class="active">O</span></b></td>
<td class="text-right">0</td><td class="color_red text-right"><b>3.544.192.350</b></td></tr>
<tr><td>Giải Nhất</td><td class="color_red" nowrap><b>O O O O O</b></td>
<td class="text-right">9</td><td class="color_red text-right"><b>40.000.000</b></td></tr>
<tr><td>Giải Nhì</td><td class="color_red" nowrap><b>O O O O</b></td>
<td class="text-right">776</td><td class="color_red text-right"><b>500.000</b></td></tr>
<tr><td>Giải Ba</td><td class="color_red" nowrap><b>O O O</b></td>
<td class="text-right">16.116</td><td class="color_red text-right"><b>50.000</b></td></tr>
</tbody></table>
"""

MEGA645_PAGE = """
<div class="gt_jackpot"><div class="row">
<div class="col-md-5"><h5>Giá trị Jackpot</h5></div>
<div class="col-md-7"><div class="so_tien"><h3>24.507.110.500</h3><p>VNĐ</p></div></div>
</div></div><!-- /gt_jackpot -->
<table class="table table-hover"><thead><tr><th>Giải thưởng</th><th>Kết quả</th>
<th class="text-right">Số lượng giải</th><th class="text-right">Giá trị giải (đồng)</th>
</tr></thead><tbody>
<tr><td>Jackpot</td><td class="color_red" nowrap><b>O O O O O O</b></td>
<td class="text-right">0</td><td class="color_red text-right"><b>24.507.110.500</b></td></tr>
<tr><td>Giải Nhất</td><td class="color_red" nowrap><b>O O O O O</b></td>
<td class="text-right">23</td><td class="color_red text-right"><b>10.000.000</b></td></tr>
<tr><td>Giải Nhì</td><td class="color_red" nowrap><b>O O O O</b></td>
<td class="text-right">1.333</td><td class="color_red text-right"><b>300.000</b></td></tr>
<tr><td>Giải Ba</td><td class="color_red" nowrap><b>O O O</b></td>
<td class="text-right">21.272</td><td class="color_red text-right"><b>30.000</b></td></tr>
</tbody></table>
"""

# A draw somebody actually won: the top tier has a winner, so nothing rolls over.
WON_PAGE = MEGA645_PAGE.replace(
    '<td class="text-right">0</td><td class="color_red text-right"><b>24.507.110.500</b></td>',
    '<td class="text-right">1</td><td class="color_red text-right"><b>24.507.110.500</b></td>',
)


def test_parses_both_power_jackpots():
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)

    assert result.game == "power655"
    assert result.draw_id == "01386"
    assert result.jackpots == {"Jackpot 1": 34_897_731_150, "Jackpot 2": 3_544_192_350}
    assert result.source == "live:vietlott.vn"


def test_parses_mega_single_jackpot():
    result = prizes.parse_prizes(MEGA645, "01551", MEGA645_PAGE)

    assert result.jackpots == {"Jackpot": 24_507_110_500}
    assert result.top_jackpot_vnd == 24_507_110_500


def test_parses_every_prize_tier_with_winner_counts():
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)

    assert [(t.label, t.winners, t.value_vnd) for t in result.tiers] == [
        ("Jackpot 1", 0, 34_897_731_150),
        ("Jackpot 2", 0, 3_544_192_350),
        ("Giải Nhất", 9, 40_000_000),
        ("Giải Nhì", 776, 500_000),
        ("Giải Ba", 16_116, 50_000),
    ]


def test_thousands_separators_are_stripped_from_winner_counts():
    """16.116 winners is sixteen thousand, not sixteen - a dot is not a decimal point."""
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)
    third = next(t for t in result.tiers if t.label == "Giải Ba")

    assert third.winners == 16_116


def test_rolled_over_is_true_when_the_top_tier_had_no_winner():
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)

    assert result.rolled_over is True


def test_rolled_over_is_false_when_somebody_won():
    result = prizes.parse_prizes(MEGA645, "01551", WON_PAGE)

    assert result.rolled_over is False


def test_fixed_tiers_match_the_static_prize_table():
    """The scoreboard prices non-jackpot tiers from games.py. If vietlott ever changes
    them, this fails and tells us the static table has gone stale - which matters,
    because those values are what paper_won_vnd is computed from."""
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)
    live_values = {t.label: t.value_vnd for t in result.tiers}

    assert live_values["Giải Nhất"] == POWER655.prizes["first"]
    assert live_values["Giải Nhì"] == POWER655.prizes["second"]
    assert live_values["Giải Ba"] == POWER655.prizes["third"]


def test_fetched_at_is_recorded_because_the_figure_goes_stale():
    result = prizes.parse_prizes(MEGA645, "01551", MEGA645_PAGE)

    assert result.fetched_at.endswith("+00:00") or result.fetched_at.endswith("Z")


def test_missing_jackpot_block_raises_rather_than_guessing():
    with pytest.raises(prizes.PrizeParseError, match="gt_jackpot"):
        prizes.parse_prizes(MEGA645, "01551", "<html><body>nothing here</body></html>")


def test_missing_prize_table_raises():
    only_jackpot = MEGA645_PAGE.split("<table")[0]

    with pytest.raises(prizes.PrizeParseError, match="prize table"):
        prizes.parse_prizes(MEGA645, "01551", only_jackpot)


def test_power_page_missing_its_second_jackpot_raises():
    """Power 6/55 has two jackpots. One is a layout change, not a valid page."""
    crippled = POWER655_PAGE.replace(
        '<div class="col-md-5"><h5>Giá trị Jackpot 2</h5></div>\n'
        '<div class="col-md-7"><div class="so_tien"><h3>3.544.192.350</h3><p>VNĐ</p></div></div>\n',
        "",
    )

    with pytest.raises(prizes.PrizeParseError, match="expected 2 jackpot"):
        prizes.parse_prizes(POWER655, "01386", crippled)


def test_a_jackpot_that_is_not_a_number_raises():
    broken = MEGA645_PAGE.replace("24.507.110.500", "Đang cập nhật")

    with pytest.raises(prizes.PrizeParseError):
        prizes.parse_prizes(MEGA645, "01551", broken)


def test_implausibly_small_jackpot_raises():
    """Below the game's own floor is not a jackpot, it is a mis-parse. Mega's floor is
    12 billion, so a figure in the millions means the regex latched onto a prize row."""
    wrong = MEGA645_PAGE.replace("24.507.110.500", "30.000")

    with pytest.raises(prizes.PrizeParseError, match="floor"):
        prizes.parse_prizes(MEGA645, "01551", wrong)


def test_as_dict_round_trips_through_json():
    import json

    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)
    revived = json.loads(json.dumps(result.as_dict()))

    assert revived["jackpots"]["Jackpot 1"] == 34_897_731_150
    assert revived["tiers"][0]["winners"] == 0
    assert revived["draw_id"] == "01386"


# ------------------------------------- mapping scraped labels onto wheel.py's tier keys


def test_tier_values_uses_the_keys_wheel_expects():
    """wheel.payout_vnd is keyed on jackpot1/jackpot2; the page says "Jackpot 1"."""
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)

    assert result.tier_values(POWER655) == {
        "jackpot1": 34_897_731_150,
        "jackpot2": 3_544_192_350,
    }


def test_tier_values_for_a_single_jackpot_game():
    result = prizes.parse_prizes(MEGA645, "01551", MEGA645_PAGE)

    assert result.tier_values(MEGA645) == {"jackpot": 24_507_110_500}


def test_tier_values_feeds_straight_into_payout_vnd():
    """The whole point of the mapping: no caller should have to translate labels."""
    from tientrivutru import wheel

    result = prizes.parse_prizes(MEGA645, "01551", MEGA645_PAGE)
    counts = wheel.prize_counts(MEGA645, 6)

    paid = wheel.payout_vnd(MEGA645, counts, jackpots=result.tier_values(MEGA645))

    # six hits wins the jackpot once, plus the lower tiers the other tickets pick up
    assert paid > 24_507_110_500


def test_tier_values_rejects_a_label_the_game_does_not_have():
    """A Power page parsed against Mega would silently invent a jackpot2 otherwise."""
    result = prizes.parse_prizes(POWER655, "01386", POWER655_PAGE)

    with pytest.raises(ValueError, match="jackpot2"):
        result.tier_values(MEGA645)
