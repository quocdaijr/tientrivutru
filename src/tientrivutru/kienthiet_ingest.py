"""Filling the kiến thiết archive without hammering minhngoc.

A weekly page carries every đài of a region for seven days in one request: 22 boards for
Miền Nam, 16-17 for Miền Trung, 7 for Miền Bắc. Walking the archive a week at a time is
roughly thirty times cheaper than asking for each đài each day, which is the difference
between a six-minute backfill and a four-hour one.

Runs are resumable. A week already covered is skipped without a request, and
`store.merge_boards` never rewrites a board it already has, so an interrupted backfill
can simply be run again. Coverage is judged from the data rather than a state file, so a
week containing a day nobody drew - Tết, mostly - is re-requested on every run. That is a
handful of wasted requests against not having to keep a sidecar honest.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

import requests

from . import store
from .sources import kienthiet as kt

WEEK = 7
DEFAULT_PAUSE_SECONDS = 0.5
FLUSH_EVERY = 500
"""Boards buffered before a write. Storage rewrites the whole region file each merge, so
flushing per week turns a backfill quadratic. A crash re-fetches at most this much."""

MIN_BOARDS_PER_DAY = {"mb": 1, "mn": 3, "mt": 2}
"""Fewest đài a region draws on its quietest day - a resume hint, not an invariant.

Merging is idempotent, so a wrong guess here costs a redundant request, never data.
"""


@dataclass(frozen=True, slots=True)
class WeekResult:
    """What one weekly page yielded. `added` is tallied at flush time, not here."""

    anchor: date
    fetched: int
    added: int
    error: str | None = None


@dataclass(slots=True)
class IngestReport:
    region: str
    requested_weeks: int = 0
    skipped_weeks: int = 0
    added: int = 0
    total: int = 0
    failures: list[WeekResult] = field(default_factory=list)
    no_draw: list[tuple[date, str]] = field(default_factory=list)
    """Days the đài genuinely did not draw - Tết, mostly. Reported, never stored."""

    @property
    def ok(self) -> bool:
        return not self.failures


def week_anchors(start: date, end: date) -> tuple[date, ...]:
    """Anchors to request, newest first. A page anchored at `d` covers d-6 .. d."""
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    anchors = []
    cursor = end
    while cursor >= start:
        anchors.append(cursor)
        cursor -= timedelta(days=WEEK)
    return tuple(anchors)


def _covered(anchor: date, have: dict[date, int], floor: int) -> bool:
    """True when every day the anchored week covers already has enough boards."""
    return all(have.get(anchor - timedelta(days=offset), 0) >= floor for offset in range(WEEK))


def ingest_region(
    region: str,
    *,
    start: date,
    end: date,
    resume: bool = True,
    pause: float = DEFAULT_PAUSE_SECONDS,
    session: requests.Session | None = None,
    on_week: Callable[[WeekResult], None] | None = None,
) -> IngestReport:
    """Walk a region's archive backwards a week at a time, merging as it goes."""
    if region not in kt.REGIONS:
        raise KeyError(f"Unknown region {region!r}. Known: {', '.join(sorted(kt.REGIONS))}")

    report = IngestReport(region=region)
    floor = MIN_BOARDS_PER_DAY[region]
    have: dict[date, int] = {}
    for board in store.read_boards(region):
        have[board.date] = have.get(board.date, 0) + 1
    pending: list[kt.Board] = []

    for anchor in week_anchors(start, end):
        if resume and _covered(anchor, have, floor):
            report.skipped_weeks += 1
            continue

        report.requested_weeks += 1
        try:
            boards = kt.fetch_week(
                region,
                anchor,
                session=session,
                on_no_draw=lambda day, slug, _why: report.no_draw.append((day, slug)),
            )
        except (requests.RequestException, ValueError) as exc:
            result = WeekResult(anchor=anchor, fetched=0, added=0, error=str(exc))
            report.failures.append(result)
        else:
            wanted = [b for b in boards if start <= b.date <= end]
            pending.extend(wanted)
            for board in wanted:
                have[board.date] = have.get(board.date, 0) + 1
            result = WeekResult(anchor=anchor, fetched=len(wanted), added=0)

        if len(pending) >= FLUSH_EVERY:
            report.added += _flush(region, pending, report)
        if on_week is not None:
            on_week(result)
        if pause:
            time.sleep(pause)

    report.added += _flush(region, pending, report)
    report.total = report.total or len(store.read_boards(region))
    return report


def _flush(region: str, pending: list[kt.Board], report: IngestReport) -> int:
    """Write what has been collected so far and empty the buffer."""
    if not pending:
        return 0
    added, total = store.merge_boards(region, pending)
    report.total = total
    pending.clear()
    return added


def ingest_days(
    region: str,
    days: Iterable[date],
    *,
    pause: float = DEFAULT_PAUSE_SECONDS,
    session: requests.Session | None = None,
) -> IngestReport:
    """Patch specific missing days đài by đài. The narrow tool, for gaps a week page missed."""
    report = IngestReport(region=region)
    fetched: list[kt.Board] = []
    for day in days:
        for province in kt.provinces_in(region):
            report.requested_weeks += 1
            try:
                fetched.append(kt.fetch_board(province.slug, day, session=session))
            except (requests.RequestException, ValueError) as exc:
                report.failures.append(WeekResult(anchor=day, fetched=0, added=0, error=str(exc)))
            if pause:
                time.sleep(pause)
    added, total = store.merge_boards(region, fetched)
    report.added, report.total = added, total
    return report


def missing_days(
    region: str,
    *,
    start: date,
    end: date,
    known_no_draw: Iterable[date] = (),
) -> tuple[date, ...]:
    """Days in range with fewer boards than the region's quietest day should have.

    `known_no_draw` lets a caller subtract the holidays it just learned about, so a
    genuine hole in the archive is not buried among Tết.
    """
    floor = MIN_BOARDS_PER_DAY[region]
    have: dict[date, int] = {}
    for board in store.read_boards(region):
        have[board.date] = have.get(board.date, 0) + 1
    holidays = set(known_no_draw)
    span = (end - start).days
    return tuple(
        day
        for day in (start + timedelta(days=offset) for offset in range(span + 1))
        if have.get(day, 0) < floor and day not in holidays
    )
