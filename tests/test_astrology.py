"""Fortune inputs. Nothing here is stored; these tests pin the derivations."""

from __future__ import annotations

from datetime import date

import pytest

from tientrivutru import astrology as a


@pytest.mark.parametrize(
    "year,can_chi,animal,nap_am,element",
    [
        (1984, "Giáp Tý", "Tý", "Hải Trung Kim", "Kim"),
        (1990, "Canh Ngọ", "Ngọ", "Lộ Bàng Thổ", "Thổ"),
        (1995, "Ất Hợi", "Hợi", "Sơn Đầu Hỏa", "Hỏa"),
        (2000, "Canh Thìn", "Thìn", "Bạch Lạp Kim", "Kim"),
        (2026, "Bính Ngọ", "Ngọ", "Thiên Hà Thủy", "Thủy"),
    ],
)
def test_sexagenary_year_facts(year, can_chi, animal, nap_am, element):
    assert a.can_chi_of_year(year) == can_chi
    assert a.zodiac_animal_of_year(year) == animal
    assert a.nap_am_of_year(year) == nap_am
    assert a.element_of_year(year) == element


def test_sexagenary_cycle_anchors_on_giap_ty():
    assert a.sexagenary_index(1984) == 0
    assert a.sexagenary_index(1984 + 60) == 0
    assert a.can_chi_of_year(1924) == "Giáp Tý"


def test_nap_am_table_covers_the_whole_cycle():
    """30 names, each spanning two years, must tile all 60."""
    assert len(a.NAP_AM) == a.SEXAGENARY_CYCLE // 2
    names = {a.nap_am_of_year(1984 + offset) for offset in range(60)}
    assert names == set(a.NAP_AM)


def test_every_element_is_one_of_the_five():
    for offset in range(60):
        assert a.element_of_year(1984 + offset) in a.ELEMENTS


def test_zodiac_animal_follows_the_lunar_year_not_the_solar_one():
    """Born before Tết 2026 (17 Feb) is still Ất Tỵ, not Bính Ngọ."""
    assert a.read_fortune(date(2026, 2, 16)).zodiac_animal == "Tỵ"
    assert a.read_fortune(date(2026, 2, 17)).zodiac_animal == "Ngọ"
    assert a.read_fortune(date(2026, 1, 5)).can_chi == "Ất Tỵ"


@pytest.mark.parametrize(
    "day,sign",
    [
        (date(1995, 1, 19), "Ma Kết"),
        (date(1995, 1, 20), "Bảo Bình"),
        (date(1995, 3, 20), "Song Ngư"),
        (date(1995, 3, 21), "Bạch Dương"),
        (date(1995, 7, 22), "Cự Giải"),
        (date(1995, 7, 23), "Sư Tử"),
        (date(1995, 12, 21), "Nhân Mã"),
        (date(1995, 12, 22), "Ma Kết"),
    ],
)
def test_western_sign_boundaries(day, sign):
    assert a.western_sign(day) == sign


def test_every_day_of_the_year_has_a_sign():
    day = date(1996, 1, 1)  # leap year, so 29 Feb is covered
    for _ in range(366):
        assert a.western_sign(day) in {name for _, _, name in a.ZODIAC_BOUNDS}
        day = date.fromordinal(day.toordinal() + 1)


@pytest.mark.parametrize(
    "day,expected", [(date(1995, 3, 12), 3), (date(1990, 11, 29), 5), (date(2000, 1, 1), 4)]
)
def test_life_path_number(day, expected):
    assert a.life_path_number(day) == expected


def test_life_path_is_always_a_root_or_master_number():
    day = date(1970, 1, 1)
    for _ in range(400):
        value = a.life_path_number(day)
        assert 1 <= value <= 9 or value in a.MASTER_NUMBERS
        day = date.fromordinal(day.toordinal() + 1)


def test_master_numbers_survive_reduction():
    assert a.reduce_to_root(11) == 11
    assert a.reduce_to_root(22) == 22
    assert a.reduce_to_root(11, keep_master=False) == 2


def test_strip_diacritics_handles_vietnamese_and_d_bar():
    assert a.strip_diacritics("Nguyễn Quốc Đại") == "Nguyen Quoc Dai"
    assert a.strip_diacritics("đường") == "duong"
    assert a.strip_diacritics("ĐỖ") == "DO"


def test_name_number_ignores_spaces_and_punctuation():
    assert a.name_number("Dai") == a.name_number("D a i!")
    assert a.name_number("Nguyễn Quốc Đại") == a.name_number("Nguyen Quoc Dai")


def test_name_number_is_none_without_letters():
    assert a.name_number("") is None
    assert a.name_number("123 !!") is None


def test_pythagorean_rows_cover_the_alphabet():
    letters = "".join(a.PYTHAGOREAN_ROWS)
    assert sorted(letters) == sorted("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert a.letter_value("A") == 1
    assert a.letter_value("I") == 9
    assert a.letter_value("J") == 1
    assert a.letter_value("Z") == 8
    assert a.letter_value("5") is None


def test_guardian_star_needs_gender_and_is_optional():
    """Gender stays optional so nobody has to disclose it."""
    assert a.guardian_star(1995, 2026, None) is None
    assert a.guardian_star(1995, 2026, "khác") is None
    assert a.guardian_star(1995, 2026, "nam") in a.STARS_MALE
    assert a.guardian_star(1995, 2026, "nữ") in a.STARS_FEMALE


def test_guardian_star_cycles_every_nine_years():
    assert a.guardian_star(1995, 2026, "nam") == a.guardian_star(1995 - 9, 2026 - 9, "nam")
    assert len(a.STARS_MALE) == len(a.STARS_FEMALE) == 9


def test_tam_hop_and_tu_hanh_xung_partition_the_animals():
    from tientrivutru.lunar import CHI

    assert sorted(x for g in a.TAM_HOP for x in g) == sorted(CHI)
    assert sorted(x for g in a.TU_HANH_XUNG for x in g) == sorted(CHI)


def test_tam_hop_excludes_self_and_has_two_members():
    for animal in ("Ngọ", "Tý", "Hợi"):
        harmony = a.tam_hop_of(animal)
        assert len(harmony) == 2
        assert animal not in harmony


def test_tu_hanh_xung_excludes_self_and_has_three_members():
    for animal in ("Ngọ", "Dần", "Thìn"):
        clash = a.tu_hanh_xung_of(animal)
        assert len(clash) == 3
        assert animal not in clash


def test_read_fortune_contains_no_identifying_data():
    """The record must be derivations only - never the name or the date itself."""
    fortune = a.read_fortune(date(1995, 3, 12), name="Nguyễn Quốc Đại", gender="nam")
    payload = fortune.as_dict()

    assert "Nguyễn" not in str(payload)
    assert "1995-03-12" not in str(payload)
    assert "name" not in payload
    assert "birth_date" not in payload
    assert payload["name_number"] == a.name_number("Nguyễn Quốc Đại")


def test_read_fortune_without_optional_inputs():
    fortune = a.read_fortune(date(1995, 3, 12))
    assert fortune.name_number is None
    assert fortune.guardian_star is None
    assert fortune.zodiac_animal == "Hợi"


def test_lunar_year_table_shape():
    table = a.lunar_year_table(1990, 1995)

    assert sorted(table) == list(range(1990, 1996))
    assert table[1995]["tet"] == "1995-01-31"
    assert table[1990]["tet"] == "1990-01-27"
    assert table[2026 - 31]["can_chi"] == a.can_chi_of_year(1995)


def test_lunar_year_table_tet_always_falls_in_the_right_window():
    for year, entry in a.lunar_year_table(1930, 2035).items():
        tet = date.fromisoformat(entry["tet"])
        assert tet.year == year
        assert date(year, 1, 21) <= tet <= date(year, 2, 21)
