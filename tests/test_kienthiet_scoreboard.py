"""Settling committed tickets. The ROI must be arithmetic, never a mood."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tientrivutru import kienthiet_oracle as ko
from tientrivutru import kienthiet_prizes as kp
from tientrivutru import kienthiet_scoreboard as ks
from tientrivutru.models import utc_now
from tientrivutru.sources.kienthiet import Board

SPECIAL = "510332"
TAIL = (
    ("g1", ("89516",)),
    ("g2", ("44895",)),
    ("g3", ("52640", "02439")),
    ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
    ("g5", ("1635",)),
    ("g6", ("9670", "9023", "3404")),
    ("g7", ("516",)),
    ("g8", ("54",)),
)


def board(day: date, province: str = "an-giang", special: str = SPECIAL) -> Board:
    return Board(date=day, region="mn", province=province, tiers=(("db", (special,)), *TAIL))


def ticket(day: date, ve: str, province: str = "an-giang") -> ko.VeProphecy:
    return ko.VeProphecy(
        province=province,
        region="mn",
        draw_date=day,
        ve=ve,
        seed="deadbeef" * 8,
        signals={},
        sermon="Thầy nói một lần thôi đấy.",
        reasons=(),
        karma=None,
        oracle_version=ko.KIENTHIET_ORACLE_VERSION,
        created_at=utc_now(),
    )


DAY = date(2026, 8, 20)


# --- one ticket ---------------------------------------------------------------------


def test_a_losing_ticket_still_gets_scored():
    row = ks.score_one(board(DAY), ticket(DAY, "777777"))

    assert row.payout_vnd == 0
    assert row.cost_vnd == kp.TICKET_PRICE_VND
    assert row.special == SPECIAL


def test_the_special_is_recorded_even_when_the_ticket_missed():
    """The Hall of Shame has to show what came out, not only what was guessed."""
    assert ks.score_one(board(DAY), ticket(DAY, "000000")).special == SPECIAL


def test_a_ticket_for_another_day_is_refused():
    with pytest.raises(ValueError, match="does not match"):
        ks.score_one(board(DAY), ticket(DAY + timedelta(days=7), "777777"))


def test_a_ticket_for_another_dai_is_refused():
    with pytest.raises(ValueError, match="does not match"):
        ks.score_one(board(DAY, "tay-ninh"), ticket(DAY, "777777", "an-giang"))


# --- aggregation --------------------------------------------------------------------


def test_only_days_with_both_a_ticket_and_a_board_are_scored():
    prophecies = [ticket(DAY, "777777"), ticket(DAY + timedelta(days=7), "777777")]
    score = ks.build(prophecies, [board(DAY)])

    assert score.tickets == 1


def test_nothing_scored_is_reported_as_nothing_not_as_zero_roi_luck():
    score = ks.build([], [board(DAY)])

    assert score.tickets == 0
    assert score.best is None
    assert score.theoretical_roi == -0.5


def test_a_hundred_losing_tickets_are_a_hundred_percent_loss():
    days = [DAY - timedelta(days=7 * n) for n in range(100)]
    score = ks.build([ticket(d, "777777") for d in days], [board(d) for d in days])

    assert score.tickets == 100
    assert score.paper_burned_vnd == 100 * kp.TICKET_PRICE_VND
    assert score.roi == -1.0
    assert score.winning_tickets == 0


def test_the_special_is_reported_separately_because_it_rewrites_the_roi():
    """One đặc biệt in ten thousand flips ROI from ruinous to absurd. Show both."""
    days = [DAY - timedelta(days=7 * n) for n in range(100)]
    tickets = [ticket(d, "777777") for d in days[1:]] + [ticket(days[0], SPECIAL)]
    score = ks.build(tickets, [board(d) for d in days])

    assert score.roi > 100
    assert score.roi_excluding_headline == -1.0
    assert score.prize_counts_total["db"] == 1


def test_the_best_ticket_is_the_one_that_paid_most():
    days = [DAY, DAY - timedelta(days=7)]
    tickets = [ticket(days[0], "999654"), ticket(days[1], SPECIAL)]
    score = ks.build(tickets, [board(d) for d in days])

    assert score.best is not None
    assert score.best.ve == SPECIAL


def test_regions_are_scored_apart_and_together():
    centre = Board(
        date=DAY, region="mt", province="phu-yen", tiers=(("db", (SPECIAL,)), *TAIL)
    )
    tickets = [
        ticket(DAY, "777777"),
        ko.VeProphecy(
            province="phu-yen",
            region="mt",
            draw_date=DAY,
            ve="777777",
            seed="0" * 64,
            signals={},
            sermon="",
            reasons=(),
            karma=None,
            oracle_version=ko.KIENTHIET_ORACLE_VERSION,
            created_at=utc_now(),
        ),
    ]
    boards = [board(DAY), centre]

    assert ks.build(tickets, boards, region="mn").tickets == 1
    assert ks.build(tickets, boards, region="mt").tickets == 1
    assert ks.build(tickets, boards).tickets == 2


def test_build_all_covers_every_prophesiable_region_and_the_roll_up():
    scores = ks.build_all([], [])
    assert set(scores) == {"mn", "mt", "all"}
    assert "mb" not in scores


def test_an_unknown_region_is_refused():
    with pytest.raises(KeyError, match="mien-tay"):
        ks.build([], [], region="mien-tay")


# --- the era guard ------------------------------------------------------------------


def test_a_five_digit_board_is_skipped_not_guessed():
    """Pre-2011 boards cannot settle a six-digit ticket. Skipping beats inventing."""
    old = Board(
        date=date(2010, 1, 4),
        region="mt",
        province="phu-yen",
        tiers=(("db", ("06278",)), *TAIL),
    )
    prophecy = ko.VeProphecy(
        province="phu-yen",
        region="mt",
        draw_date=date(2010, 1, 4),
        ve="006278",
        seed="0" * 64,
        signals={},
        sermon="",
        reasons=(),
        karma=None,
        oracle_version=ko.KIENTHIET_ORACLE_VERSION,
        created_at=utc_now(),
    )

    assert ks.score_rows([prophecy], [old]) == ()
    assert ks.build([prophecy], [old]).tickets == 0


# --- the honest number --------------------------------------------------------------


def test_roi_converges_towards_minus_fifty_percent_over_many_random_boards():
    """Fifty thousand random tickets against random boards. Not proof - a sanity floor.

    Measured over two million tickets the two figures land at −58.0% and −74.25%; the
    exact expectations are −50% and −74.5%. The gap between them IS the point: the đặc
    biệt is 40% of the pool and lands about once per million tickets, so the headline ROI
    stays noise for a very long time. Fifty thousand is small, hence the wide tolerance.
    """
    import random

    rng = random.Random(510332)

    def random_board(day: date) -> Board:
        rows = []
        for tier in (
            ("db", 1, 6),
            ("g1", 1, 5),
            ("g2", 1, 5),
            ("g3", 2, 5),
            ("g4", 7, 5),
            ("g5", 1, 4),
            ("g6", 3, 4),
            ("g7", 1, 3),
            ("g8", 1, 2),
        ):
            key, count, width = tier
            rows.append((key, tuple(f"{rng.randrange(10**width):0{width}d}" for _ in range(count))))
        return Board(date=day, region="mn", province="an-giang", tiers=tuple(rows))

    days = [date(2000, 1, 1) + timedelta(days=n) for n in range(50_000)]
    boards = [random_board(d) for d in days]
    tickets = [ticket(d, f"{rng.randrange(1_000_000):06d}") for d in days]

    score = ks.build(tickets, boards)

    assert score.tickets == 50_000
    assert score.theoretical_roi == -0.5
    assert score.theoretical_roi_excluding_headline == -0.745
    assert score.roi_excluding_headline == pytest.approx(-0.745, abs=0.25)
