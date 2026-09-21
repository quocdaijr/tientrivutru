"""Lunar calendar, pinned against independently known reference dates."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tientrivutru.lunar import julian_day_from_date, to_lunar


def test_tet_2026_is_lunar_new_year():
    """Tet Binh Ngo fell on 17 Feb 2026 - so that date must be lunar 1/1/2026."""
    lunar = to_lunar(date(2026, 2, 17))

    assert (lunar.day, lunar.month) == (1, 1)
    assert lunar.year == 2026
    assert lunar.year_can_chi == "Bính Ngọ"
    assert lunar.zodiac == "Ngọ"


def test_millennium_reference_date():
    """1 Jan 2000 is widely published as lunar 25/11/1999, year Ky Mao."""
    lunar = to_lunar(date(2000, 1, 1))

    assert (lunar.day, lunar.month, lunar.year) == (25, 11, 1999)
    assert lunar.year_can_chi == "Kỷ Mão"


def test_day_can_chi_cycles_every_sixty_days():
    start = date(2026, 8, 19)
    assert to_lunar(start).day_can_chi == to_lunar(start + timedelta(days=60)).day_can_chi
    assert to_lunar(start).day_can_chi != to_lunar(start + timedelta(days=1)).day_can_chi


def test_lunar_day_is_always_in_range():
    day = date(2026, 1, 1)
    for _ in range(400):
        lunar = to_lunar(day)
        assert 1 <= lunar.day <= 30
        assert 1 <= lunar.month <= 12
        day += timedelta(days=1)


def test_julian_day_is_monotonic():
    a = julian_day_from_date(date(2026, 8, 18))
    b = julian_day_from_date(date(2026, 8, 19))
    assert b == a + 1


def test_julian_day_known_value():
    """1 Jan 2000 noon is Julian day 2451545."""
    assert julian_day_from_date(date(2000, 1, 1)) == 2451545


@pytest.mark.parametrize("day", [date(2026, 2, 17), date(2026, 8, 19)])
def test_str_renders_vietnamese(day):
    assert "âm lịch" in str(to_lunar(day))


# Known Tết dates. 1968 is the famous one: Vietnam moved from UTC+8 to UTC+7 that year,
# so the North kept Tết Mậu Thân on 29 January while the South kept it on the 30th.
# This algorithm is UTC+7, so 29 January is the correct answer, not a bug.
KNOWN_TET = {
    1930: date(1930, 1, 30),
    1945: date(1945, 2, 13),
    1960: date(1960, 1, 28),
    1968: date(1968, 1, 29),
    1975: date(1975, 2, 11),
    1984: date(1984, 2, 2),
    1990: date(1990, 1, 27),
    1995: date(1995, 1, 31),
    2000: date(2000, 2, 5),
    2008: date(2008, 2, 7),
    2020: date(2020, 1, 25),
    2024: date(2024, 2, 10),
    2025: date(2025, 1, 29),
    2026: date(2026, 2, 17),
}


def _find_tet(year: int) -> date | None:
    day = date(year, 1, 20)
    for _ in range(35):
        lunar = to_lunar(day)
        if lunar.day == 1 and lunar.month == 1 and not lunar.is_leap_month:
            return day
        day += timedelta(days=1)
    return None


@pytest.mark.parametrize("year,expected", sorted(KNOWN_TET.items()))
def test_known_tet_dates(year, expected):
    assert _find_tet(year) == expected


@pytest.mark.parametrize("year", range(1930, 2036))
def test_every_year_has_a_findable_tet(year):
    """Regression: Python's int() truncates toward zero while the reference algorithm's
    INT() is floor. The two differ only for negative intermediates, which occur for
    dates before 2000 - and that silently broke lunar month detection for 14 years
    between 1930 and 1998, including 1990.
    """
    tet = _find_tet(year)
    assert tet is not None, f"no lunar new year found in {year}"
    assert date(year, 1, 21) <= tet <= date(year, 2, 21)


def test_sun_longitude_sector_is_never_negative():
    """The direct cause of that bug: a negative sector index."""
    from tientrivutru.lunar import _sun_longitude, julian_day_from_date

    for year in (1930, 1968, 1990, 1999, 2000, 2026):
        sector = _sun_longitude(julian_day_from_date(date(year, 6, 15)))
        assert 0 <= sector <= 11, f"{year}: sector {sector} outside 0..11"
