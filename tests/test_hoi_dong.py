"""The Council's server half: what a verdict row is, what is due, and what can be afforded.

The scoring is not here - it runs in the reader's browser, because the only usable price
sources forbid automated collection or carry no licence to republish what is derived from them.
Its rules are pinned in tests/test_trader_js.py, against the file that actually applies them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tientrivutru.hoi_dong import (
    PRICES,
    Asset,
    UnknownModelPrice,
    Verdict,
    can_afford,
    cost_usd,
    due_assets,
    local_date,
    month_spend,
    prices_are_fresh,
    reserve_usd,
    sitting_cost,
)

BTC = Asset("BTC-USD", "crypto", "UTC")
FPT = Asset("FPT.VN", "vn_stock", "Asia/Ho_Chi_Minh")
ASSETS = {a.key: a for a in (BTC, FPT)}
TEST_PRICES = {"m": (3.0, 15.0), "cheap": (0.1, 0.5), "dear": (2.0, 10.0)}


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


def verdict(asset: str = "BTC-USD", day: str = "2026-09-21", committed: str | None = None,
            rating: str | None = "Buy", status: str = "ok", cost: float = 0.0,
            model: str = "m") -> Verdict:
    """Written at 12:10 UTC on its own day unless told otherwise - the cron's time."""
    return Verdict(
        asset=asset, trade_date=date.fromisoformat(day),
        committed_at=at(committed or f"{day}T12:10:00+00:00"),
        status=status, rating=rating, model={"provider": "p", "deep": model, "quick": model},
        usage={"llm_calls": 1, "tokens_in": 0, "tokens_out": 0, "cost_usd": cost},
    )


# --- the record itself ----------------------------------------------------------------------

def test_verdict_round_trips():
    v = verdict(rating="Underweight")
    assert Verdict.from_dict(v.to_dict()) == v


def test_a_verdict_row_carries_no_price_and_no_prose():
    """What is committed is only what is the repo's own. A price, a return or a paragraph of
    model output quoting a news source would each be data this repo has no licence to publish."""
    assert set(verdict().to_dict()) == {
        "asset", "trade_date", "committed_at", "status", "rating", "model", "upstream",
        "usage", "error",
    }


def test_an_ok_verdict_needs_a_real_rating():
    with pytest.raises(ValueError):
        verdict(rating="Strong Buy")
    with pytest.raises(ValueError):
        verdict(rating=None)


def test_anything_but_ok_carries_no_rating():
    """REVIEW is not Hold: Hold is a position, REVIEW is the absence of one."""
    with pytest.raises(ValueError):
        verdict(status="review", rating="Buy")
    with pytest.raises(ValueError):
        verdict(status="exploded", rating=None)


def test_committed_at_must_carry_a_timezone():
    with pytest.raises(ValueError):
        Verdict(asset="BTC-USD", trade_date=date(2026, 9, 21),
                committed_at=datetime(2026, 9, 21, 12, 10), status="ok", rating="Buy")


def test_committed_at_is_stored_in_utc():
    v = Verdict(asset="BTC-USD", trade_date=date(2026, 9, 21),
                committed_at=at("2026-09-21T19:10:00+07:00"), status="ok", rating="Buy")
    assert v.committed_at == datetime(2026, 9, 21, 12, 10, tzinfo=UTC)


# --- the budget -----------------------------------------------------------------------------

def test_cost_comes_from_real_tokens():
    assert cost_usd(1_000_000, 500_000, "m", prices=TEST_PRICES) == pytest.approx(3.0 + 7.5)


def test_unknown_model_price_refuses():
    """A cap enforced against a price nobody looked up is not a cap."""
    with pytest.raises(UnknownModelPrice):
        cost_usd(1, 1, "never-priced", prices=TEST_PRICES)
    with pytest.raises(UnknownModelPrice):
        sitting_cost(1, 1, "cheap", "never-priced", prices=TEST_PRICES)


def test_one_model_is_priced_exactly():
    assert sitting_cost(1_000_000, 100_000, "cheap", "cheap", prices=TEST_PRICES) == \
        pytest.approx(0.15)


def test_two_models_are_priced_at_the_dearer_rate():
    """Tokens are counted per sitting, not per model, so a mixed sitting is priced as if every
    token went to the dearer model - an upper bound, the safe side of a cap."""
    assert sitting_cost(1_000_000, 100_000, "cheap", "dear", prices=TEST_PRICES) == \
        pytest.approx(3.0)


def test_failed_runs_still_count_against_the_budget():
    rows = [verdict(cost=1.0), verdict(status="failed", rating=None, cost=2.5, day="2026-09-22"),
            verdict(cost=9.0, day="2026-08-31")]
    assert month_spend(rows, "2026-09") == pytest.approx(3.5)


def test_reserve_is_the_worst_recent_sitting_of_that_model():
    rows = [verdict(cost=c, day=f"2026-09-{d:02d}") for d, c in
            [(1, 9.0), (2, 1.0), (3, 2.0), (4, 3.0), (5, 1.5), (6, 1.0)]]
    assert reserve_usd(rows, "m", first_run=4.0) == pytest.approx(3.0), "only the last five"
    assert reserve_usd(rows, "other-model", first_run=4.0) == pytest.approx(4.0)


def test_a_skipped_day_is_not_a_cost_sample():
    """A skip cost nothing, so letting it into the reserve would make the next sitting look
    cheaper than any real one has been."""
    rows = [verdict(cost=5.0), verdict(status="skipped_budget", rating=None, day="2026-09-22")]
    assert reserve_usd(rows, "m", first_run=0.0) == pytest.approx(5.0)


def test_budget_skips_when_the_reserve_would_cross_the_cap():
    """Spent 9 + 2 = 11, and the reserve is the WORST recent sitting (9), not the latest (2):
    the next sitting is only affordable if the cap covers 20."""
    rows = [verdict(cost=9.0), verdict(cost=2.0, day="2026-09-22")]
    assert not can_afford(rows, cap=19.99, model_id="m", month="2026-09", first_run=0.0)
    assert can_afford(rows, cap=20.0, model_id="m", month="2026-09", first_run=0.0)


def test_a_stale_price_table_is_not_trusted():
    """Providers reprice without notice; after a quarter the table is re-read, not assumed."""
    assert prices_are_fresh(date(2026, 12, 22), checked=date(2026, 9, 23))
    assert not prices_are_fresh(date(2026, 12, 23), checked=date(2026, 9, 23))


def test_every_listed_price_is_positive_and_output_costs_more():
    """A zero or swapped price would let the cap wave through a sitting it should have stopped."""
    assert PRICES, "the table was filled from research/gia-model"
    for model, (per_in, per_out) in PRICES.items():
        assert 0 < per_in < per_out, model


# --- what is due today ----------------------------------------------------------------------

def test_today_is_the_asset_s_own_date():
    now = at("2026-09-23T18:00:00+00:00")
    assert local_date(BTC, now) == date(2026, 9, 23)
    assert local_date(FPT, now) == date(2026, 9, 24), "01:00 in Vietnam is already tomorrow"


def test_vn_sits_monday_to_friday_btc_every_day():
    saturday = at("2026-09-19T12:10:00+00:00")
    friday = at("2026-09-18T12:10:00+00:00")
    assert [a.key for a in due_assets([], saturday, assets=ASSETS)] == ["BTC-USD"]
    assert [a.key for a in due_assets([], friday, assets=ASSETS)] == ["BTC-USD", "FPT.VN"]


def test_the_weekday_is_vietnam_s_not_utc_s():
    """Friday 18:00 UTC is already Saturday 01:00 in Vietnam: no session to sit on."""
    late_friday_utc = at("2026-09-18T18:00:00+00:00")
    assert [a.key for a in due_assets([], late_friday_utc, assets=ASSETS)] == ["BTC-USD"]


def test_nothing_is_due_twice():
    """Whatever the first attempt's status - a skipped or failed day stays skipped or failed."""
    thursday = at("2026-09-17T12:10:00+00:00")
    existing = [verdict(day="2026-09-17", status="failed", rating=None),
                verdict(asset="FPT.VN", day="2026-09-17", status="skipped_budget", rating=None)]
    assert due_assets(existing, thursday, assets=ASSETS) == ()


# --- what the page receives -----------------------------------------------------------------

def test_the_page_gets_ratings_and_the_month_s_budget():
    from tientrivutru.hoi_dong import council_payload

    rows = [
        verdict(cost=0.4),
        verdict(asset="FPT.VN", day="2026-09-22", cost=0.3),
        verdict(day="2026-09-23", status="skipped_budget", rating=None),
        verdict(day="2026-08-31", cost=9.0),
    ]
    rows = [Verdict.from_dict({**r.to_dict(), "usage": {**r.usage, "cap_usd": 1.0}})
            for r in rows]
    payload = council_payload(rows, at("2026-09-23T13:00:00+00:00"))
    assert payload["month"] == "2026-09"
    assert payload["spent_usd"] == pytest.approx(0.7)
    assert payload["cap_usd"] == 1.0
    assert payload["stopped"] is True
    assert {v["asset"] for v in payload["verdicts"]} == {"BTC-USD", "FPT.VN"}
    first = payload["verdicts"][0]
    assert set(first) == {"asset", "trade_date", "committed_at", "status", "rating", "memory"}


def test_the_page_is_told_which_verdicts_could_remember():
    """Rows written before ticket 09 have no memory flag: that Council could not remember."""
    from tientrivutru.hoi_dong import council_payload

    old = verdict(day="2026-09-21")
    new = Verdict.from_dict({**verdict(day="2026-09-22").to_dict(),
                             "usage": {"cost_usd": 0.0, "memory": True}})
    rows = council_payload([old, new], at("2026-09-23T13:00:00+00:00"))["verdicts"]
    assert [r["memory"] for r in rows] == [False, True]


def test_an_empty_council_is_a_valid_payload():
    from tientrivutru.hoi_dong import council_payload

    payload = council_payload([], at("2026-09-23T13:00:00+00:00"))
    assert payload["verdicts"] == [] and payload["spent_usd"] == 0 and payload["cap_usd"] is None
    assert payload["stopped"] is False


def test_the_page_is_told_when_the_council_runs_for_free():
    from tientrivutru.hoi_dong import council_payload

    free = Verdict.from_dict({**verdict().to_dict(),
                              "usage": {"cost_usd": 0.0, "billing": "free"}})
    assert council_payload([free], at("2026-09-21T13:00:00+00:00"))["billing"] == "free"
    assert council_payload([free], at("2026-09-21T13:00:00+00:00"))["provider"] == "p"
    paid = verdict(cost=0.2)
    assert council_payload([paid], at("2026-09-21T13:00:00+00:00"))["billing"] == "paid"
    assert council_payload([], at("2026-09-21T13:00:00+00:00"))["billing"] is None
