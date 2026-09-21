"""Xổ số kiến thiết — the traditional provincial lottery, all three regions.

Source: minhngoc.net.vn. Two shapes are served, both parsed here:

  * `/getkqxs/<đài>/<dd-mm-yyyy>.js` — one board, ~6 KB. Verified back to 2005-10-01
    for Miền Bắc and 2010 for Miền Nam / Miền Trung.
  * `/ket-qua-xo-so/<miền>/<dd-mm-yyyy>.html` — a whole week of a region in one
    request (22 boards for Miền Nam, 16 for Miền Trung). The backfill path.

This deliberately does NOT reuse `Draw`, for the same reasons `sources/xsmb.py` gives:
a prize board is not a pick-N. It does not reuse `XsmbDraw` either, because that record
throws away everything but the last two digits — which is exactly what makes it unable
to settle a ticket. A board here keeps the printed number, as a string, at its printed
width. `Board.tails` derives the 00..99 lô space on demand, and `store.read_xsmb()`
rebuilds the old record from it, so nothing downstream had to change.

Widths matter and are validated: Miền Nam / Miền Trung specials were five digits until
roughly 2011 and six afterwards, so `db` accepts both. Everything else is fixed. A board
that does not match its region's shape is refused at the boundary rather than stored.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from types import MappingProxyType

import requests

from .. import stats

BASE_URL = "https://www.minhngoc.net.vn"
SOURCE_LABEL = "minhngoc.net.vn"
DEFAULT_TIMEOUT = 30

DIGIT_SPACE = 100
"""The lô space: last two digits of any prize number, 00..99, zero included."""


@dataclass(frozen=True, slots=True)
class TierSpec:
    """One row of the printed board."""

    key: str
    display: str
    count: int
    widths: frozenset[int]


@dataclass(frozen=True, slots=True)
class RegionSpec:
    key: str
    display: str
    path: str
    tiers: tuple[TierSpec, ...]
    prophesiable: bool

    @property
    def slots(self) -> int:
        return sum(tier.count for tier in self.tiers)

    @property
    def tier_keys(self) -> tuple[str, ...]:
        return tuple(tier.key for tier in self.tiers)

    def tier(self, key: str) -> TierSpec:
        for tier in self.tiers:
            if tier.key == key:
                return tier
        raise KeyError(f"{self.key} has no tier {key!r}")


_FIVE = frozenset({5})
_FOUR = frozenset({4})

# Miền Nam and Miền Trung print the same board: 18 numbers, giải tám down to đặc biệt.
_SOUTHERN_TIERS = (
    TierSpec("db", "Giải đặc biệt", 1, frozenset({5, 6})),
    TierSpec("g1", "Giải nhất", 1, _FIVE),
    TierSpec("g2", "Giải nhì", 1, _FIVE),
    TierSpec("g3", "Giải ba", 2, _FIVE),
    TierSpec("g4", "Giải tư", 7, _FIVE),
    TierSpec("g5", "Giải năm", 1, _FOUR),
    TierSpec("g6", "Giải sáu", 3, _FOUR),
    TierSpec("g7", "Giải bảy", 1, frozenset({3})),
    TierSpec("g8", "Giải tám", 1, frozenset({2})),
)

# Miền Bắc is a different board entirely: 27 numbers, no eighth prize.
_NORTHERN_TIERS = (
    TierSpec("db", "Giải đặc biệt", 1, _FIVE),
    TierSpec("g1", "Giải nhất", 1, _FIVE),
    TierSpec("g2", "Giải nhì", 2, _FIVE),
    TierSpec("g3", "Giải ba", 6, _FIVE),
    TierSpec("g4", "Giải tư", 4, _FOUR),
    TierSpec("g5", "Giải năm", 6, _FOUR),
    TierSpec("g6", "Giải sáu", 3, frozenset({3})),
    TierSpec("g7", "Giải bảy", 4, frozenset({2})),
)

REGIONS: Mapping[str, RegionSpec] = MappingProxyType(
    {
        "mn": RegionSpec("mn", "Miền Nam", "mien-nam", _SOUTHERN_TIERS, prophesiable=True),
        "mt": RegionSpec("mt", "Miền Trung", "mien-trung", _SOUTHERN_TIERS, prophesiable=True),
        "mb": RegionSpec("mb", "Miền Bắc", "mien-bac", _NORTHERN_TIERS, prophesiable=False),
    }
)


ARCHIVE_START: Mapping[str, date] = MappingProxyType(
    {
        # The oldest Miền Bắc board minhngoc serves, and the first row of data/xsmb.jsonl.
        "mb": date(2005, 10, 1),
        # Southern and central boards go back to 2010, but the five-digit special era ends
        # around 2011 and the ticket price changed with it. 2017 is a knob, not a limit.
        "mn": date(2017, 1, 1),
        "mt": date(2017, 1, 1),
    }
)


@dataclass(frozen=True, slots=True)
class Province:
    slug: str
    display: str
    region: str


def _provinces(region: str, entries: Mapping[str, str]) -> dict[str, Province]:
    return {slug: Province(slug, display, region) for slug, display in entries.items()}


PROVINCES: Mapping[str, Province] = MappingProxyType(
    {
        **_provinces(
            "mn",
            {
                "an-giang": "An Giang",
                "bac-lieu": "Bạc Liêu",
                "ben-tre": "Bến Tre",
                "binh-duong": "Bình Dương",
                "binh-phuoc": "Bình Phước",
                "binh-thuan": "Bình Thuận",
                "ca-mau": "Cà Mau",
                "can-tho": "Cần Thơ",
                "da-lat": "Đà Lạt",
                "dong-nai": "Đồng Nai",
                "dong-thap": "Đồng Tháp",
                "hau-giang": "Hậu Giang",
                "kien-giang": "Kiên Giang",
                "long-an": "Long An",
                "soc-trang": "Sóc Trăng",
                "tay-ninh": "Tây Ninh",
                "tien-giang": "Tiền Giang",
                "tp-hcm": "TP. HCM",
                "tra-vinh": "Trà Vinh",
                "vinh-long": "Vĩnh Long",
                "vung-tau": "Vũng Tàu",
            },
        ),
        **_provinces(
            "mt",
            {
                "binh-dinh": "Bình Định",
                "da-nang": "Đà Nẵng",
                "dak-lak": "Đắk Lắk",
                "dak-nong": "Đắk Nông",
                "gia-lai": "Gia Lai",
                "khanh-hoa": "Khánh Hòa",
                "kon-tum": "Kon Tum",
                "ninh-thuan": "Ninh Thuận",
                "phu-yen": "Phú Yên",
                "quang-binh": "Quảng Bình",
                "quang-nam": "Quảng Nam",
                "quang-ngai": "Quảng Ngãi",
                "quang-tri": "Quảng Trị",
                "thua-thien-hue": "Huế",
            },
        ),
        **_provinces("mb", {"mien-bac": "Miền Bắc"}),
    }
)


def get_province(slug: str) -> Province:
    try:
        return PROVINCES[slug]
    except KeyError:
        raise KeyError(f"Unknown đài {slug!r}. Known đài: {', '.join(sorted(PROVINCES))}") from None


def provinces_in(region: str) -> tuple[Province, ...]:
    if region not in REGIONS:
        raise KeyError(f"Unknown region {region!r}. Known: {', '.join(sorted(REGIONS))}")
    return tuple(p for p in PROVINCES.values() if p.region == region)


@dataclass(frozen=True, slots=True)
class Board:
    """One đài's full prize board for one day, numbers kept as printed."""

    date: date
    region: str
    province: str
    tiers: tuple[tuple[str, tuple[str, ...]], ...]
    ticket_type: str | None = None
    source: str = SOURCE_LABEL

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "tiers", tuple((key, tuple(values)) for key, values in self.tiers)
        )
        spec = REGIONS.get(self.region)
        if spec is None:
            raise ValueError(f"{self.province} {self.date}: unknown region {self.region!r}")
        if PROVINCES[self.province].region != self.region:
            raise ValueError(
                f"{self.province} belongs to {PROVINCES[self.province].region}, "
                f"not {self.region}"
            )
        where = f"{self.province} {self.date}"
        if self.tier_keys != spec.tier_keys:
            raise ValueError(
                f"{where}: board tiers {self.tier_keys} do not match "
                f"{spec.display} {spec.tier_keys}"
            )
        for tier in spec.tiers:
            values = dict(self.tiers)[tier.key]
            if len(values) != tier.count:
                raise ValueError(
                    f"{where}: tier {tier.key} expected {tier.count} numbers, got {len(values)}"
                )
            for value in values:
                if not value.isdigit():
                    raise ValueError(f"{where}: tier {tier.key} value {value!r} is not digits")
                if len(value) not in tier.widths:
                    raise ValueError(
                        f"{where}: tier {tier.key} value {value!r} is {len(value)} digits, "
                        f"expected {sorted(tier.widths)}"
                    )

    @property
    def tier_keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.tiers)

    @property
    def spec(self) -> RegionSpec:
        return REGIONS[self.region]

    @property
    def special(self) -> str:
        return self.tiers[0][1][0]

    @property
    def numbers(self) -> tuple[str, ...]:
        """Every printed number, in board order, đặc biệt first."""
        return tuple(value for _, values in self.tiers for value in values)

    @property
    def tails(self) -> tuple[int, ...]:
        """The lô view: last two digits of every slot. Zero is a legal value."""
        return tuple(int(value[-2:]) for value in self.numbers)

    @property
    def key(self) -> tuple[date, str]:
        return (self.date, self.province)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "date": self.date.isoformat(),
            "region": self.region,
            "province": self.province,
            "tiers": [[key, list(values)] for key, values in self.tiers],
        }
        if self.ticket_type:
            payload["ticket_type"] = self.ticket_type
        payload["source"] = self.source
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Board:
        tiers = tuple(
            (str(key), tuple(str(v) for v in values))
            for key, values in payload["tiers"]  # type: ignore[union-attr]
        )
        ticket_type = payload.get("ticket_type")
        return cls(
            date=date.fromisoformat(str(payload["date"])),
            region=str(payload["region"]),
            province=str(payload["province"]),
            tiers=tiers,
            ticket_type=str(ticket_type) if ticket_type else None,
            source=str(payload.get("source", SOURCE_LABEL)),
        )


# --- parsing ------------------------------------------------------------------------

# `giaidbl` / `giai4l` are the label column. Requiring the closing quote keeps them out.
_CELL = re.compile(r'class="(giaidb|giai[1-8])"[^>]*>(.*?)</td>', re.DOTALL)
_DIGIT_RUN = re.compile(r"\d+")
_TICKET_TYPE = re.compile(r"Loại vé:\s*([A-Z0-9\-]+)", re.IGNORECASE)
_CLASS_TO_TIER = {"giaidb": "db", **{f"giai{n}": f"g{n}" for n in range(1, 9)}}


class NoDraw(ValueError):
    """Raised for a day the đài did not draw at all.

    minhngoc marks these by printing `Tết` where the giải đặc biệt goes and a bare `0`
    in every other prize cell. A parser that shrugged and took the zeros would file
    twenty-seven fake 00s into the frequency table, which is worse than a gap - so a
    non-numeric đặc biệt means no draw, loudly.
    """


def _extract_tiers(markup: str) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    """Pull tier -> numbers out of a result table, whichever way round it is printed.

    Also returns the tiers whose cell was present but carried no digits, which is how a
    no-draw day and a label cell both look.
    """
    found: dict[str, tuple[str, ...]] = {}
    blank: set[str] = set()
    for class_name, cell in _CELL.findall(markup):
        tier = _CLASS_TO_TIER[class_name]
        numbers = tuple(_DIGIT_RUN.findall(cell))
        if not numbers:
            blank.add(tier)
            continue
        found.setdefault(tier, numbers)
    return found, blank - set(found)


def parse_board(markup: str, *, province: str, on: date) -> Board:
    """Build a Board from one đài's result table. Raises ValueError on any mismatch."""
    known = get_province(province)
    spec = REGIONS[known.region]
    text = html.unescape(markup)
    found, blank = _extract_tiers(text)

    if "db" in blank:
        raise NoDraw(f"{province} {on}: giải đặc biệt carries no number — đài không quay")
    missing = [key for key in spec.tier_keys if key not in found]
    if missing:
        raise ValueError(f"{province} {on}: board is missing tier(s) {', '.join(missing)}")

    ticket = _TICKET_TYPE.search(text)
    return Board(
        date=on,
        region=known.region,
        province=province,
        tiers=tuple((key, found[key]) for key in spec.tier_keys),
        ticket_type=ticket.group(1) if ticket else None,
    )


_DAY_BLOCK = re.compile(r'<div class="box_kqxs')
_PAGE_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_PROVINCE_LINK = re.compile(r'href="/xo-so-mien-(?:nam|trung|bac)/([a-z0-9\-]+)\.html"')
_BOARD_TABLE = re.compile(r'class="rightcl"')


def parse_region_week(
    markup: str,
    *,
    region: str,
    on_no_draw: Callable[[date, str, str], None] | None = None,
) -> tuple[Board, ...]:
    """Parse a region's weekly page into every board it carries.

    One request yields a week: 22 boards for Miền Nam, 16 for Miền Trung. Days or đài
    the page does not carry are simply absent - the caller decides what a gap means.
    Days nobody drew (Tết) are reported through `on_no_draw` rather than aborting the
    week, because one holiday must not cost the other six days on the page.
    """
    if region not in REGIONS:
        raise KeyError(f"Unknown region {region!r}")
    text = html.unescape(markup)
    only = provinces_in(region)
    boards: list[Board] = []

    def take(fragment: str, slug: str, on: date) -> None:
        try:
            boards.append(parse_board(fragment, province=slug, on=on))
        except NoDraw as exc:
            if on_no_draw is not None:
                on_no_draw(on, slug, str(exc))

    for block in _DAY_BLOCK.split(text)[1:]:
        stamp = _PAGE_DATE.search(block)
        if stamp is None:
            continue
        day, month, year = (int(part) for part in stamp.groups())
        on = date(year, month, day)
        if len(only) == 1:
            # Miền Bắc has a single đài, so its blocks carry no province link.
            take(block, only[0].slug, on)
            continue
        for chunk in _BOARD_TABLE.split(block)[1:]:
            link = _PROVINCE_LINK.search(chunk)
            if link is None or link.group(1) not in PROVINCES:
                continue
            slug = link.group(1)
            if PROVINCES[slug].region != region:
                continue
            take(chunk, slug, on)
    return tuple(sorted(boards, key=lambda b: b.key))


# --- fetching -----------------------------------------------------------------------


def _vn_date(on: date) -> str:
    return on.strftime("%d-%m-%Y")


def board_url(province: str, on: date | None = None) -> str:
    """A single đài's board. Without a date, minhngoc serves that đài's latest draw."""
    get_province(province)
    if on is None:
        return f"{BASE_URL}/getkqxs/{province}.js"
    return f"{BASE_URL}/getkqxs/{province}/{_vn_date(on)}.js"


def week_url(region: str, on: date) -> str:
    """A whole week of one region, ending on `on`."""
    if region not in REGIONS:
        raise KeyError(f"Unknown region {region!r}")
    return f"{BASE_URL}/ket-qua-xo-so/{REGIONS[region].path}/{_vn_date(on)}.html"


def _get(url: str, *, timeout: int, session: requests.Session | None) -> str:
    getter = session.get if session is not None else requests.get
    response = getter(url, timeout=timeout, headers={"User-Agent": "tientrivutru/1.0"})
    response.raise_for_status()
    return response.text


def fetch_board(
    province: str,
    on: date | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    session: requests.Session | None = None,
) -> Board:
    markup = _get(board_url(province, on), timeout=timeout, session=session)
    if on is None:
        stamp = _PAGE_DATE.search(html.unescape(markup))
        if stamp is None:
            raise ValueError(f"{province}: latest board carries no date")
        day, month, year = (int(part) for part in stamp.groups())
        on = date(year, month, day)
    return parse_board(markup, province=province, on=on)


def fetch_week(
    region: str,
    on: date,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    session: requests.Session | None = None,
    on_no_draw: Callable[[date, str, str], None] | None = None,
) -> tuple[Board, ...]:
    markup = _get(week_url(region, on), timeout=timeout, session=session)
    return parse_region_week(markup, region=region, on_no_draw=on_no_draw)


# --- statistics ---------------------------------------------------------------------


def frequency(boards: Iterable[Board]) -> Mapping[int, int]:
    """How often each 00..99 tail appeared across every prize slot."""
    counts = dict.fromkeys(range(DIGIT_SPACE), 0)
    for board in boards:
        for tail in board.tails:
            counts[tail] += 1
    return MappingProxyType(counts)


def chi_square_uniform(boards: Sequence[Board]) -> stats.ChiSquareResult:
    """Test H0: all 100 two-digit tails are equally likely."""
    if not boards:
        raise ValueError("cannot test uniformity with no boards")
    counts = frequency(boards)
    observations = sum(counts.values())
    expected = observations / DIGIT_SPACE
    statistic = sum((count - expected) ** 2 / expected for count in counts.values())
    df = DIGIT_SPACE - 1
    return stats.ChiSquareResult(
        statistic=statistic,
        degrees_of_freedom=df,
        p_value=stats.chi_square_sf(statistic, df),
        observations=observations,
    )


def latest_board(boards: Sequence[Board], province: str | None = None) -> Board | None:
    candidates = [b for b in boards if province is None or b.province == province]
    if not candidates:
        return None
    return max(candidates, key=lambda b: b.date)


SCHEDULE_WEEKS = 8
"""How much recent history the đài calendar is derived from.

Long enough to see every weekday several times, short enough that a province which
changed its day is not remembered on both. The calendar is derived rather than hardcoded
because provinces do move - and a hardcoded table would quietly go stale instead.
"""


def schedule_from(
    boards: Sequence[Board], *, weeks: int = SCHEDULE_WEEKS
) -> Mapping[int, tuple[str, ...]]:
    """Weekday (Mon=0) -> the đài that drew on it recently, newest history only."""
    if not boards:
        return MappingProxyType({})
    newest = max(b.date for b in boards)
    since = newest - timedelta(weeks=weeks)
    by_weekday: dict[int, set[str]] = {}
    for board in boards:
        if board.date >= since:
            by_weekday.setdefault(board.date.weekday(), set()).add(board.province)
    return MappingProxyType({day: tuple(sorted(names)) for day, names in by_weekday.items()})


def dai_on(boards: Sequence[Board], day: date, *, weeks: int = SCHEDULE_WEEKS) -> tuple[str, ...]:
    """Which đài draw on a given day, according to what recently happened."""
    return schedule_from(boards, weeks=weeks).get(day.weekday(), ())


LOOKAHEAD_DAYS = 14


def next_draw_date(
    boards: Sequence[Board], province: str, *, on: date, weeks: int = SCHEDULE_WEEKS
) -> date | None:
    """The đài's next unfinished draw day, from `on` inclusive.

    A day the đài has already drawn is skipped rather than returned, because prophesying
    a settled draw is exactly what the append-only guard exists to refuse.
    """
    get_province(province)
    calendar = schedule_from(boards, weeks=weeks)
    drawn = {b.date for b in boards if b.province == province}
    for offset in range(LOOKAHEAD_DAYS):
        day = on + timedelta(days=offset)
        if province in calendar.get(day.weekday(), ()) and day not in drawn:
            return day
    return None


def summarise(boards: Sequence[Board]) -> dict[str, object]:
    return {
        "count": len(boards),
        "first_date": min(b.date for b in boards).isoformat() if boards else None,
        "last_date": max(b.date for b in boards).isoformat() if boards else None,
        "observations": sum(len(b.numbers) for b in boards),
        "provinces": len({b.province for b in boards}),
    }
