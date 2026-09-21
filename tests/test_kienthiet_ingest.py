"""Backfill walks the archive a week at a time and must never lose or rewrite a board."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import requests

from tientrivutru import kienthiet_ingest as ingest
from tientrivutru import store
from tientrivutru.sources import kienthiet as kt
from tientrivutru.sources.kienthiet import Board

MN_TIERS = (
    ("db", ("510332",)),
    ("g1", ("89516",)),
    ("g2", ("44895",)),
    ("g3", ("52640", "02439")),
    ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
    ("g5", ("1635",)),
    ("g6", ("9670", "9023", "3404")),
    ("g7", ("516",)),
    ("g8", ("54",)),
)


def board(day: date, province: str = "an-giang", *, special: str = "510332") -> Board:
    tiers = (("db", (special,)), *MN_TIERS[1:])
    return Board(date=day, region="mn", province=province, tiers=tiers)


class FakeWeeks:
    """Stands in for minhngoc: hands back whatever the anchored week is supposed to hold."""

    def __init__(self, pages: dict[date, tuple[Board, ...]], *, fail: set[date] | None = None):
        self.pages = pages
        self.fail = fail or set()
        self.asked: list[date] = []

    def __call__(self, region: str, anchor: date, **_: object) -> tuple[Board, ...]:
        self.asked.append(anchor)
        if anchor in self.fail:
            raise requests.ConnectionError("minhngoc said no")
        return self.pages.get(anchor, ())


@pytest.fixture
def three_provinces_a_day():
    """Two weeks of Miền Nam: three đài every day, the real cadence."""
    pages = {}
    for anchor in (date(2026, 8, 20), date(2026, 8, 13)):
        boards = []
        for offset in range(7):
            day = anchor - timedelta(days=offset)
            for province in ("an-giang", "tay-ninh", "vung-tau"):
                boards.append(board(day, province))
        pages[anchor] = tuple(boards)
    return pages


# --- anchors ------------------------------------------------------------------------


def test_anchors_step_back_a_week_at_a_time_from_the_end():
    anchors = ingest.week_anchors(date(2026, 8, 1), date(2026, 8, 20))
    assert anchors == (date(2026, 8, 20), date(2026, 8, 13), date(2026, 8, 6))


def test_anchors_cover_the_start_even_on_a_partial_week():
    anchors = ingest.week_anchors(date(2026, 8, 15), date(2026, 8, 20))
    assert anchors == (date(2026, 8, 20),)


def test_anchors_refuse_a_backwards_range():
    with pytest.raises(ValueError, match="after"):
        ingest.week_anchors(date(2026, 8, 20), date(2026, 8, 1))


# --- ingest -------------------------------------------------------------------------


def test_a_backfill_stores_every_board_the_pages_carried(monkeypatch, three_provinces_a_day):
    fake = FakeWeeks(three_provinces_a_day)
    monkeypatch.setattr(kt, "fetch_week", fake)

    report = ingest.ingest_region(
        "mn", start=date(2026, 8, 7), end=date(2026, 8, 20), pause=0
    )

    assert report.ok
    assert report.added == 14 * 3
    assert len(store.read_boards("mn")) == 14 * 3


def test_boards_outside_the_range_are_not_stored(monkeypatch, three_provinces_a_day):
    """A week page overshoots the range at both ends. Only what was asked for lands."""
    monkeypatch.setattr(kt, "fetch_week", FakeWeeks(three_provinces_a_day))

    ingest.ingest_region("mn", start=date(2026, 8, 18), end=date(2026, 8, 20), pause=0)

    assert {b.date for b in store.read_boards("mn")} == {
        date(2026, 8, 18),
        date(2026, 8, 19),
        date(2026, 8, 20),
    }


def test_a_second_run_asks_for_nothing(monkeypatch, three_provinces_a_day):
    fake = FakeWeeks(three_provinces_a_day)
    monkeypatch.setattr(kt, "fetch_week", fake)
    span = {"start": date(2026, 8, 7), "end": date(2026, 8, 20), "pause": 0}

    ingest.ingest_region("mn", **span)
    asked_first = len(fake.asked)
    second = ingest.ingest_region("mn", **span)

    assert asked_first == 2
    assert len(fake.asked) == asked_first
    assert second.added == 0
    assert second.skipped_weeks == 2


def test_resume_off_refetches_and_still_adds_nothing(monkeypatch, three_provinces_a_day):
    """Merging is idempotent, so a forced re-run costs requests and changes no data."""
    fake = FakeWeeks(three_provinces_a_day)
    monkeypatch.setattr(kt, "fetch_week", fake)
    span = {"start": date(2026, 8, 7), "end": date(2026, 8, 20), "pause": 0}

    ingest.ingest_region("mn", **span)
    before = store.read_boards("mn")
    again = ingest.ingest_region("mn", resume=False, **span)

    assert len(fake.asked) == 4
    assert again.added == 0
    assert store.read_boards("mn") == before


def test_a_failed_week_is_reported_and_the_rest_still_land(
    monkeypatch, three_provinces_a_day
):
    fake = FakeWeeks(three_provinces_a_day, fail={date(2026, 8, 13)})
    monkeypatch.setattr(kt, "fetch_week", fake)

    report = ingest.ingest_region(
        "mn", start=date(2026, 8, 7), end=date(2026, 8, 20), pause=0
    )

    assert not report.ok
    assert [f.anchor for f in report.failures] == [date(2026, 8, 13)]
    assert report.added == 7 * 3
    assert len(store.read_boards("mn")) == 7 * 3


def test_a_failure_never_silently_becomes_success(monkeypatch, three_provinces_a_day):
    monkeypatch.setattr(kt, "fetch_week", FakeWeeks({}, fail={date(2026, 8, 20)}))

    report = ingest.ingest_region(
        "mn", start=date(2026, 8, 14), end=date(2026, 8, 20), pause=0
    )

    assert report.failures[0].error == "minhngoc said no"
    assert report.added == 0


def test_ingest_rejects_an_unknown_region():
    with pytest.raises(KeyError, match="mien-tay"):
        ingest.ingest_region("mien-tay", start=date(2026, 8, 1), end=date(2026, 8, 2))


# --- gap reporting ------------------------------------------------------------------


def test_missing_days_lists_what_the_archive_never_delivered(
    monkeypatch, three_provinces_a_day
):
    monkeypatch.setattr(kt, "fetch_week", FakeWeeks(three_provinces_a_day))
    ingest.ingest_region("mn", start=date(2026, 8, 14), end=date(2026, 8, 20), pause=0)

    gaps = ingest.missing_days("mn", start=date(2026, 8, 12), end=date(2026, 8, 20))

    assert gaps == (date(2026, 8, 12), date(2026, 8, 13))


def test_a_day_short_of_its_dai_counts_as_missing(monkeypatch):
    """Two đài on a three-đài day is a gap, not a result."""
    day = date(2026, 8, 20)
    store.write_boards("mn", [board(day, "an-giang"), board(day, "tay-ninh")])

    assert ingest.missing_days("mn", start=day, end=day) == (day,)
