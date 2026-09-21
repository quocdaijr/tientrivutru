"""Cơ cấu giải thưởng xổ số kiến thiết Miền Nam / Miền Trung, and what a ticket is worth.

One đài issues 1,000,000 tickets of six digits at 10,000đ each: ten billion đồng in,
five billion out. That fifty percent is not an estimate - it falls out of the prize table
below and `tests/test_kienthiet_prizes.py` refuses to let it drift. So the honest number
for buying one ticket, forever, is ROI −50%.

Prizes are cumulative: a ticket matching the last two digits of giải tám and the last
three of giải bảy collects both.

Miền Bắc is absent on purpose. Its tickets carry a ký hiệu, its prize table changed in
2017 and again on 2025-04-01, and its special prize splits across several winners - so a
single honest ROI over twenty-one years does not exist. It stays in the honest layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from .sources.kienthiet import Board

TICKET_PRICE_VND = 10_000
TICKET_DIGITS = 6
TICKETS_PER_DAI = 10**TICKET_DIGITS


@dataclass(frozen=True, slots=True)
class PrizeTier:
    """One payable line. `tier` names the board row its number(s) come from."""

    key: str
    display: str
    tier: str
    match: int
    value_vnd: int
    winners_per_number: int

    @property
    def numbers_drawn(self) -> int:
        return _TIER_COUNTS[self.tier]

    @property
    def winners(self) -> int:
        return self.numbers_drawn * self.winners_per_number

    @property
    def pool_vnd(self) -> int:
        return self.winners * self.value_vnd


_TIER_COUNTS = {"db": 1, "g1": 1, "g2": 1, "g3": 2, "g4": 7, "g5": 1, "g6": 3, "g7": 1, "g8": 1}


def _matching_tickets(match: int) -> int:
    """How many of the million tickets share a given `match`-digit tail."""
    return 10 ** (TICKET_DIGITS - match)


PRIZES: tuple[PrizeTier, ...] = (
    PrizeTier("db", "Giải đặc biệt", "db", 6, 2_000_000_000, _matching_tickets(6)),
    PrizeTier("phu_db", "Giải phụ đặc biệt", "db", 6, 50_000_000, 9),
    PrizeTier("khuyen_khich", "Giải khuyến khích", "db", 6, 6_000_000, 45),
    PrizeTier("g1", "Giải nhất", "g1", 5, 30_000_000, _matching_tickets(5)),
    PrizeTier("g2", "Giải nhì", "g2", 5, 15_000_000, _matching_tickets(5)),
    PrizeTier("g3", "Giải ba", "g3", 5, 10_000_000, _matching_tickets(5)),
    PrizeTier("g4", "Giải tư", "g4", 5, 3_000_000, _matching_tickets(5)),
    PrizeTier("g5", "Giải năm", "g5", 4, 1_000_000, _matching_tickets(4)),
    PrizeTier("g6", "Giải sáu", "g6", 4, 400_000, _matching_tickets(4)),
    PrizeTier("g7", "Giải bảy", "g7", 3, 200_000, _matching_tickets(3)),
    PrizeTier("g8", "Giải tám", "g8", 2, 100_000, _matching_tickets(2)),
)

BY_KEY: Mapping[str, PrizeTier] = MappingProxyType({tier.key: tier for tier in PRIZES})


HEADLINE_TIERS = ("db", "phu_db")
"""Prizes big enough that one of them rewrites a lifetime of results.

The đặc biệt alone is 40% of the pool and lands about once per million tickets, so any
realised ROI that includes it is mostly noise until the sample is enormous. Excluding
these two gives the number a normal run actually converges to: −74.5%.
"""


def total_pool_vnd(*, exclude: Sequence[str] = ()) -> int:
    """Every đồng a đài pays out per draw. Five billion, and the tests say so."""
    return sum(tier.pool_vnd for tier in PRIZES if tier.key not in exclude)


def revenue_vnd() -> int:
    return TICKETS_PER_DAI * TICKET_PRICE_VND


def expected_payout_vnd(*, exclude: Sequence[str] = ()) -> float:
    """What one ticket is worth before you buy it."""
    return total_pool_vnd(exclude=exclude) / TICKETS_PER_DAI


def theoretical_roi(*, exclude: Sequence[str] = ()) -> float:
    """−0.5. Not a forecast, not a sample - arithmetic on the published prize table.

    With `exclude=HEADLINE_TIERS` it is −0.745, which is what a run of a few hundred
    thousand tickets will actually show.
    """
    return expected_payout_vnd(exclude=exclude) / TICKET_PRICE_VND - 1.0


class TicketEraError(ValueError):
    """Raised for boards from before the six-digit special, where a ticket has no meaning."""


def _off_by_one_positions(ticket: str, special: str) -> list[int]:
    """Positions where the ticket differs from the special. Empty means an exact match."""
    return [i for i, (a, b) in enumerate(zip(ticket, special, strict=True)) if a != b]


def check_ticket(ticket: str) -> str:
    if len(ticket) != TICKET_DIGITS or not ticket.isdigit():
        raise ValueError(f"a ticket is {TICKET_DIGITS} digits, got {ticket!r}")
    return ticket


def payout_vnd(board: Board, ticket: str) -> tuple[Mapping[str, int], int]:
    """What one ticket wins on one board. Returns (prizes won by key, total đồng).

    Cumulative: every tier the ticket matches pays. Raises TicketEraError on a board
    whose special is not six digits, because tickets were five digits back then and
    pretending otherwise would silently invent an ROI.
    """
    check_ticket(ticket)
    if board.region == "mb":
        raise TicketEraError("Miền Bắc has no single ticket prize table - see this module")
    rows = dict(board.tiers)
    special = rows["db"][0]
    if len(special) != TICKET_DIGITS:
        raise TicketEraError(
            f"{board.province} {board.date}: giải đặc biệt is {len(special)} digits, "
            f"so a {TICKET_DIGITS}-digit ticket cannot be settled"
        )

    won: dict[str, int] = {}
    off_by = _off_by_one_positions(ticket, special)
    if not off_by:
        won["db"] = 1
    elif len(off_by) == 1:
        won["phu_db" if off_by[0] == 0 else "khuyen_khich"] = 1

    for tier in PRIZES:
        if tier.key in ("db", "phu_db", "khuyen_khich"):
            continue
        tail = ticket[-tier.match :]
        hits = sum(1 for number in rows[tier.tier] if number[-tier.match :] == tail)
        if hits:
            won[tier.key] = hits

    total = sum(BY_KEY[key].value_vnd * count for key, count in won.items())
    return MappingProxyType(won), total


def describe(won: Mapping[str, int]) -> str:
    """Human-readable prize list, highest tier first. Empty string when nothing won."""
    parts = [
        f"{BY_KEY[tier.key].display}{'' if won[tier.key] == 1 else f' ×{won[tier.key]}'}"
        for tier in PRIZES
        if tier.key in won
    ]
    return " · ".join(parts)
