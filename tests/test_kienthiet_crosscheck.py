"""Why minhngoc is the source and t-k-minh/XSMienNam-Analysis is not.

The obvious move for a Vietnamese lottery dataset is the GitHub mirror everybody links to,
which is how XSMB got into this repo in the first place. For the southern boards that
mirror is lossy in a way that is invisible unless you compare: its CSV has four columns
for giải tư, and giải tư has **seven** numbers. Every draw silently loses three.

This test is the evidence for that choice, and the alarm if it ever changes: if the mirror
grows the missing columns, the diff below stops being exactly three giải-tư numbers and
this fails - at which point the mirror is worth reconsidering.

Network-gated, because CI must not depend on someone else's uptime.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import date

import pytest
import requests

from tientrivutru.sources import kienthiet as kt

MIRROR_URL = (
    "https://raw.githubusercontent.com/t-k-minh/XSMienNam-Analysis/main/data/xsmn.csv"
)
NETWORK = os.environ.get("TIENTRIVUTRU_NETWORK_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not NETWORK, reason="set TIENTRIVUTRU_NETWORK_TESTS=1 to hit the network"
)

# An Giang, Thursday 2026-08-20. Chosen because its giải tư is unremarkable, which is the
# point: the loss is not confined to odd draws.
SAMPLE_DAY = date(2026, 8, 20)
SAMPLE_PROVINCE = "an-giang"
MIRROR_CODE = "AG"


def _mirror_row() -> dict[str, str]:
    response = requests.get(MIRROR_URL, timeout=90)
    response.raise_for_status()
    for row in csv.DictReader(io.StringIO(response.text)):
        if row["date"] == SAMPLE_DAY.isoformat() and row["province"] == MIRROR_CODE:
            return row
    pytest.skip(f"the mirror has no row for {MIRROR_CODE} {SAMPLE_DAY}")


def test_the_mirror_only_carries_four_of_the_seven_fourth_prizes():
    row = _mirror_row()
    assert [k for k in row if k.startswith("prize4")] == [
        "prize4_1",
        "prize4_2",
        "prize4_3",
        "prize4_4",
    ]


def test_minhngoc_and_the_mirror_agree_on_everything_the_mirror_stores():
    """Fifteen of eighteen numbers match. The source choice is about the other three."""
    row = _mirror_row()
    board = dict(kt.fetch_board(SAMPLE_PROVINCE, SAMPLE_DAY).tiers)

    assert board["db"][0] == row["special"]
    assert board["g1"][0] == row["prize1"]
    assert board["g2"][0] == row["prize2"]
    assert board["g3"] == (row["prize3_1"], row["prize3_2"])
    assert board["g4"][:4] == (
        row["prize4_1"],
        row["prize4_2"],
        row["prize4_3"],
        row["prize4_4"],
    )
    assert board["g5"][0] == row["prize5"]
    assert board["g6"] == (row["prize6_1"], row["prize6_2"], row["prize6_3"])
    assert board["g7"][0] == row["prize7"]
    assert board["g8"][0] == row["prize8"]


def test_the_missing_three_are_real_numbers_the_mirror_never_had():
    """Not a formatting quirk: three five-digit prizes exist and are simply absent."""
    board = dict(kt.fetch_board(SAMPLE_PROVINCE, SAMPLE_DAY).tiers)
    lost = board["g4"][4:]

    assert len(lost) == 3
    assert all(len(number) == 5 and number.isdigit() for number in lost)
