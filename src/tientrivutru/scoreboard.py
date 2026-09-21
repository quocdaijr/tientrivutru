"""The Hall of Shame: what the oracle promised versus what actually came out.

Only draws that have BOTH a committed prophecy and a real result are scored, so
the oracle can never quietly drop its bad days. Money is paper money: this counts
what a bao 12 bet would have cost and returned, not what anyone actually spent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from . import wheel
from .games import WHEEL_SIZE, GameSpec, get_game
from .models import Draw, Prophecy, utc_now

JACKPOT_TIERS = ("jackpot", "jackpot1", "jackpot2")


@dataclass(frozen=True, slots=True)
class ScoreRow:
    """One scored draw."""

    game: str
    draw_id: str
    draw_date: date
    hits: int
    bonus_hit: bool
    prize_counts: Mapping[str, int]
    payout_vnd: int
    cost_vnd: int
    payout_excluding_jackpot_vnd: int = 0

    @property
    def won_jackpot(self) -> bool:
        return any(self.prize_counts.get(tier, 0) for tier in JACKPOT_TIERS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "draw_id": self.draw_id,
            "draw_date": self.draw_date.isoformat(),
            "hits": self.hits,
            "bonus_hit": self.bonus_hit,
            "prize_counts": {t: n for t, n in self.prize_counts.items() if n},
            "payout_vnd": self.payout_vnd,
            "cost_vnd": self.cost_vnd,
        }


@dataclass(frozen=True, slots=True)
class GameScore:
    """Aggregate humiliation for one game."""

    game: str
    display: str
    draws_scored: int
    hits_total: int
    hits_per_draw_actual: float
    hits_per_draw_expected: float
    paper_burned_vnd: int
    paper_won_vnd: int
    roi: float
    prize_counts_total: Mapping[str, int]
    best_draw: ScoreRow | None
    jackpot_hits: int
    # A single jackpot in a thousand draws flips ROI from catastrophic to positive
    # while the hit rate stays exactly at chance. Reporting only `roi` would let one
    # lucky draw tell a story the data does not support, so the jackpot-free figure
    # is a first-class number, not a footnote.
    paper_won_excluding_jackpot_vnd: int = 0
    roi_excluding_jackpot: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "display": self.display,
            "draws_scored": self.draws_scored,
            "hits_total": self.hits_total,
            "hits_per_draw_actual": round(self.hits_per_draw_actual, 4),
            "hits_per_draw_expected": round(self.hits_per_draw_expected, 4),
            "paper_burned_vnd": self.paper_burned_vnd,
            "paper_won_vnd": self.paper_won_vnd,
            "roi": round(self.roi, 6),
            "paper_won_excluding_jackpot_vnd": self.paper_won_excluding_jackpot_vnd,
            "roi_excluding_jackpot": round(self.roi_excluding_jackpot, 6),
            "prize_counts_total": {t: n for t, n in self.prize_counts_total.items() if n},
            "best_draw": self.best_draw.to_dict() if self.best_draw else None,
            "jackpot_hits": self.jackpot_hits,
        }


def score_one(
    spec: GameSpec, prophecy: Prophecy, draw: Draw, *, wheel_size: int = WHEEL_SIZE
) -> ScoreRow:
    """Score a single prophecy against the draw it committed to."""
    if prophecy.game != draw.game:
        raise ValueError(f"cannot score {prophecy.game} prophecy against {draw.game} draw")
    if prophecy.draw_id != draw.draw_id:
        raise ValueError(
            f"prophecy targets draw {prophecy.draw_id} but draw is {draw.draw_id}"
        )

    picks = set(prophecy.numbers)
    hits = len(picks & set(draw.main))
    bonus_hit = bool(spec.has_bonus and draw.bonus is not None and draw.bonus in picks)

    counts = wheel.prize_counts(spec, hits, bonus_hit=bonus_hit, wheel=wheel_size)
    fixed_only = {t: n for t, n in counts.items() if t in wheel.FIXED_TIERS}
    return ScoreRow(
        game=spec.key,
        draw_id=draw.draw_id,
        draw_date=draw.date,
        hits=hits,
        bonus_hit=bonus_hit,
        prize_counts=counts,
        payout_vnd=wheel.payout_vnd(spec, counts),
        cost_vnd=wheel.wheel_cost_vnd(spec, wheel_size),
        payout_excluding_jackpot_vnd=wheel.payout_vnd(spec, fixed_only),
    )


def score_rows(
    spec: GameSpec,
    prophecies: Sequence[Prophecy],
    draws: Sequence[Draw],
    *,
    wheel_size: int = WHEEL_SIZE,
) -> tuple[ScoreRow, ...]:
    """Score every prophecy that has a matching result, in draw order."""
    by_id = {d.draw_id: d for d in draws if d.game == spec.key}
    rows = [
        score_one(spec, p, by_id[p.draw_id], wheel_size=wheel_size)
        for p in sorted(prophecies, key=lambda p: p.draw_id)
        if p.game == spec.key and p.draw_id in by_id
    ]
    return tuple(rows)


def build(
    spec: GameSpec,
    prophecies: Sequence[Prophecy],
    draws: Sequence[Draw],
    *,
    wheel_size: int = WHEEL_SIZE,
) -> GameScore:
    """Aggregate all scored draws for one game."""
    rows = score_rows(spec, prophecies, draws, wheel_size=wheel_size)
    expected = spec.expected_hits(wheel_size)

    if not rows:
        return GameScore(
            game=spec.key,
            display=spec.display,
            draws_scored=0,
            hits_total=0,
            hits_per_draw_actual=0.0,
            hits_per_draw_expected=expected,
            paper_burned_vnd=0,
            paper_won_vnd=0,
            roi=0.0,
            prize_counts_total={},
            best_draw=None,
            jackpot_hits=0,
        )

    totals: dict[str, int] = {}
    for row in rows:
        for tier, n in row.prize_counts.items():
            totals[tier] = totals.get(tier, 0) + n

    burned = sum(r.cost_vnd for r in rows)
    won = sum(r.payout_vnd for r in rows)
    won_no_jackpot = sum(r.payout_excluding_jackpot_vnd for r in rows)
    hits_total = sum(r.hits for r in rows)

    return GameScore(
        game=spec.key,
        display=spec.display,
        draws_scored=len(rows),
        hits_total=hits_total,
        hits_per_draw_actual=hits_total / len(rows),
        hits_per_draw_expected=expected,
        paper_burned_vnd=burned,
        paper_won_vnd=won,
        roi=won / burned - 1.0,
        prize_counts_total=totals,
        best_draw=max(rows, key=lambda r: (r.hits, r.payout_vnd)),
        jackpot_hits=sum(1 for r in rows if r.won_jackpot),
        paper_won_excluding_jackpot_vnd=won_no_jackpot,
        roi_excluding_jackpot=won_no_jackpot / burned - 1.0,
    )


def build_all(
    prophecies: Sequence[Prophecy], draws_by_game: Mapping[str, Sequence[Draw]]
) -> dict[str, GameScore]:
    return {
        game: build(get_game(game), prophecies, draws)
        for game, draws in sorted(draws_by_game.items())
    }


def as_json(scores: Mapping[str, GameScore]) -> dict[str, Any]:
    return {
        "generated_at": utc_now().isoformat(),
        "disclaimer": (
            "Paper trading. Xo so la bien co doc lap; ROI am la ket qua dung, khong phai bug."
        ),
        "per_game": {game: score.to_dict() for game, score in sorted(scores.items())},
    }
