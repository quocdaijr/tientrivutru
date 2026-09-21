"""Vietnamese lunar calendar, computed offline.

Implements Ho Ngoc Duc's algorithm (the reference implementation behind most
Vietnamese lunar calendars), so the oracle can consult the moon without a network
call. Timezone is fixed at UTC+7 because that is the meridian Vietnamese lunar
dates are defined against.

The astronomy here is real. What the oracle then does with it is not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

VN_TIMEZONE = 7.0
# The reference algorithm's INT() is Math.floor, NOT truncation-toward-zero. The two
# agree only for non-negative values, and several intermediates here go negative for
# dates before 2000 (the sun-longitude series is anchored at J2000). Using Python's
# int() there silently produced negative "sectors", which broke lunar-month detection
# for 14 years between 1930 and 1998 - including 1990.
DEG = math.pi / 180
SYNODIC_MONTH = 29.530588853
EPOCH_OFFSET = 2415021.076998695

CAN = ("Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý")
CHI = ("Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi")


@dataclass(frozen=True, slots=True)
class LunarDate:
    day: int
    month: int
    year: int
    is_leap_month: bool
    day_can_chi: str
    year_can_chi: str
    zodiac: str

    def __str__(self) -> str:
        leap = " (nhuận)" if self.is_leap_month else ""
        return (
            f"{self.day}/{self.month}{leap} âm lịch, "
            f"ngày {self.day_can_chi}, năm {self.year_can_chi}"
        )


def julian_day_from_date(day: date) -> int:
    """Julian day number at noon for a Gregorian/Julian calendar date."""
    dd, mm, yy = day.day, day.month, day.year
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def _new_moon(k: int) -> float:
    """Julian day of the k-th new moon since 1900-01-01."""
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * DEG)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * DEG) + 0.0021 * math.sin(2 * DEG * m)
    c1 -= 0.4068 * math.sin(mpr * DEG) + 0.0161 * math.sin(2 * DEG * mpr)
    c1 -= 0.0004 * math.sin(3 * DEG * mpr)
    c1 += 0.0104 * math.sin(2 * DEG * f) - 0.0051 * math.sin((m + mpr) * DEG)
    c1 -= 0.0074 * math.sin((m - mpr) * DEG) + 0.0004 * math.sin((2 * f + m) * DEG)
    c1 -= 0.0004 * math.sin((2 * f - m) * DEG) - 0.0006 * math.sin((2 * f + mpr) * DEG)
    c1 += 0.0010 * math.sin((2 * f - mpr) * DEG) + 0.0005 * math.sin((2 * mpr + m) * DEG)
    if t < -11:
        deltat = (
            0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
        )
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    return jd1 + c1 - deltat


def _new_moon_day(k: int, tz: float = VN_TIMEZONE) -> int:
    return math.floor(_new_moon(k) + 0.5 + tz / 24.0)


def _sun_longitude(jdn: float, tz: float = VN_TIMEZONE) -> int:
    """Sun's longitude in 30-degree sectors (0..11) at the start of the given day."""
    t = (jdn - 2451545.5 - tz / 24.0) / 36525
    t2 = t * t
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(DEG * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(DEG * 2 * m) + 0.000290 * math.sin(DEG * 3 * m)
    lon = (l0 + dl) * DEG
    lon = lon - math.pi * 2 * math.floor(lon / (math.pi * 2))
    return math.floor(lon / math.pi * 6)


def _lunar_month_11(year: int, tz: float = VN_TIMEZONE) -> int:
    off = julian_day_from_date(date(year, 12, 31)) - 2415021
    k = math.floor(off / SYNODIC_MONTH)
    nm = _new_moon_day(k, tz)
    if _sun_longitude(nm, tz) >= 9:
        nm = _new_moon_day(k - 1, tz)
    return nm


def _leap_month_offset(a11: int, tz: float = VN_TIMEZONE) -> int:
    k = math.floor((a11 - EPOCH_OFFSET) / SYNODIC_MONTH + 0.5)
    i = 1
    arc = _sun_longitude(_new_moon_day(k + i, tz), tz)
    while True:
        last = arc
        i += 1
        arc = _sun_longitude(_new_moon_day(k + i, tz), tz)
        if arc == last or i >= 14:
            break
    return i - 1


def to_lunar(day: date, tz: float = VN_TIMEZONE) -> LunarDate:
    """Convert a solar date to its Vietnamese lunar equivalent."""
    day_number = julian_day_from_date(day)
    k = math.floor((day_number - EPOCH_OFFSET) / SYNODIC_MONTH)
    month_start = _new_moon_day(k + 1, tz)
    if month_start > day_number:
        month_start = _new_moon_day(k, tz)

    a11 = _lunar_month_11(day.year, tz)
    b11 = a11
    if a11 >= month_start:
        lunar_year = day.year
        a11 = _lunar_month_11(day.year - 1, tz)
    else:
        lunar_year = day.year + 1
        b11 = _lunar_month_11(day.year + 1, tz)

    lunar_day = day_number - month_start + 1
    diff = math.floor((month_start - a11) / 29)
    is_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_offset = _leap_month_offset(a11, tz)
        if diff >= leap_offset:
            lunar_month = diff + 10
            if diff == leap_offset:
                is_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1

    return LunarDate(
        day=lunar_day,
        month=lunar_month,
        year=lunar_year,
        is_leap_month=is_leap,
        day_can_chi=f"{CAN[(day_number + 9) % 10]} {CHI[(day_number + 1) % 12]}",
        year_can_chi=f"{CAN[(lunar_year + 6) % 10]} {CHI[(lunar_year + 8) % 12]}",
        zodiac=CHI[(lunar_year + 8) % 12],
    )
