"""Jackpot value and prize tiers for one draw, from the page the crawler already fetches.

This is deliberately a separate module from `vietlott_live`. That one produces `Draw`,
the core append-only record whose identity the whole scoreboard rests on; a change to
the prize markup must never be able to break number extraction. Different concern,
different failure surface, different file.

Two honesty rules are enforced in code rather than left to whoever renders the value:

1. **Nothing is inferred.** Every figure comes from the page or the parse fails loudly.
   A jackpot is money, on a site whose whole premise is that none of its numbers lie,
   so a plausible wrong amount is worse than no amount.
2. **The figure carries the moment it was read.** A jackpot grows with ticket sales
   between draws, so a number without a timestamp is a claim the page cannot support.

What this can and cannot know, stated once so callers do not have to guess:

- It reads the jackpot **as at the completed draw**, not an estimate for the next one.
  vietlott.vn serves the estimate only through JavaScript; the plain HTML has it nowhere.
- When the top tier had no winner, that pot rolls forward, so the next draw's jackpot is
  **at least** this figure plus whatever the new tickets add. `rolled_over` says which
  case a caller is in, and nothing here ever phrases it as the current jackpot.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ..games import GameSpec
from ..models import normalise_draw_id, utc_now
from . import vietlott_live

SOURCE_LABEL = "live:vietlott.vn"

JACKPOT_BLOCK = re.compile(r'<div class="gt_jackpot">(?P<block>.*?)<!-- /gt_jackpot -->', re.S)
JACKPOT_ROW = re.compile(
    r"<h5>\s*Giá trị (?P<label>Jackpot(?:\s*\d)?)\s*</h5>.*?<h3>\s*(?P<value>[\d.]+)\s*</h3>",
    re.S,
)
PRIZE_TABLE = re.compile(
    r"<thead>.*?Giải thưởng.*?</thead>\s*<tbody>(?P<body>.*?)</tbody>", re.S
)
PRIZE_ROW = re.compile(r"<tr>(?P<row>.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(?P<cell>.*?)</td>", re.S)
TAGS = re.compile(r"<[^>]+>")


class PrizeParseError(RuntimeError):
    """The page did not contain the figures this module promises to return."""


@dataclass(frozen=True, slots=True)
class PrizeTier:
    """One row of the prize table: how many won it and what it paid."""

    label: str
    winners: int
    value_vnd: int

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "winners": self.winners, "value_vnd": self.value_vnd}


@dataclass(frozen=True, slots=True)
class DrawPrizes:
    """Every money figure the page states for one draw, plus when it was read."""

    game: str
    draw_id: str
    jackpots: Mapping[str, int]
    tiers: tuple[PrizeTier, ...]
    fetched_at: str
    source: str = SOURCE_LABEL

    @property
    def top_jackpot_vnd(self) -> int:
        """The largest jackpot on the page - Jackpot 1 for Power, the only one for Mega."""
        return max(self.jackpots.values())

    @property
    def rolled_over(self) -> bool:
        """True when the top tier found no winner, so the pot carries into the next draw.

        This is the difference between "at least this much is already in the pot" and
        "somebody took it and it has reset to the floor". Callers must not describe a
        jackpot without saying which of the two happened.
        """
        if not self.tiers:
            return False
        return self.tiers[0].winners == 0

    def tier_values(self, spec: GameSpec) -> Mapping[str, int]:
        """Jackpot figures keyed the way `wheel.payout_vnd` expects them.

        The page writes "Giá trị Jackpot 1"; wheel.py keys on `jackpot1`. Translating in
        one place keeps every caller from doing it slightly differently, and validating
        against the game spec means a Power page parsed against Mega raises instead of
        quietly inventing a second jackpot Mega does not have.
        """
        mapped = {label.lower().replace(" ", ""): value for label, value in self.jackpots.items()}
        unknown = set(mapped) - set(spec.jackpot_floor)
        if unknown:
            raise ValueError(
                f"{spec.key} has no jackpot tier(s) {sorted(unknown)} - "
                "these figures came from a different game's page"
            )
        return MappingProxyType(mapped)

    def as_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "draw_id": self.draw_id,
            "jackpots": dict(self.jackpots),
            "tiers": [tier.as_dict() for tier in self.tiers],
            "top_jackpot_vnd": self.top_jackpot_vnd,
            "rolled_over": self.rolled_over,
            "fetched_at": self.fetched_at,
            "source": self.source,
        }


def _to_int(raw: str, what: str) -> int:
    """Vietnamese thousands separator is a dot, so 16.116 is sixteen thousand.

    Reading it as a decimal would turn sixteen thousand winners into sixteen - the kind
    of quiet wrong answer this module exists to make impossible.
    """
    cleaned = raw.strip().replace(".", "").replace(",", "")
    if not cleaned.isdigit():
        raise PrizeParseError(f"{what}: {raw.strip()!r} is not a number")
    return int(cleaned)


def _parse_jackpots(spec: GameSpec, page: str) -> Mapping[str, int]:
    block = JACKPOT_BLOCK.search(page)
    if not block:
        raise PrizeParseError(
            f"{spec.key}: no gt_jackpot block on the results page - layout changed"
        )

    found = {
        re.sub(r"\s+", " ", match.group("label")).strip(): _to_int(
            match.group("value"), f"{spec.key} jackpot"
        )
        for match in JACKPOT_ROW.finditer(block.group("block"))
    }
    expected = len(spec.jackpot_floor) or 1
    if len(found) != expected:
        raise PrizeParseError(
            f"{spec.key}: expected {expected} jackpot value(s), found {len(found)}: "
            f"{sorted(found)}"
        )

    # A jackpot below the game's own reset floor is not a small jackpot, it is a
    # mis-parse that latched onto a prize row. Refuse it rather than publish it.
    floor = min(spec.jackpot_floor.values()) if spec.jackpot_floor else 0
    for label, value in found.items():
        if floor and value < floor:
            raise PrizeParseError(
                f"{spec.key} {label}: {value:,} is below the {floor:,} floor - "
                "the parser latched onto the wrong figure"
            )
    return MappingProxyType(dict(found))


def _parse_tiers(spec: GameSpec, page: str) -> tuple[PrizeTier, ...]:
    table = PRIZE_TABLE.search(page)
    if not table:
        raise PrizeParseError(f"{spec.key}: no prize table on the results page")

    tiers: list[PrizeTier] = []
    for row in PRIZE_ROW.finditer(table.group("body")):
        cells = [TAGS.sub("", cell).strip() for cell in CELL.findall(row.group("row"))]
        if len(cells) < 4:
            continue
        label, _result, winners, value = cells[0], cells[1], cells[2], cells[3]
        tiers.append(
            PrizeTier(
                label=re.sub(r"\s+", " ", label),
                winners=_to_int(winners, f"{spec.key} {label} winners"),
                value_vnd=_to_int(value, f"{spec.key} {label} value"),
            )
        )

    if not tiers:
        raise PrizeParseError(f"{spec.key}: prize table had no readable rows")
    return tuple(tiers)


def parse_prizes(spec: GameSpec, draw_id: str, page: str) -> DrawPrizes:
    """Extract every money figure the results page states for one draw."""
    return DrawPrizes(
        game=spec.key,
        draw_id=normalise_draw_id(draw_id),
        jackpots=_parse_jackpots(spec, page),
        tiers=_parse_tiers(spec, page),
        fetched_at=utc_now().isoformat(),
        source=SOURCE_LABEL,
    )


def fetch_prizes(
    spec: GameSpec, draw_id: str, *, timeout: int = vietlott_live.DEFAULT_TIMEOUT
) -> DrawPrizes:
    """Jackpot and prize tiers straight from vietlott.vn.

    Shares one fetch with the draw crawler by design: the numbers and the money live on
    the same page, so asking twice would double the load for nothing.
    """
    return parse_prizes(spec, draw_id, vietlott_live.fetch_html(spec, timeout=timeout))
