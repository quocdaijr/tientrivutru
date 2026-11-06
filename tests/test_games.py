"""Which days a game draws on."""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru.games import MEGA645, POWER655, POWERBALL, is_draw_day


@pytest.mark.parametrize(
    ("spec", "day", "expected"),
    [
        (POWER655, date(2026, 2, 17), False),  # mùng 1 Tết Bính Ngọ, a Tuesday
        (MEGA645, date(2025, 1, 29), False),  # mùng 1 Tết Ất Tỵ, a Wednesday
        (POWER655, date(2025, 1, 28), False),  # giao thừa (29/12), a Tuesday
        (POWER655, date(2026, 2, 19), True),  # mùng 3: Vietlott is back
        (POWERBALL, date(2026, 2, 16), True),  # US games know nothing of Tết (a Monday)
    ],
)
def test_vietlott_does_not_draw_over_tet(spec, day, expected):
    """Every Tết gap in the 2018-2026 history is giao thừa or mùng 1, and none of them
    consumed a draw id - so counting them as draw days mislabels the next prophecy."""
    assert is_draw_day(spec, day) is expected
