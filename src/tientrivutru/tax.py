"""Vietnamese personal income tax on a lottery prize.

Its own module because it is a rule of the jurisdiction, not of the game: it applies
identically to Power, Mega and anything else, and it changes on a schedule none of the
game specs control.

Why it exists at all: the page advertises jackpot figures. Announcing 34.9 billion while
staying quiet about the 3.49 billion withheld from it is what the scam sites do, and this
repository is built on the opposite promise. The announced figure and the take-home are
both real numbers, so both get printed.

The rule: 10% of whatever the prize exceeds 10 million dong, per prize, per ticket, per
draw - it is the *excess* that is taxed, not the whole prize, which is why a prize of
exactly 10 million is received whole.

Deliberately NOT modelled here, because these are not numbers to invent:
  - whether a bao ticket counts as one ticket or 924 for the per-ticket rule
  - a jackpot split between several winners, which is taxed per winner's share
Anything that needs those must say it does not know.
"""

from __future__ import annotations

TAX_FREE_VND = 10_000_000
"""Prizes are taxed only on what they exceed this by."""

RATE = 0.10
"""Flat rate on the excess."""


def withheld_vnd(prize_vnd: int) -> int:
    """Tax withheld at source from a single prize.

    Integer arithmetic on purpose: the result is dong, and floating point has no business
    anywhere near a figure this size.
    """
    if prize_vnd < 0:
        raise ValueError(f"a prize cannot be negative, got {prize_vnd}")
    excess = max(0, prize_vnd - TAX_FREE_VND)
    return excess * int(RATE * 100) // 100


def take_home_vnd(prize_vnd: int) -> int:
    """What actually reaches the winner from a single prize."""
    return prize_vnd - withheld_vnd(prize_vnd)
