"""Primary source: the MIT-licensed mirror at github.com/thanhnhu/vietlott.

Why a mirror instead of vietlott.vn directly: the official site sits behind
Cloudflare and only renders the newest draw, with history reachable only through an
AJAX call. The mirror already solved that and commits results as JSONL.

Verified against live data on 2026-08-19:
  power655.jsonl - 1386 draws, ids 1..1386, zero gaps, all 7-number rows,
                   first six always sorted ascending -> the 7th IS the bonus.
  power645.jsonl - 1352 draws, ids 198..1549, zero gaps, all 6-number rows.
                   Despite the filename this is Mega 6/45, not a 6/45 "Power".

Known upstream weakness: the mirror lags on Mega 6/45 (the Sun 2026-08-16 draw was
missing while Power 6/55 was current), which is exactly why find_missing_dates exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

import requests

from ..games import GameSpec, draw_days_between
from ..models import Draw

MIRROR_BASE = "https://raw.githubusercontent.com/thanhnhu/vietlott/master/data"
SOURCE_LABEL = "mirror:thanhnhu/vietlott"
DEFAULT_TIMEOUT = 30


def mirror_url(spec: GameSpec) -> str:
    return f"{MIRROR_BASE}/{spec.mirror_filename}"


def fetch_text(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Download the raw JSONL for a game. Network errors propagate deliberately."""
    response = requests.get(mirror_url(spec), timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_row(spec: GameSpec, row: Mapping[str, Any]) -> Draw:
    """Turn one upstream JSON object into a validated Draw.

    Fails loudly on anything unexpected - a silently skipped row is a silently wrong
    scoreboard later.
    """
    for field in ("date", "id", "result"):
        if field not in row:
            raise ValueError(f"{spec.key}: upstream row missing {field!r}: {row}")

    result = row["result"]
    if not isinstance(result, list):
        raise TypeError(f"{spec.key} draw {row['id']}: result must be a list, got {type(result)}")
    if len(result) != spec.result_length:
        raise ValueError(
            f"{spec.key} draw {row['id']}: expected {spec.result_length} numbers "
            f"(pick {spec.pick}{' + bonus' if spec.has_bonus else ''}), got {len(result)}: {result}"
        )

    main = tuple(result[: spec.pick])
    bonus = result[spec.pick] if spec.has_bonus else None

    return Draw(
        game=spec.key,
        draw_id=str(row["id"]),
        date=date.fromisoformat(str(row["date"])),
        main=main,
        bonus=bonus,
        source=SOURCE_LABEL,
    )


def parse_jsonl(spec: GameSpec, text: str) -> tuple[Draw, ...]:
    """Parse a whole JSONL payload, sorted by draw_id."""
    draws = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{spec.key} mirror line {lineno}: invalid JSON: {exc}") from exc
        draws.append(parse_row(spec, row))
    return tuple(sorted(draws, key=lambda d: d.draw_id))


def fetch_draws(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[Draw, ...]:
    return parse_jsonl(spec, fetch_text(spec, timeout=timeout))


def find_gaps(draws: Sequence[Draw]) -> tuple[str, ...]:
    """draw_ids missing from the contiguous span between the first and last draw."""
    if not draws:
        return ()
    ids = sorted(int(d.draw_id) for d in draws)
    present = set(ids)
    width = len(draws[0].draw_id)
    return tuple(
        str(n).zfill(width) for n in range(ids[0], ids[-1] + 1) if n not in present
    )


def find_missing_dates(
    spec: GameSpec, draws: Sequence[Draw], until: date
) -> tuple[date, ...]:
    """Draw days between the last stored draw and `until` that produced no draw.

    This is the lag detector: the mirror can be internally gap-free yet still be
    days behind reality.
    """
    if not draws:
        return ()
    seen = {d.date for d in draws}
    latest = max(seen)
    expected = draw_days_between(spec, latest, until)
    return tuple(day for day in expected if day not in seen)


def summarise(spec: GameSpec, draws: Sequence[Draw], until: date) -> dict[str, Any]:
    """A compact ingest report, used by the CLI and the Actions step summary."""
    gaps = find_gaps(draws)
    missing = find_missing_dates(spec, draws, until)
    return {
        "game": spec.key,
        "display": spec.display,
        "count": len(draws),
        "first_id": draws[0].draw_id if draws else None,
        "last_id": draws[-1].draw_id if draws else None,
        "last_date": max(d.date for d in draws).isoformat() if draws else None,
        "gap_ids": list(gaps),
        "missing_draw_dates": [d.isoformat() for d in missing],
    }


def iter_history(draws: Iterable[Draw]) -> Iterable[Draw]:
    """Chronological iteration helper, kept explicit for readability at call sites."""
    return sorted(draws, key=lambda d: d.draw_id)
