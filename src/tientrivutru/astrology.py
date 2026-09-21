"""Vietnamese and Western fortune-telling inputs, derived from a birth date.

Everything here is computed, never stored. The web UI runs the same logic in the
browser so a birth date never leaves the device; this module is the source of truth
that generates the lookup table the browser uses, and it keeps the whole thing
testable in pytest.

The astronomy and the sexagenary cycle are real. The conclusions drawn from them are
entertainment, and the module says so rather than pretending otherwise.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from .lunar import CAN, CHI, to_lunar

SEXAGENARY_CYCLE = 60
SEXAGENARY_EPOCH_YEAR = 4
"""Year 4 CE is Giáp Tý, index 0. Checks out: 1984 -> 0, 2026 -> 42 (Bính Ngọ)."""

# Ngũ hành nạp âm: one element per PAIR of sexagenary years, 30 entries covering 60 years.
NAP_AM = (
    "Hải Trung Kim", "Lư Trung Hỏa", "Đại Lâm Mộc", "Lộ Bàng Thổ", "Kiếm Phong Kim",
    "Sơn Đầu Hỏa", "Giản Hạ Thủy", "Thành Đầu Thổ", "Bạch Lạp Kim", "Dương Liễu Mộc",
    "Tuyền Trung Thủy", "Ốc Thượng Thổ", "Tích Lịch Hỏa", "Tùng Bách Mộc",
    "Trường Lưu Thủy", "Sa Trung Kim", "Sơn Hạ Hỏa", "Bình Địa Mộc", "Bích Thượng Thổ",
    "Kim Bạch Kim", "Phú Đăng Hỏa", "Thiên Hà Thủy", "Đại Trạch Thổ", "Thoa Xuyến Kim",
    "Tang Đố Mộc", "Đại Khê Thủy", "Sa Trung Thổ", "Thiên Thượng Hỏa", "Thạch Lựu Mộc",
    "Đại Hải Thủy",
)

ELEMENTS = ("Kim", "Mộc", "Thủy", "Hỏa", "Thổ")

# Western zodiac, as (start_month, start_day, name). Ma Kết wraps the new year.
ZODIAC_BOUNDS = (
    (1, 20, "Bảo Bình"), (2, 19, "Song Ngư"), (3, 21, "Bạch Dương"),
    (4, 20, "Kim Ngưu"), (5, 21, "Song Tử"), (6, 22, "Cự Giải"),
    (7, 23, "Sư Tử"), (8, 23, "Xử Nữ"), (9, 23, "Thiên Bình"),
    (10, 24, "Bọ Cạp"), (11, 22, "Nhân Mã"), (12, 22, "Ma Kết"),
)

# Sao chiếu mệnh: nine stars rotating yearly, indexed from age 10.
STARS_MALE = (
    "La Hầu", "Thổ Tú", "Thủy Diệu", "Thái Bạch", "Thái Dương",
    "Vân Hán", "Kế Đô", "Thái Âm", "Mộc Đức",
)
STARS_FEMALE = (
    "Kế Đô", "Vân Hán", "Mộc Đức", "Thái Âm", "Thổ Tú",
    "La Hầu", "Thái Dương", "Thái Bạch", "Thủy Diệu",
)
STAR_BASE_AGE = 10

TAM_HOP = (
    ("Thân", "Tý", "Thìn"),
    ("Dần", "Ngọ", "Tuất"),
    ("Hợi", "Mão", "Mùi"),
    ("Tỵ", "Dậu", "Sửu"),
)
TU_HANH_XUNG = (
    ("Dần", "Thân", "Tỵ", "Hợi"),
    ("Tý", "Ngọ", "Mão", "Dậu"),
    ("Thìn", "Tuất", "Sửu", "Mùi"),
)

MASTER_NUMBERS = (11, 22, 33)
PYTHAGOREAN_ROWS = ("ABCDEFGHI", "JKLMNOPQR", "STUVWXYZ")


@dataclass(frozen=True, slots=True)
class Fortune:
    """Everything derivable from one birth date. Contains no identifying data."""

    lunar_year: int
    can_chi: str
    zodiac_animal: str
    nap_am: str
    element: str
    western_sign: str
    life_path: int
    name_number: int | None
    guardian_star: str | None
    tam_hop: tuple[str, ...]
    tu_hanh_xung: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "lunar_year": self.lunar_year,
            "can_chi": self.can_chi,
            "zodiac_animal": self.zodiac_animal,
            "nap_am": self.nap_am,
            "element": self.element,
            "western_sign": self.western_sign,
            "life_path": self.life_path,
            "name_number": self.name_number,
            "guardian_star": self.guardian_star,
            "tam_hop": list(self.tam_hop),
            "tu_hanh_xung": list(self.tu_hanh_xung),
        }


def sexagenary_index(lunar_year: int) -> int:
    """Position in the 60-year cycle. Giáp Tý = 0."""
    return (lunar_year - SEXAGENARY_EPOCH_YEAR) % SEXAGENARY_CYCLE


def can_chi_of_year(lunar_year: int) -> str:
    index = sexagenary_index(lunar_year)
    return f"{CAN[index % len(CAN)]} {CHI[index % len(CHI)]}"


def zodiac_animal_of_year(lunar_year: int) -> str:
    return CHI[sexagenary_index(lunar_year) % len(CHI)]


def nap_am_of_year(lunar_year: int) -> str:
    """The element-name of the year. Each name spans two consecutive years."""
    return NAP_AM[sexagenary_index(lunar_year) // 2]


def element_of_year(lunar_year: int) -> str:
    """The bare five-element class, extracted from the nạp âm name's last word."""
    return nap_am_of_year(lunar_year).rsplit(" ", 1)[-1]


def western_sign(day: date) -> str:
    """Sun sign from the solar date. Ma Kết wraps around the new year."""
    for month, start_day, name in reversed(ZODIAC_BOUNDS):
        if (day.month, day.day) >= (month, start_day):
            return name
    # Before 20 January: still Ma Kết, which began the previous December.
    return "Ma Kết"


def reduce_to_root(value: int, *, keep_master: bool = True) -> int:
    """Numerology reduction, preserving master numbers 11/22/33 when asked."""
    while value > 9:
        if keep_master and value in MASTER_NUMBERS:
            return value
        value = sum(int(ch) for ch in str(value))
    return value


def life_path_number(day: date) -> int:
    """Sum every digit of the birth date, then reduce."""
    digits = sum(int(ch) for ch in day.strftime("%Y%m%d"))
    return reduce_to_root(digits)


def strip_diacritics(text: str) -> str:
    """Fold Vietnamese diacritics so the Pythagorean table applies.

    đ/Đ has no combining form, so it is mapped explicitly rather than lost.
    """
    swapped = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", swapped)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def letter_value(char: str) -> int | None:
    """Pythagorean value 1..9 for an ASCII letter, else None."""
    upper = char.upper()
    for row in PYTHAGOREAN_ROWS:
        position = row.find(upper)
        if position >= 0:
            return position + 1
    return None


def name_number(name: str) -> int | None:
    """Numerology value of a name. None when the name carries no letters."""
    values = [v for ch in strip_diacritics(name) if (v := letter_value(ch)) is not None]
    if not values:
        return None
    return reduce_to_root(sum(values))


def guardian_star(lunar_year: int, current_lunar_year: int, gender: str | None) -> str | None:
    """The star watching over someone this year. None when gender is not supplied.

    Uses tuổi mụ (Vietnamese reckoning: age 1 at birth), the convention these tables
    are built on. Gender is optional precisely so nobody has to disclose it.
    """
    if gender not in ("nam", "nữ"):
        return None
    age = current_lunar_year - lunar_year + 1
    if age < STAR_BASE_AGE:
        age = STAR_BASE_AGE
    table = STARS_MALE if gender == "nam" else STARS_FEMALE
    return table[(age - STAR_BASE_AGE) % len(table)]


def tam_hop_of(animal: str) -> tuple[str, ...]:
    """The two animals that harmonise with this one."""
    for group in TAM_HOP:
        if animal in group:
            return tuple(a for a in group if a != animal)
    return ()


def tu_hanh_xung_of(animal: str) -> tuple[str, ...]:
    """The three animals that clash with this one."""
    for group in TU_HANH_XUNG:
        if animal in group:
            return tuple(a for a in group if a != animal)
    return ()


def read_fortune(
    birth_date: date,
    *,
    name: str | None = None,
    gender: str | None = None,
    today: date | None = None,
) -> Fortune:
    """Derive every fortune input from a birth date.

    The lunar year matters: someone born in January 2026, before Tết on 17 February,
    still belongs to the Ất Tỵ year, not Bính Ngọ.
    """
    lunar = to_lunar(birth_date)
    current_lunar_year = to_lunar(today).year if today else lunar.year
    animal = zodiac_animal_of_year(lunar.year)

    return Fortune(
        lunar_year=lunar.year,
        can_chi=can_chi_of_year(lunar.year),
        zodiac_animal=animal,
        nap_am=nap_am_of_year(lunar.year),
        element=element_of_year(lunar.year),
        western_sign=western_sign(birth_date),
        life_path=life_path_number(birth_date),
        name_number=name_number(name) if name else None,
        guardian_star=guardian_star(lunar.year, current_lunar_year, gender),
        tam_hop=tam_hop_of(animal),
        tu_hanh_xung=tu_hanh_xung_of(animal),
    )


def lunar_year_table(start: int, end: int) -> Mapping[int, dict[str, str]]:
    """Per-year lookup the browser needs, so JS never reimplements the lunar algorithm.

    For each solar year it records the date Tết falls on plus that lunar year's can chi,
    animal and element. From this the browser can place any birth date in its lunar year
    with a single date comparison.
    """
    table: dict[int, dict[str, str]] = {}
    for year in range(start, end + 1):
        tet = _tet_date(year)
        table[year] = {
            "tet": tet.isoformat(),
            "can_chi": can_chi_of_year(year),
            "animal": zodiac_animal_of_year(year),
            "nap_am": nap_am_of_year(year),
            "element": element_of_year(year),
        }
    return MappingProxyType(table)


def _tet_date(solar_year: int) -> date:
    """The solar date of lunar 1/1 for a given lunar year, found by scanning January-February.

    Tết always falls between 21 January and 21 February, so a short scan is exact and
    avoids inverting the lunar conversion.
    """
    for day_number in range(21, 53):  # 21 Jan .. 21 Feb
        candidate = date(solar_year, 1, 1).toordinal() + day_number - 1
        day = date.fromordinal(candidate)
        lunar = to_lunar(day)
        if lunar.day == 1 and lunar.month == 1:
            return day
    raise AssertionError(f"no lunar new year found in {solar_year}")
