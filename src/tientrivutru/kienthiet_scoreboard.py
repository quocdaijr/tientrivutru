"""Bảng Phong Thần cho vé số kiến thiết: one ticket per đài, settled against the board.

Only days that have BOTH a committed ticket and a real board are scored, so the oracle
cannot quietly drop the days it did badly on.

The đặc biệt is 40% of the whole prize pool, which is the same trap the Vietlott jackpot
sets in `scoreboard`: one lucky ticket in ten thousand flips ROI from −80% to +2000% while
the hit rate stays exactly at chance. So the đặc-biệt-free figure is reported as a
first-class number, not a footnote - and both are compared against the exact −50% that
`kienthiet_prizes` derives from the published table.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from . import kienthiet_prizes as prizes
from .kienthiet_oracle import VeProphecy
from .models import utc_now
from .sources.kienthiet import PROVINCES, REGIONS, Board

HEADLINE_TIERS = prizes.HEADLINE_TIERS


@dataclass(frozen=True, slots=True)
class VeScoreRow:
    """One settled ticket."""

    draw_date: date
    province: str
    region: str
    ve: str
    special: str
    prize_counts: Mapping[str, int]
    payout_vnd: int
    cost_vnd: int

    @property
    def won_headline(self) -> bool:
        return any(self.prize_counts.get(tier, 0) for tier in HEADLINE_TIERS)

    @property
    def payout_excluding_headline_vnd(self) -> int:
        return sum(
            prizes.BY_KEY[tier].value_vnd * count
            for tier, count in self.prize_counts.items()
            if tier not in HEADLINE_TIERS
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "draw_date": self.draw_date.isoformat(),
            "province": self.province,
            "display": PROVINCES[self.province].display,
            "ve": self.ve,
            "special": self.special,
            "prize_counts": {t: n for t, n in self.prize_counts.items() if n},
            "prizes": prizes.describe(self.prize_counts),
            "payout_vnd": self.payout_vnd,
            "cost_vnd": self.cost_vnd,
        }


@dataclass(frozen=True, slots=True)
class VeScore:
    """Aggregate humiliation for one region, or for all of them."""

    region: str | None
    display: str
    tickets: int
    paper_burned_vnd: int
    paper_won_vnd: int
    roi: float
    paper_won_excluding_headline_vnd: int
    roi_excluding_headline: float
    theoretical_roi: float
    theoretical_roi_excluding_headline: float
    prize_counts_total: Mapping[str, int]
    winning_tickets: int
    best: VeScoreRow | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "display": self.display,
            "tickets": self.tickets,
            "paper_burned_vnd": self.paper_burned_vnd,
            "paper_won_vnd": self.paper_won_vnd,
            "roi": self.roi,
            "paper_won_excluding_headline_vnd": self.paper_won_excluding_headline_vnd,
            "roi_excluding_headline": self.roi_excluding_headline,
            "theoretical_roi": self.theoretical_roi,
            "theoretical_roi_excluding_headline": self.theoretical_roi_excluding_headline,
            "prize_counts_total": dict(self.prize_counts_total),
            "winning_tickets": self.winning_tickets,
            "best": self.best.to_dict() if self.best else None,
        }


def score_one(board: Board, prophecy: VeProphecy) -> VeScoreRow:
    """Settle one committed ticket against the đài's board."""
    if board.key != prophecy.key:
        raise ValueError(f"board {board.key} does not match vé {prophecy.key}")
    won, payout = prizes.payout_vnd(board, prophecy.ve)
    return VeScoreRow(
        draw_date=board.date,
        province=board.province,
        region=board.region,
        ve=prophecy.ve,
        special=board.special,
        prize_counts=won,
        payout_vnd=payout,
        cost_vnd=prizes.TICKET_PRICE_VND,
    )


def score_rows(
    prophecies: Sequence[VeProphecy], boards: Sequence[Board]
) -> tuple[VeScoreRow, ...]:
    """Score every ticket that has a matching board, oldest first.

    Boards from before the six-digit special era are skipped rather than guessed at -
    a five-digit board cannot settle a six-digit ticket, and inventing a rule for it
    would invent an ROI with it.
    """
    by_key = {b.key: b for b in boards}
    rows = []
    for prophecy in sorted(prophecies, key=lambda p: p.key):
        board = by_key.get(prophecy.key)
        if board is None:
            continue
        try:
            rows.append(score_one(board, prophecy))
        except prizes.TicketEraError:
            continue
    return tuple(rows)


def _empty(region: str | None) -> VeScore:
    return VeScore(
        region=region,
        display=REGIONS[region].display if region else "Kiến thiết",
        tickets=0,
        paper_burned_vnd=0,
        paper_won_vnd=0,
        roi=0.0,
        paper_won_excluding_headline_vnd=0,
        roi_excluding_headline=0.0,
        theoretical_roi=prizes.theoretical_roi(),
        theoretical_roi_excluding_headline=prizes.theoretical_roi(exclude=HEADLINE_TIERS),
        prize_counts_total={},
        winning_tickets=0,
        best=None,
    )


def build(
    prophecies: Sequence[VeProphecy],
    boards: Sequence[Board],
    *,
    region: str | None = None,
) -> VeScore:
    """Aggregate every settled ticket, optionally for one region."""
    if region is not None and region not in REGIONS:
        raise KeyError(f"Unknown region {region!r}")
    rows = [r for r in score_rows(prophecies, boards) if region is None or r.region == region]
    if not rows:
        return _empty(region)

    totals: dict[str, int] = {}
    for row in rows:
        for tier, count in row.prize_counts.items():
            totals[tier] = totals.get(tier, 0) + count

    burned = sum(r.cost_vnd for r in rows)
    won = sum(r.payout_vnd for r in rows)
    won_plain = sum(r.payout_excluding_headline_vnd for r in rows)

    return VeScore(
        region=region,
        display=REGIONS[region].display if region else "Kiến thiết",
        tickets=len(rows),
        paper_burned_vnd=burned,
        paper_won_vnd=won,
        roi=won / burned - 1.0,
        paper_won_excluding_headline_vnd=won_plain,
        roi_excluding_headline=won_plain / burned - 1.0,
        theoretical_roi=prizes.theoretical_roi(),
        theoretical_roi_excluding_headline=prizes.theoretical_roi(exclude=HEADLINE_TIERS),
        prize_counts_total=totals,
        winning_tickets=sum(1 for r in rows if r.payout_vnd),
        best=max(rows, key=lambda r: (r.payout_vnd, r.draw_date)),
    )


def build_all(
    prophecies: Sequence[VeProphecy], boards: Sequence[Board]
) -> dict[str, VeScore]:
    """One score per prophesiable region, plus an "all" roll-up under the empty key."""
    scores = {
        region: build(prophecies, boards, region=region)
        for region, spec in REGIONS.items()
        if spec.prophesiable
    }
    scores["all"] = build(prophecies, boards)
    return scores


def as_json(scores: Mapping[str, VeScore]) -> dict[str, Any]:
    return {
        "generated_at": utc_now().isoformat(),
        "disclaimer": (
            "Paper trading, moi ky mot ve. Co cau giai tra ve dung 50% doanh thu, "
            "nen ROI ky vong la -50%. Con so thuc te lech nhieu vi giai dac biet "
            "chiem 40% quy giai va rat lau moi ve mot lan."
        ),
        "per_region": {key: score.to_dict() for key, score in sorted(scores.items())},
    }
