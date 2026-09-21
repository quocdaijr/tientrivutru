"""XSMB is now a view over the Miền Bắc boards. These tests pin that nothing moved.

`data/xsmb.jsonl` holds 21 years of two-digit tails from a different upstream
(khiemdoan/vietnam-lottery-xsmb-analysis). `data/boards/mb.jsonl` holds the same draws
as full printed numbers from minhngoc. Two independent sources, one shared past: if the
tails derived from the boards do not reproduce the legacy file row for row, one of them
is wrong and the migration must not land.

The offline test is the gate and runs against whatever is committed. The network test
spot-checks live minhngoc against the legacy file and is opt-in via
TIENTRIVUTRU_NETWORK_TESTS=1, because CI must not depend on someone else's uptime.
"""

from __future__ import annotations

import json
import os
import random
from datetime import date
from pathlib import Path

import pytest

from tientrivutru.sources import kienthiet as kt
from tientrivutru.sources.xsmb import PRIZE_SLOTS, XsmbDraw

REPO_DATA = Path(__file__).resolve().parents[1] / "data"
LEGACY = REPO_DATA / "xsmb.jsonl"
BOARDS = REPO_DATA / "boards" / "mb.jsonl"
NETWORK = os.environ.get("TIENTRIVUTRU_NETWORK_TESTS") == "1"


def _legacy_rows() -> dict[date, XsmbDraw]:
    rows = {}
    with LEGACY.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                draw = XsmbDraw.from_dict(json.loads(line))
                rows[draw.date] = draw
    return rows


def _board_rows() -> dict[date, kt.Board]:
    rows = {}
    with BOARDS.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                board = kt.Board.from_dict(json.loads(line))
                rows[board.date] = board
    return rows


def test_the_legacy_file_is_still_here_to_check_against():
    """Deleting it would delete the only independent witness to 21 years of results."""
    assert LEGACY.exists()
    assert len(_legacy_rows()) > 7_000


# The two sources disagree on exactly these days, and no third archive within reach can
# break the tie. minhngoc and khiemdoan return completely different boards for them; the
# t-k-minh mirror is not an independent witness (it carries khiemdoan's numbers verbatim).
# They are named here rather than filtered away, so the disagreement stays visible and any
# NEW disagreement fails the build.
DISPUTED = (date(2006, 6, 17), date(2006, 9, 21))


def _tier_multisets(board: kt.Board) -> list[tuple[int, ...]]:
    """Tails per tier, sorted. Order inside a tier is presentation, not result."""
    out, cursor = [], 0
    for _, values in board.tiers:
        out.append(tuple(sorted(board.tails[cursor : cursor + len(values)])))
        cursor += len(values)
    return out


def _legacy_tier_multisets(board: kt.Board, draw: XsmbDraw) -> list[tuple[int, ...]]:
    out, cursor = [], 0
    for _, values in board.tiers:
        out.append(tuple(sorted(draw.prizes[cursor : cursor + len(values)])))
        cursor += len(values)
    return out


@pytest.mark.skipif(not BOARDS.exists(), reason="Miền Bắc boards not ingested yet")
def test_the_two_sources_agree_on_every_prize_tier():
    """The assertion that matters: same numbers in the same tier, day after day.

    Ordering WITHIN a tier is not compared. Six third-prize balls are drawn as a set, and
    the two sources happen to print a handful of them in different orders - which changes
    no frequency, no chi-square and no ticket.
    """
    legacy, boards = _legacy_rows(), _board_rows()
    shared = sorted(set(legacy) & set(boards))
    assert len(shared) > 7_000, "the two sources barely overlap - check the backfill range"

    mismatched = [
        day
        for day in shared
        if _tier_multisets(boards[day]) != _legacy_tier_multisets(boards[day], legacy[day])
    ]
    assert mismatched == list(DISPUTED)


@pytest.mark.skipif(not BOARDS.exists(), reason="Miền Bắc boards not ingested yet")
def test_the_sources_agree_exactly_on_all_but_a_handful_of_days():
    """Row-for-row, ordering included. A dozen cosmetic differences is the whole gap."""
    legacy, boards = _legacy_rows(), _board_rows()
    shared = sorted(set(legacy) & set(boards))
    identical = [day for day in shared if boards[day].tails == legacy[day].prizes]

    assert len(shared) - len(identical) <= 15
    assert len(identical) / len(shared) > 0.998


@pytest.mark.skipif(not BOARDS.exists(), reason="Miền Bắc boards not ingested yet")
def test_every_legacy_date_survived_the_migration():
    missing = sorted(set(_legacy_rows()) - set(_board_rows()))
    assert missing == []


@pytest.mark.skipif(not BOARDS.exists(), reason="Miền Bắc boards not ingested yet")
def test_no_board_is_the_all_zero_tet_filler():
    """The failure this file exists to catch: 27 fake 00s per holiday, filed as results."""
    for board in _board_rows().values():
        assert set(board.tails) != {0}


@pytest.mark.skipif(not BOARDS.exists(), reason="Miền Bắc boards not ingested yet")
def test_derived_view_keeps_the_xsmb_record_shape():
    board = next(iter(_board_rows().values()))
    draw = XsmbDraw(date=board.date, special=board.tails[0], prizes=board.tails)

    assert len(draw.prizes) == PRIZE_SLOTS
    assert draw.special == draw.prizes[0]


def test_read_xsmb_prefers_boards_over_the_legacy_file(tmp_path, monkeypatch):
    """With boards present the legacy file is ignored, so one past cannot shadow another."""
    from tientrivutru import store

    legacy = XsmbDraw(date=date(2005, 10, 1), special=1, prizes=tuple([1] * PRIZE_SLOTS))
    store.write_xsmb([legacy])
    assert store.read_xsmb() == (legacy,)

    board = kt.parse_board(_MIEN_BAC_2005, province="mien-bac", on=date(2005, 10, 1))
    store.write_boards("mb", [board])

    derived = store.read_xsmb()
    assert len(derived) == 1
    assert derived[0].prizes == board.tails
    assert derived[0].prizes != legacy.prizes


@pytest.mark.skipif(not NETWORK, reason="set TIENTRIVUTRU_NETWORK_TESTS=1 to hit minhngoc.net.vn")
def test_live_minhngoc_agrees_with_the_legacy_file_on_random_dates():
    """Twelve dates drawn from 21 years. Any disagreement means the sources diverge."""
    legacy = _legacy_rows()
    rng = random.Random(20051001)
    for day in rng.sample(sorted(legacy), 12):
        board = kt.fetch_board("mien-bac", day)
        assert board.tails == legacy[day].prizes, day


# Kept here rather than imported so this file states its own fixture, the way
# tests/test_kienthiet.py does.
_MIEN_BAC_2005 = (
    '<table class="bkqtinhmienbac_mini"><tbody>'
    '<tr><td nowrap class="giaidbl">Giải ĐB</td><td class="giaidb">34584</td></tr>'
    '<tr><td nowrap class="giai1l">Giải nhất</td><td class="giai1">16876</td></tr>'
    '<tr><td class="giai2">34885 - 65037</td></tr>'
    '<tr><td class="giai3">44442 - 95464 - 14795 - 94080 - 18983 - 22006</td></tr>'
    '<tr><td class="giai4">4979 - 4293 - 2502 - 4395</td></tr>'
    '<tr><td class="giai5">4240 - 3439 - 3988 - 5912 - 3636 - 5423</td></tr>'
    '<tr><td class="giai6">729 - 272 - 278</td></tr>'
    '<tr><td class="giai7">12 - 25 - 78 - 70</td></tr>'
    "</tbody></table>"
)
