"""The prize table is the only place in this repo where the honest number is exact.

Everything else here is a sample: 12,578 draws, a p-value, a paper-trading ROI that
wobbles. The southern kiến thiết prize table is arithmetic. One million tickets at
10,000đ is ten billion in; the table pays five billion out; a ticket is worth 5,000đ.
If any of these assertions ever fail, either the law changed or someone fat-fingered a
zero, and the ROI on the front page became a lie either way.
"""

from __future__ import annotations

import itertools
import random
from datetime import date

import pytest

from tientrivutru import kienthiet_prizes as kp
from tientrivutru.sources.kienthiet import Board

SPECIAL = "510332"
BOARD = Board(
    date=date(2026, 8, 20),
    region="mn",
    province="an-giang",
    tiers=(
        ("db", (SPECIAL,)),
        ("g1", ("89516",)),
        ("g2", ("44895",)),
        ("g3", ("52640", "02439")),
        ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
        ("g5", ("1635",)),
        ("g6", ("9670", "9023", "3404")),
        ("g7", ("516",)),
        ("g8", ("54",)),
    ),
)

# --- the table itself ---------------------------------------------------------------


def test_a_dai_pays_out_exactly_five_billion():
    assert kp.total_pool_vnd() == 5_000_000_000


def test_a_dai_takes_exactly_ten_billion():
    assert kp.revenue_vnd() == 10_000_000_000


def test_a_ticket_is_worth_exactly_half_what_it_costs():
    assert kp.expected_payout_vnd() == 5_000
    assert kp.theoretical_roi() == -0.5


def test_the_pool_divides_evenly_across_the_million_tickets():
    assert kp.total_pool_vnd() % kp.TICKETS_PER_DAI == 0


def test_without_the_headline_prizes_a_ticket_is_worth_2550d():
    """What a run of a few hundred thousand tickets actually converges to."""
    assert kp.total_pool_vnd(exclude=kp.HEADLINE_TIERS) == 2_550_000_000
    assert kp.theoretical_roi(exclude=kp.HEADLINE_TIERS) == -0.745


def test_special_prize_is_forty_percent_of_the_pool():
    """Which is why a single ticket's realised ROI converges so slowly."""
    assert kp.BY_KEY["db"].pool_vnd / kp.total_pool_vnd() == pytest.approx(0.4)


def test_phu_db_is_the_first_digit_and_khuyen_khich_is_the_other_five():
    assert kp.BY_KEY["phu_db"].winners == 9
    assert kp.BY_KEY["khuyen_khich"].winners == 5 * 9


def test_every_tier_maps_to_a_row_that_exists_on_a_southern_board():
    printed = dict(BOARD.tiers)
    for tier in kp.PRIZES:
        assert tier.tier in printed
        assert len(printed[tier.tier]) == tier.numbers_drawn


# --- settling one ticket ------------------------------------------------------------


def test_the_special_number_itself_wins_two_billion():
    won, total = kp.payout_vnd(BOARD, SPECIAL)
    assert won["db"] == 1
    assert total >= 2_000_000_000


def test_wrong_first_digit_is_the_fifty_million_consolation():
    won, _ = kp.payout_vnd(BOARD, "010332")
    assert "phu_db" in won
    assert "khuyen_khich" not in won


@pytest.mark.parametrize("position", [1, 2, 3, 4, 5])
def test_wrong_any_other_digit_is_the_six_million_consolation(position):
    digits = list(SPECIAL)
    digits[position] = str((int(digits[position]) + 1) % 10)
    won, total = kp.payout_vnd(BOARD, "".join(digits))
    assert "khuyen_khich" in won
    assert "phu_db" not in won
    assert total >= 6_000_000


def test_two_wrong_digits_is_worth_nothing_from_the_special():
    won, _ = kp.payout_vnd(BOARD, "010333")
    assert "db" not in won and "phu_db" not in won and "khuyen_khich" not in won


def _board_with(**rows: tuple[str, ...]) -> Board:
    """The reference board with some rows swapped out."""
    return Board(
        date=BOARD.date,
        region="mn",
        province="an-giang",
        tiers=tuple((key, rows.get(key, values)) for key, values in BOARD.tiers),
    )


def test_only_the_matching_tail_pays():
    """Giải tám is 54 here, so 999654 collects that and nothing else."""
    assert dict(kp.payout_vnd(BOARD, "999654")[0]) == {"g8": 1}


def test_a_ticket_can_win_several_tiers_at_once():
    """Prizes are cumulative: 154 is giải bảy and its last two digits are giải tám."""
    board = _board_with(g7=("154",), g8=("54",))
    won, total = kp.payout_vnd(board, "999154")

    assert dict(won) == {"g7": 1, "g8": 1}
    assert total == 200_000 + 100_000


def test_a_number_drawn_twice_pays_twice():
    """Giải tư holds seven numbers, and nothing stops two of them being the same."""
    board = _board_with(g4=("90111", "32541", "20491", "71417", "32217", "57371", "90111"))
    won, total = kp.payout_vnd(board, "990111")

    assert won["g4"] == 2
    assert total == 2 * kp.BY_KEY["g4"].value_vnd


def test_a_losing_ticket_wins_nothing():
    won, total = kp.payout_vnd(BOARD, "777777")
    assert dict(won) == {}
    assert total == 0


def test_a_ticket_must_be_six_digits():
    for bad in ("51033", "5103322", "51033x"):
        with pytest.raises(ValueError, match="6 digits"):
            kp.payout_vnd(BOARD, bad)


def test_the_five_digit_special_era_is_refused_not_guessed():
    old = Board(
        date=date(2010, 1, 4),
        region="mt",
        province="phu-yen",
        tiers=(("db", ("06278",)), *BOARD.tiers[1:]),
    )
    with pytest.raises(kp.TicketEraError, match="5 digits"):
        kp.payout_vnd(old, "006278")


def test_mien_bac_has_no_ticket_prize_table():
    from tientrivutru.sources.kienthiet import REGIONS

    assert not REGIONS["mb"].prophesiable
    north = Board(
        date=date(2026, 8, 20),
        region="mb",
        province="mien-bac",
        tiers=(
            ("db", ("07523",)),
            ("g1", ("29580",)),
            ("g2", ("34885", "65037")),
            ("g3", ("44442", "95464", "14795", "94080", "18983", "22006")),
            ("g4", ("4979", "4293", "2502", "4395")),
            ("g5", ("4240", "3439", "3988", "5912", "3636", "5423")),
            ("g6", ("729", "272", "278")),
            ("g7", ("12", "25", "78", "70")),
        ),
    )
    with pytest.raises(kp.TicketEraError, match="Miền Bắc"):
        kp.payout_vnd(north, "007523")


# --- the whole million --------------------------------------------------------------


def _winning_tickets(board: Board) -> set[str]:
    """Every ticket that wins anything, built independently of the scorer."""
    rows = dict(board.tiers)
    special = rows["db"][0]
    tickets = {special}
    for position in range(kp.TICKET_DIGITS):
        for digit in "0123456789":
            if digit != special[position]:
                tickets.add(special[:position] + digit + special[position + 1 :])
    for tier in kp.PRIZES:
        if tier.key in ("db", "phu_db", "khuyen_khich"):
            continue
        for number in rows[tier.tier]:
            tail = number[-tier.match :]
            head = kp.TICKET_DIGITS - tier.match
            for prefix in itertools.product("0123456789", repeat=head):
                tickets.add("".join(prefix) + tail)
    return tickets


def test_the_winners_add_up_to_the_whole_prize_pool():
    """Settle every ticket that can win. The scorer must hand out five billion, no more."""
    paid = sum(kp.payout_vnd(BOARD, ticket)[1] for ticket in _winning_tickets(BOARD))
    assert paid == kp.total_pool_vnd()


def test_no_ticket_outside_the_winners_set_is_paid():
    winners = _winning_tickets(BOARD)
    rng = random.Random(510332)
    checked = 0
    while checked < 2_000:
        ticket = f"{rng.randrange(kp.TICKETS_PER_DAI):06d}"
        if ticket in winners:
            continue
        assert kp.payout_vnd(BOARD, ticket)[1] == 0
        checked += 1


def test_exhaustive_million_tickets_pay_exactly_five_billion():
    """Three seconds to settle every ticket a đài prints. Worth it - this is the number."""
    paid = sum(kp.payout_vnd(BOARD, f"{n:06d}")[1] for n in range(kp.TICKETS_PER_DAI))
    assert paid == 5_000_000_000
