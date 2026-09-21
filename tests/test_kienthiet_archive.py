"""What the committed kiến thiết archive is allowed to be missing.

A gap in lottery history is not automatically a bug - đài genuinely stop drawing. But
"the ingest quietly dropped a week" and "the country suspended the lottery" look
identical in a JSONL file, so every gap in the archive is enumerated here and has to be
one of the two known reasons:

  * Tết. Miền Bắc does not draw over the lunar new year; the southern and central đài do.
  * COVID-19. Nationwide suspension 01-22/04/2020, and the long southern lockdown from
    09/07/2021 to 21/10/2021, with shorter central windows in mid-2021.

Anything else is the ingest losing data, and this file is what makes that fail loudly
instead of becoming a slightly emptier heatmap nobody notices.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tientrivutru import kienthiet_ingest as ingest
from tientrivutru.lunar import to_lunar
from tientrivutru.sources import kienthiet as kt

REPO_DATA = Path(__file__).resolve().parents[1] / "data" / "boards"

# Lunar days Miền Bắc skips over Tết. The window is read from the lunar calendar rather
# than a list of dates so it keeps working in 2027 without anyone editing this file.
TET_DAYS = frozenset({(12, 29), (12, 30), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5)})

SUSPENSIONS = {
    "mb": ((date(2020, 4, 1), date(2020, 4, 22)),),
    "mn": (
        (date(2020, 4, 1), date(2020, 4, 28)),
        (date(2021, 7, 9), date(2021, 10, 21)),
    ),
    "mt": (
        (date(2020, 4, 1), date(2020, 4, 23)),
        (date(2021, 7, 27), date(2021, 8, 18)),
    ),
}

EXPECTED_END = date(2026, 8, 24)


def _archive(region: str) -> Path:
    return REPO_DATA / f"{region}.jsonl"


def _explained(region: str, day: date) -> bool:
    moon = to_lunar(day)
    if region == "mb" and (moon.month, moon.day) in TET_DAYS:
        return True
    return any(start <= day <= end for start, end in SUSPENSIONS[region])


@pytest.mark.parametrize("region", ("mb", "mn", "mt"))
def test_every_region_has_a_committed_archive(region):
    assert _archive(region).exists(), f"data/boards/{region}.jsonl is missing"


@pytest.mark.parametrize("region", ("mb", "mn", "mt"))
def test_every_gap_in_the_archive_has_a_reason(region, monkeypatch):
    """The test this file exists for: a silently lost week must not pass as a holiday."""
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))

    gaps = ingest.missing_days(
        region, start=kt.ARCHIVE_START[region], end=EXPECTED_END
    )
    unexplained = [day.isoformat() for day in gaps if not _explained(region, day)]

    assert unexplained == []


@pytest.mark.parametrize("region", ("mb", "mn", "mt"))
def test_the_archive_reaches_the_expected_span(region, monkeypatch):
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))
    from tientrivutru import store

    boards = store.read_boards(region)
    assert boards
    assert min(b.date for b in boards) <= kt.ARCHIVE_START[region] + _slack(region)
    assert max(b.date for b in boards) >= EXPECTED_END


def _slack(region: str):
    """Miền Nam and Miền Trung start on whatever day their first đài drew, not 1 January."""
    from datetime import timedelta

    return timedelta(days=0 if region == "mb" else 200)


@pytest.mark.parametrize("region", ("mb", "mn", "mt"))
def test_no_board_in_the_archive_is_the_all_zero_filler(region, monkeypatch):
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))
    from tientrivutru import store

    for board in store.read_boards(region):
        assert set(board.tails) != {0}, f"{board.province} {board.date}"


@pytest.mark.parametrize("region", ("mb", "mn", "mt"))
def test_every_board_belongs_to_its_region_and_a_known_dai(region, monkeypatch):
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))
    from tientrivutru import store

    for board in store.read_boards(region):
        assert board.region == region
        assert kt.PROVINCES[board.province].region == region


# --- the six-digit era --------------------------------------------------------------
# Miền Trung ran five-digit đặc biệt until 2017-03-31 and six from 2017-04-01. Miền Nam
# had already switched before the archive starts. A six-digit ticket cannot settle a
# five-digit board, so those 205 boards feed the honest layer and are skipped by the vé
# scorer - which is a decision worth pinning, not an accident worth rediscovering.

SIX_DIGIT_FROM = {"mn": date(2017, 1, 1), "mt": date(2017, 4, 1)}


@pytest.mark.parametrize("region", ("mn", "mt"))
def test_the_special_is_six_digits_from_the_switchover_onwards(region, monkeypatch):
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))
    from tientrivutru import store

    widths = {
        len(b.special) for b in store.read_boards(region) if b.date >= SIX_DIGIT_FROM[region]
    }
    assert widths == {6}


def test_mien_trung_still_carries_its_five_digit_era(monkeypatch):
    """Kept, not discarded: chi-square wants every draw, only the ticket scorer cannot."""
    monkeypatch.setenv("TIENTRIVUTRU_DATA_DIR", str(REPO_DATA.parent))
    from tientrivutru import store

    early = [b for b in store.read_boards("mt") if b.date < SIX_DIGIT_FROM["mt"]]
    assert early
    assert {len(b.special) for b in early} == {5}
