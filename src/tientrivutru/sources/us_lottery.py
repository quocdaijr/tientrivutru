"""US lotteries, carried for comparison only.

Why not data.ny.gov: the whole domain returns 403 from this network - every path,
including the plain HTML landing page, with and without browser headers. That is a
network-level block, not a Socrata auth problem, so it is unusable here rather than
merely awkward. powerball.com is reachable but its old JSON API now 301s to the
marketing site and its results pages are JS-rendered.

So we use the same trick that worked for Vietlott: a maintained, MIT-licensed mirror
that a GitHub Action refreshes after every draw.
  https://github.com/jbaranski/jeffs-lottery-utils

Verified live on 2026-08-19:
  powerball.csv    - 1395 draws, 2015-10-07 -> 2026-08-17 (current 5/69 + 1/26 format)
  megamillions.csv - 918 draws, 2017-10-31 -> present

Both files deliberately exclude older game formats (Powerball's matrix changed on
2015-10-07, Mega Millions' on 2017-10-28). Mixing formats would pool draws from
different number spaces, which would corrupt any frequency or chi-square analysis -
so we take only the current-format file and say so.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import date, datetime

import requests

from ..games import GameSpec
from ..models import Draw

MIRROR_BASE = "https://raw.githubusercontent.com/jbaranski/jeffs-lottery-utils/master/numbers"
SOURCE_LABEL = "mirror:jbaranski/jeffs-lottery-utils"
DEFAULT_TIMEOUT = 30
BALL_SEPARATOR = "|"

# The mirror's own column naming differs per game; the bonus ball is the only part
# that changes, so each game declares which column holds it.
BONUS_COLUMNS = {"powerball": "red_ball", "megamillions": "yellow_ball"}


def mirror_url(spec: GameSpec) -> str:
    return f"{MIRROR_BASE}/{spec.mirror_filename}"


def fetch_text(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(mirror_url(spec), timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_us_date(raw: str) -> date:
    """US dates arrive as M/D/YYYY and are NOT zero-padded (e.g. '11/3/2017')."""
    return datetime.strptime(raw.strip(), "%m/%d/%Y").date()


def parse_row(spec: GameSpec, row: dict[str, str], draw_id: int) -> Draw:
    """Turn one CSV row into a validated Draw.

    These files carry no draw number, so the id is the row's position in date order.
    That is stable as long as history is only ever appended, which is why ingest sorts
    by date before assigning ids.
    """
    bonus_column = BONUS_COLUMNS[spec.key]
    for field in ("date", "white_balls", bonus_column):
        if field not in row or row[field] in (None, ""):
            raise ValueError(f"{spec.key}: CSV row missing {field!r}: {row}")

    whites = tuple(int(part) for part in row["white_balls"].split(BALL_SEPARATOR))
    if len(whites) != spec.pick:
        raise ValueError(
            f"{spec.key} {row['date']}: expected {spec.pick} white balls, got {len(whites)}"
        )

    return Draw(
        game=spec.key,
        draw_id=str(draw_id),
        date=parse_us_date(row["date"]),
        main=tuple(sorted(whites)),
        bonus=int(row[bonus_column]),
        source=SOURCE_LABEL,
    )


def parse_csv(spec: GameSpec, text: str) -> tuple[Draw, ...]:
    """Parse the whole CSV, assigning sequential ids in date order."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError(f"{spec.key}: mirror CSV is empty")
    rows.sort(key=lambda r: parse_us_date(r["date"]))
    return tuple(parse_row(spec, row, index) for index, row in enumerate(rows, start=1))


def fetch_draws(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[Draw, ...]:
    return parse_csv(spec, fetch_text(spec, timeout=timeout))


def summarise(spec: GameSpec, draws: Sequence[Draw]) -> dict[str, object]:
    return {
        "game": spec.key,
        "display": spec.display,
        "count": len(draws),
        "first_date": min(d.date for d in draws).isoformat() if draws else None,
        "last_date": max(d.date for d in draws).isoformat() if draws else None,
    }
