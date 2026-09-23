"""One sitting of the Council, with the Council replaced by a fake.

TradingAgents is not a dependency of this package - it is installed only inside the workflow
step that runs it - so the runner takes its graph and its token counter as arguments and these
tests hand it stand-ins. What is pinned is everything this repo decides: which config the real
graph would get, what is written when it answers, when it cannot be read, and when it crashes.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tientrivutru.hoi_dong import ASSETS
from tientrivutru.hoi_dong_run import Model, council_config, run_verdict

PRICES = {"cheap": (0.10, 0.50), "dear": (2.0, 10.0)}
MODEL = Model(provider="openai", deep="cheap", quick="cheap")


class FakeCounter:
    def __init__(self, calls: int = 14, tokens_in: int = 1_000_000, tokens_out: int = 200_000):
        self._stats = {"llm_calls": calls, "tokens_in": tokens_in, "tokens_out": tokens_out}

    def stats(self) -> dict:
        return dict(self._stats)


class FakeGraph:
    def __init__(self, config, callbacks, *, signal="Overweight", boom=None):
        self.config, self.callbacks, self.signal, self.boom = config, callbacks, signal, boom
        self.calls = []

    def propagate(self, ticker, trade_date, asset_type="stock"):
        self.calls.append((ticker, trade_date, asset_type))
        if self.boom:
            raise self.boom
        return {
            "investment_debate_state": {
                "bull_history": "Bull Analyst: momentum, per a Reuters headline.",
                "bear_history": "Bear Analyst: valuation is stretched.",
                "judge_decision": "",
            },
        }, self.signal


def sit(asset="BTC-USD", *, signal="Overweight", boom=None, counter=None, graphs=None,
        now=lambda: datetime(2026, 9, 23, 12, 14, 5, tzinfo=UTC)):
    graphs = [] if graphs is None else graphs

    def factory(config, callbacks):
        graph = FakeGraph(config, callbacks, signal=signal, boom=boom)
        graphs.append(graph)
        return graph

    return run_verdict(
        ASSETS[asset], date(2026, 9, 23), model=MODEL, graph_factory=factory,
        counter_factory=lambda: counter or FakeCounter(), base_config=dict, prices=PRICES,
        now=now,
    )


def test_the_module_imports_without_tradingagents():
    """The package, the CLI and every other test import this module; none of them may drag in
    langchain. The heavy import happens inside run_verdict, and only for a real sitting."""
    probe = ("import sys, tientrivutru.hoi_dong_run; "
             "print('tradingagents' in sys.modules, 'langchain_core' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.split() == ["False", "False"]


def test_an_answer_becomes_an_ok_verdict_with_its_real_cost():
    v = sit()
    assert (v.status, v.rating) == ("ok", "Overweight")
    assert v.usage == {"llm_calls": 14, "tokens_in": 1_000_000, "tokens_out": 200_000,
                       "billing": "paid", "cost_usd": pytest.approx(0.10 + 0.10)}
    assert v.model == {"provider": "openai", "deep": "cheap", "quick": "cheap"}


def test_an_unreadable_answer_is_review_not_hold():
    v = sit(signal="REVIEW")
    assert (v.status, v.rating) == ("review", None)
    assert v.cost_usd > 0, "the tokens were still bought"


def test_a_crash_is_failed_and_still_costs():
    v = sit(boom=RuntimeError("upstream exploded"))
    assert v.status == "failed" and v.rating is None
    assert v.cost_usd == pytest.approx(0.20)
    assert v.error == "RuntimeError: upstream exploded"


def test_a_crash_message_cannot_publish_a_key():
    """The error lands in a public repo. Whatever a provider SDK echoes back, a key-shaped
    string does not survive the trip."""
    leaky = RuntimeError("401 for key sk-proj-AbCdEf0123456789XyZ on https://api.x/v1")
    v = sit(boom=leaky)
    assert "sk-proj-AbCdEf0123456789XyZ" not in v.error
    assert "[redacted]" in v.error


def test_a_long_crash_message_is_cut():
    v = sit(boom=ValueError("x" * 5_000))
    assert len(v.error) <= 500


def test_the_verdict_is_stamped_after_the_sitting_ends():
    """committed_at is when the rating became known. Stamping the start would open the window
    on a bar the Council was still deliberating through - so the clock is read once, after."""
    events = []
    end = datetime(2026, 9, 23, 12, 31, tzinfo=UTC)

    class Recording(FakeGraph):
        def propagate(self, *args, **kwargs):
            events.append("propagate")
            return super().propagate(*args, **kwargs)

    def clock():
        events.append("now")
        return end

    v = run_verdict(ASSETS["BTC-USD"], date(2026, 9, 23), model=MODEL,
                    graph_factory=lambda cfg, cbs: Recording(cfg, cbs),
                    counter_factory=FakeCounter, base_config=dict, prices=PRICES, now=clock)
    assert events == ["propagate", "now"]
    assert v.committed_at == end


def test_crypto_and_stocks_take_their_own_pipeline():
    graphs = []
    sit("BTC-USD", graphs=graphs)
    sit("FPT.VN", graphs=graphs)
    assert [g.calls[0] for g in graphs] == [
        ("BTC-USD", "2026-09-23", "crypto"), ("FPT.VN", "2026-09-23", "stock")]


def test_no_model_prose_leaves_the_sitting():
    """The debate quotes sources nobody licensed for republication; only the rating is kept."""
    row = sit().to_dict()
    assert "Reuters" not in str(row) and "valuation" not in str(row)


# --- the config the real graph would get ------------------------------------------------

def test_memory_and_logs_never_land_in_the_repo(tmp_path):
    """A council with no memory is the default; and a memory that did exist must not be written
    somewhere a commit could pick it up."""
    cfg = council_config({"memory_log_path": "/home/x/.tradingagents/memory.md"}, MODEL, tmp_path)
    for key in ("memory_log_path", "results_dir", "data_cache_dir"):
        assert Path(cfg[key]).is_relative_to(tmp_path), key


def test_temperature_is_left_to_the_provider(tmp_path):
    """Research 03: a non-default temperature is a 400 on Claude Sonnet 5 and Opus 5, and makes
    Gemini 3 prone to looping. The runner does not touch it."""
    assert "temperature" not in council_config({}, MODEL, tmp_path)
    assert council_config({"temperature": None}, MODEL, tmp_path)["temperature"] is None


def test_the_model_choice_reaches_the_graph(tmp_path):
    cfg = council_config({"llm_provider": "openai", "deep_think_llm": "x"},
                         Model("anthropic", "claude-sonnet-5", "claude-haiku-4-5"), tmp_path)
    assert (cfg["llm_provider"], cfg["deep_think_llm"], cfg["quick_think_llm"]) == (
        "anthropic", "claude-sonnet-5", "claude-haiku-4-5")
    assert cfg["checkpoint_enabled"] is False


# --- the gate in front of a real sitting --------------------------------------------------

from tientrivutru.hoi_dong_run import council_settings  # noqa: E402

GOOD_ENV = {
    "TRADINGAGENTS_LLM_PROVIDER": "openai",
    "TRADINGAGENTS_DEEP_THINK_LLM": "gpt-5.6-luna",
    "HOI_DONG_MONTHLY_CAP_USD": "10",
}
TODAY = date(2026, 9, 23)


def test_a_complete_env_yields_a_model_and_a_cap():
    model, cap, problems = council_settings(GOOD_ENV, TODAY)
    assert problems == []
    assert model == Model("openai", "gpt-5.6-luna", "gpt-5.6-luna"), "quick defaults to deep"
    assert cap == 10.0


@pytest.mark.parametrize("drop", sorted(GOOD_ENV))
def test_every_setting_is_required(drop):
    """No default model and no default cap: a sitting that spends real money on a guess is the
    one thing this command must never do."""
    env = {k: v for k, v in GOOD_ENV.items() if k != drop}
    _, _, problems = council_settings(env, TODAY)
    assert any(drop in p for p in problems), problems


@pytest.mark.parametrize("cap", ["ten", "0", "-5", "nan", "inf"])
def test_a_cap_must_be_a_positive_finite_number(cap):
    _, _, problems = council_settings({**GOOD_ENV, "HOI_DONG_MONTHLY_CAP_USD": cap}, TODAY)
    assert problems


def test_an_unpriced_model_is_refused():
    env = {**GOOD_ENV, "TRADINGAGENTS_QUICK_THINK_LLM": "some-new-model"}
    _, _, problems = council_settings(env, TODAY)
    assert any("some-new-model" in p for p in problems)


def test_a_stale_price_table_blocks_the_sitting():
    _, _, problems = council_settings(GOOD_ENV, date(2027, 6, 1))
    assert any("PRICES" in p for p in problems)


# --- the free tier ---------------------------------------------------------------------------

FREE_ENV = {
    "TRADINGAGENTS_LLM_PROVIDER": "google",
    "TRADINGAGENTS_DEEP_THINK_LLM": "gemini-3.1-flash-lite",
    "HOI_DONG_BILLING": "free",
}


def test_the_free_tier_needs_no_money_cap():
    """On a Google project without billing there is no account to charge: going past the limit
    gets a rate-limit error, never a bill. That is the cap, and it is Google's, not ours."""
    model, cap, problems = council_settings(FREE_ENV, TODAY)
    assert problems == []
    assert model == Model("google", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite")
    assert cap is None


def test_a_billing_mode_nobody_defined_is_refused():
    _, _, problems = council_settings({**FREE_ENV, "HOI_DONG_BILLING": "maybe"}, TODAY)
    assert any("HOI_DONG_BILLING" in p for p in problems)


def test_paid_is_the_default_and_still_needs_its_cap():
    env = {k: v for k, v in FREE_ENV.items() if k != "HOI_DONG_BILLING"}
    _, _, problems = council_settings(env, TODAY)
    assert any("HOI_DONG_MONTHLY_CAP_USD" in p for p in problems)


def test_a_free_sitting_costs_nothing_but_keeps_its_tokens():
    """The page must not say the Council burned money it did not burn - and the tokens are still
    worth recording, because they are what would be billed if the project ever turned it on."""
    v = run_verdict(ASSETS["BTC-USD"], date(2026, 9, 23), model=MODEL,
                    graph_factory=lambda cfg, cbs: FakeGraph(cfg, cbs),
                    counter_factory=FakeCounter, base_config=dict, prices=None)
    assert v.usage["cost_usd"] == 0.0
    assert v.usage["billing"] == "free"
    assert v.usage["tokens_in"] == 1_000_000


def test_an_error_keeps_enough_to_read_the_provider_s_instruction():
    """The trial run lost Google's actual instruction behind a 200-character cut ('Plea...').
    Long enough to read it; still bounded, still redacted."""
    msg = "429 RESOURCE_EXHAUSTED. " + "Your project has exceeded its monthly spending cap. " * 5
    v = sit(boom=RuntimeError(msg))
    assert len(v.error) > 250 and len(v.error) <= 500
