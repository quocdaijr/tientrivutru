"""Vietnamese personal income tax on a prize.

Here because the page advertises jackpot figures. Quoting 34.9 billion while staying quiet
about the 3.49 billion withheld from it is what the scam sites do, and this repository is
built on the opposite promise.
"""

from __future__ import annotations

import pytest

from tientrivutru import tax


def test_a_prize_at_the_threshold_is_untaxed():
    """The law taxes the portion ABOVE 10 million, so exactly 10 million owes nothing -
    which is why Mega's first prize is the largest one received whole."""
    assert tax.withheld_vnd(10_000_000) == 0
    assert tax.take_home_vnd(10_000_000) == 10_000_000


def test_a_prize_below_the_threshold_is_untaxed():
    assert tax.withheld_vnd(500_000) == 0


@pytest.mark.parametrize(
    "prize,expected",
    [
        (40_000_000, 3_000_000),
        (3_544_192_350, 353_419_235),
        (34_897_731_150, 3_488_773_115),
        (24_507_110_500, 2_449_711_050),
    ],
)
def test_ten_percent_of_the_excess_only(prize, expected):
    assert tax.withheld_vnd(prize) == expected


def test_take_home_is_the_prize_minus_the_withholding():
    prize = 34_897_731_150
    assert tax.take_home_vnd(prize) == prize - tax.withheld_vnd(prize)


def test_withholding_is_never_negative_and_never_exceeds_the_prize():
    for prize in (0, 1, 9_999_999, 10_000_001, 10**12):
        assert 0 <= tax.withheld_vnd(prize) <= prize


def test_a_negative_prize_is_refused():
    with pytest.raises(ValueError):
        tax.withheld_vnd(-1)


def test_the_threshold_is_named_not_inlined():
    """A magic 10_000_000 scattered through the code is how a law change becomes a bug."""
    assert tax.TAX_FREE_VND == 10_000_000
    assert tax.RATE == 0.10
