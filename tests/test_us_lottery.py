"""US lottery source. Fixtures are real rows from the mirror, fetched 2026-08-19."""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru.games import MEGAMILLIONS, POWERBALL, PROPHECY_GAMES
from tientrivutru.models import Draw
from tientrivutru.sources import us_lottery as us

POWERBALL_CSV = """date,white_balls,red_ball,power_play
10/07/2015,18|30|40|48|52,9,3X
10/10/2015,12|27|29|43|68,1,2X
08/17/2026,8|15|25|49|65,22,4X
"""

MEGAMILLIONS_CSV = """date,white_balls,yellow_ball,megaplier
10/31/2017,6|28|31|52|53,12,4X
11/3/2017,10|22|42|61|69,3,2X
"""


def test_parses_powerball_rows_in_date_order():
    draws = us.parse_csv(POWERBALL, POWERBALL_CSV)

    assert len(draws) == 3
    assert [d.draw_id for d in draws] == ["00001", "00002", "00003"]
    assert draws[0].date == date(2015, 10, 7)
    assert draws[0].main == (18, 30, 40, 48, 52)
    assert draws[0].bonus == 9


def test_parses_megamillions_and_its_differently_named_bonus_column():
    draws = us.parse_csv(MEGAMILLIONS, MEGAMILLIONS_CSV)
    assert draws[0].bonus == 12
    assert draws[1].bonus == 3


def test_handles_unpadded_us_dates():
    """The mirror writes '11/3/2017', not '11/03/2017'."""
    assert us.parse_us_date("11/3/2017") == date(2017, 11, 3)
    assert us.parse_us_date("10/07/2015") == date(2015, 10, 7)


def test_ids_are_assigned_after_sorting_by_date():
    """Rows out of order must still get chronological ids."""
    shuffled = "date,white_balls,red_ball,power_play\n" + "\n".join(
        ["10/10/2015,12|27|29|43|68,1,2X", "10/07/2015,18|30|40|48|52,9,3X"]
    )
    draws = us.parse_csv(POWERBALL, shuffled)
    assert draws[0].date < draws[1].date
    assert draws[0].draw_id == "00001"


def test_white_balls_are_sorted_even_if_upstream_is_not():
    row = "date,white_balls,red_ball,power_play\n10/07/2015,52|18|40|30|48,9,3X"
    draw = us.parse_csv(POWERBALL, row)[0]
    assert draw.main == (18, 30, 40, 48, 52)


def test_rejects_wrong_white_ball_count():
    row = "date,white_balls,red_ball,power_play\n10/07/2015,18|30|40|48,9,3X"
    with pytest.raises(ValueError, match="expected 5 white balls"):
        us.parse_csv(POWERBALL, row)


@pytest.mark.parametrize("missing", ["white_balls", "red_ball"])
def test_rejects_missing_columns(missing):
    whites = "" if missing == "white_balls" else "18|30|40|48|52"
    red = "" if missing == "red_ball" else "9"
    row = f"date,white_balls,red_ball,power_play\n10/07/2015,{whites},{red},3X"
    with pytest.raises(ValueError, match=f"missing '{missing}'"):
        us.parse_csv(POWERBALL, row)


def test_rejects_empty_csv():
    with pytest.raises(ValueError, match="empty"):
        us.parse_csv(POWERBALL, "date,white_balls,red_ball,power_play\n")


def test_bonus_from_a_separate_pool_may_repeat_a_main_number():
    """99 real Powerball draws do exactly this - the model must allow it."""
    row = "date,white_balls,red_ball,power_play\n10/07/2015,7|30|40|48|52,7,3X"
    draw = us.parse_csv(POWERBALL, row)[0]
    assert draw.bonus == 7
    assert draw.bonus in draw.main


def test_bonus_outside_its_own_pool_is_rejected():
    """Powerball's red ball tops out at 26, even though whites run to 69."""
    row = "date,white_balls,red_ball,power_play\n10/07/2015,18|30|40|48|52,27,3X"
    with pytest.raises(ValueError, match="outside 1..26"):
        us.parse_csv(POWERBALL, row)


def test_power655_bonus_still_may_not_repeat_a_main_number():
    """The looser rule must apply only to separate-pool games."""
    with pytest.raises(ValueError, match="duplicates a main number"):
        Draw(
            game="power655",
            draw_id="1",
            date=date(2026, 8, 18),
            main=(3, 15, 18, 38, 41, 48),
            bonus=38,
        )


def test_us_games_are_excluded_from_prophecies():
    """Bao 12 is a Vietlott product; US games are statistics only."""
    assert not POWERBALL.wheel_playable
    assert not MEGAMILLIONS.wheel_playable
    assert "powerball" not in PROPHECY_GAMES
    assert "megamillions" not in PROPHECY_GAMES
    assert set(PROPHECY_GAMES) == {"power655", "mega645"}


def test_us_game_shapes_match_the_published_matrices():
    assert (POWERBALL.pool, POWERBALL.pick, POWERBALL.bonus_pool) == (69, 5, 26)
    assert (MEGAMILLIONS.pool, MEGAMILLIONS.pick, MEGAMILLIONS.bonus_pool) == (70, 5, 25)
    assert not POWERBALL.bonus_shares_main_pool
    assert list(POWERBALL.bonus_numbers) == list(range(1, 27))


def test_mirror_urls_point_at_the_current_format_files():
    """Older-format files are excluded on purpose: mixing number spaces corrupts stats."""
    assert us.mirror_url(POWERBALL).endswith("/powerball.csv")
    assert "pre-10-07-2015" not in us.mirror_url(POWERBALL)
