"""The Council's scoreboard, which runs in the reader's browser - so it is tested here, in Node.

Scoring happens client-side because the only usable price sources either forbid automated
collection (Yahoo's ToS) or carry no licence to republish what is derived from them. The repo
commits ratings and write times; site/hoi-dong.js fetches prices and applies the rules below.

Three rules carry the whole scoreboard. The window opens at the first bar AFTER the verdict was
written, so a late write can only move the window, never choose it. A bar the source reports
as missing is a hole, not a reason to slide to the next day. And a Vietnamese stock cannot be
shorted by a retail account, so a bearish verdict there is a flat position.

Every asset here is built with its own fees, never the module's constants, so these tests pin
the arithmetic rather than whatever the fee happens to be this year.

Skipped when Node is unavailable, same as test_trader_js.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SITE = Path(__file__).resolve().parents[1] / "site"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Real VNDIRECT response for FPT, recorded 2026-09-23, trimmed to the fields read. 09-18 is a
# corporate action: traded 74.5 -> 71.7, adjusted 67.728 -> 65.182, next session opens at 66.5.
VNDIRECT = {"data": [
    {"code": "FPT", "date": "2026-09-23", "open": 66.6, "close": 66.2, "adOpen": 66.6,
     "adClose": 66.2},
    {"code": "FPT", "date": "2026-09-22", "open": 66.6, "close": 66.6, "adOpen": 66.6,
     "adClose": 66.6},
    {"code": "FPT", "date": "2026-09-21", "open": 66.5, "close": 66.4, "adOpen": 66.5,
     "adClose": 66.4},
    {"code": "FPT", "date": "2026-09-18", "open": 74.5, "close": 71.7, "adOpen": 67.728,
     "adClose": 65.182},
    {"code": "FPT", "date": "2026-09-17", "open": 73.3, "close": 74.3, "adOpen": 66.637,
     "adClose": 67.546},
    {"code": "FPT", "date": "2026-09-16", "open": 72.8, "close": 73.8, "adOpen": 66.182,
     "adClose": 67.092},
    {"code": "FPT", "date": "2026-09-15", "open": 72.7, "close": 72.7, "adOpen": 66.092,
     "adClose": 66.092},
]}

BTC = {"key": "BTC-USD", "kind": "crypto", "canShort": True, "fee": 0.001, "tax": 0,
       "exitOffset": 0}
FPT = {"key": "FPT.VN", "kind": "vn_stock", "canShort": False, "fee": 0.0015, "tax": 0.001,
       "exitOffset": 2}

PRELUDE = """
const sec = (iso) => Date.parse(iso) / 1000;
const daily = (day, o, c, hour = 0) =>
  ({ t: sec(`${day}T${String(hour).padStart(2, '0')}:00:00Z`), o, c });
const vn = (day, o, c) => daily(day, o, c, 2);
const verdict = (day, rating = 'Buy', status = 'ok', asset = 'BTC-USD') =>
  ({ asset, trade_date: day, committed_at: `${day}T12:10:00Z`, status, rating });
const rowsOf = (n, seed, aligned) => {
  const rnd = window.TienTriVuTruPersonal.seededRandom(seed);
  const rows = [];
  for (let i = 0; i < n; i++) {
    const r = (rnd() - 0.5) * 0.06;
    const rating = aligned ? (r > 0 ? 'Buy' : 'Sell') : H.RATINGS[Math.floor(rnd() * 5)];
    const pos = H.position(rating, BTC);
    rows.push({ trade_date: `d${i}`, rating, position: pos, ret: r,
                council: H.net(pos, r, BTC), alwaysBuy: H.net(1, r, BTC), coin: 0 });
  }
  return rows;
};
const windowAt = (bars, committed, now, asset = BTC) => {
  const w = H.windowFor(bars, sec(committed), asset, sec(now));
  return w && { entry: new Date(w.entry.t * 1000).toISOString(),
                exit: new Date(w.exit.t * 1000).toISOString(), gap: w.gap };
};
const BTC_BARS = [20, 21, 22, 23, 24, 25].map((d) => daily(`2026-09-${d}`, 100 + d, 101 + d));
"""


def out(expr: str):
    """Evaluate one JS expression against the real site/hoi-dong.js and return it as JSON."""
    script = f"""
    global.window = {{}};
    global.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
    require({str(SITE / "dom.js")!r});
    require({str(SITE / "personal.js")!r});
    require({str(SITE / "hoi-dong.js")!r});
    const H = window.TienTriVuTruHoiDong;
    const BTC = {json.dumps(BTC)};
    const FPT = {json.dumps(FPT)};
    const VNDIRECT = {json.dumps(VNDIRECT)};
    {PRELUDE}
    console.log(JSON.stringify({expr}));
    """
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=120,
                            check=False)
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


def test_hoi_dong_js_loads_without_a_dom():
    assert out("Object.keys(H).length > 0") is True


# --- rating -> position ---------------------------------------------------------------

def test_review_is_not_a_position():
    """TradingAgents' own rule, #1170: a decision nobody can read is not a Hold."""
    assert out("[null, 'REVIEW', 'Strong Buy'].map((r) => H.position(r, BTC))") == [None] * 3


def test_btc_can_go_short():
    assert out("H.RATINGS.map((r) => H.position(r, BTC))") == [1, 0.5, 0, -0.5, -1]


def test_vn_cannot_go_short():
    """A retail account on HOSE cannot sell shares it does not hold (Circular 120/2020 Art. 7),
    so Underweight and Sell are 'stay out' - no credit for a fall it could not have traded."""
    assert out("H.RATINGS.map((r) => H.position(r, FPT))") == [1, 0.5, 0, 0, 0]


# --- the window --------------------------------------------------------------------------

def test_window_starts_at_the_first_bar_after_commit():
    w = out("windowAt(BTC_BARS, '2026-09-21T12:10:00Z', '2026-09-24T00:00:00Z')")
    assert w == {"entry": "2026-09-22T00:00:00.000Z", "exit": "2026-09-22T00:00:00.000Z",
                 "gap": False}


def test_a_late_commit_only_moves_the_window():
    """Writing after midnight cannot buy a better entry - it just gets the next bar. This is
    what replaces the lottery's 'no prophesying a settled draw' guard."""
    got = out("[windowAt(BTC_BARS, '2026-09-21T23:59:00Z', '2026-09-26T00:00:00Z').entry,"
              " windowAt(BTC_BARS, '2026-09-22T00:00:01Z', '2026-09-26T00:00:00Z').entry]")
    assert [g[:10] for g in got] == ["2026-09-22", "2026-09-23"]


def test_a_commit_exactly_on_the_open_misses_that_bar():
    got = out("windowAt(BTC_BARS, '2026-09-22T00:00:00Z', '2026-09-26T00:00:00Z').entry")
    assert got.startswith("2026-09-23")


def test_window_is_none_while_the_exit_bar_is_live():
    got = out("[windowAt(BTC_BARS, '2026-09-21T12:10:00Z', '2026-09-22T23:59:59Z'),"
              " windowAt(BTC_BARS, '2026-09-21T12:10:00Z', '2026-09-23T00:00:00Z') !== null]")
    assert got == [None, True]


def test_window_is_none_before_the_feed_reaches_it():
    """No bar after the write at all is the feed not having got there - pending, not a hole."""
    got = out("windowAt([daily('2026-09-20', 1, 1), daily('2026-09-21', 1, 1)],"
              " '2026-09-21T12:10:00Z', '2026-09-30T00:00:00Z')")
    assert got is None


def test_vn_exits_at_the_close_of_session_t_plus_two():
    """Sessions, not calendar days: the weekend in the middle has no bar and does not count.
    Shares bought in session T can be sold from the afternoon of T+2 (HOSE guide, VSDC 2022)."""
    got = out("windowAt([vn('2026-09-17', 60, 61), vn('2026-09-18', 61, 62),"
              " vn('2026-09-21', 62, 63), vn('2026-09-22', 63, 64), vn('2026-09-23', 64, 65)],"
              " '2026-09-17T12:10:00Z', '2026-09-24T00:00:00Z', FPT)")
    assert got == {"entry": "2026-09-18T02:00:00.000Z", "exit": "2026-09-22T02:00:00.000Z",
                   "gap": False}


def test_a_missing_price_is_a_hole_not_a_reason_to_slide():
    """Yahoo returned open/close = null for BTC-USD on 2026-09-22 (measured). Sliding past it
    would quietly enter a day late; the verdict is left unscored instead."""
    got = out("windowAt([daily('2026-09-21', 1, 1), daily('2026-09-22', null, null),"
              " daily('2026-09-23', 2, 2)], '2026-09-21T12:10:00Z', '2026-09-25T00:00:00Z')")
    assert got["entry"].startswith("2026-09-22") and got["gap"] is True


def test_a_missing_crypto_day_is_a_hole_too():
    """BTC trades every day, so the entry bar's date is knowable. If the feed drops the day
    altogether, the next bar in the list is NOT the entry - it is a day too late."""
    got = out("windowAt([daily('2026-09-21', 1, 1), daily('2026-09-23', 2, 2)],"
              " '2026-09-21T12:10:00Z', '2026-09-25T00:00:00Z')")
    assert got["entry"].startswith("2026-09-22") and got["gap"] is True


# --- money ------------------------------------------------------------------------------

def test_net_return_charges_both_sides():
    """Buy fee on the entry notional, sell fee on the exit notional."""
    got = out("[H.net(1, 0.10, BTC), H.net(-1, 0.10, BTC)]")
    assert got == pytest.approx([0.10 - 0.001 * 2.10, -0.10 - 0.001 * 2.10])


def test_vn_sell_tax_is_charged_on_the_sale():
    """Tax is 0.1 percent of the sale value, Personal Income Tax Law 109/2025/QH15 Art. 13."""
    expected = 0.10 - 0.0015 * 2.10 - 0.001 * 1.10
    assert out("[H.net(1, 0.10, FPT), H.net(0.5, 0.10, FPT)]") == pytest.approx(
        [expected, expected / 2])


def test_hold_costs_nothing():
    assert out("H.net(0, 0.37, FPT)") == 0


def test_the_shipped_fees_are_the_researched_ones():
    """research/phi-thue-t2, 2026-09-23: Binance/OKX regular taker 0.1 percent; SSI and VPS
    online 0.15 percent; sale tax 0.1 percent; exit at the T+2 close; no retail shorting."""
    got = out("Object.values(H.ASSETS).map((a) => [a.key, a.fee, a.tax, a.exitOffset, a.canShort])")
    assert got == [
        ["BTC-USD", 0.001, 0, 0, True],
        ["FPT.VN", 0.0015, 0.001, 2, False],
        ["VNM.VN", 0.0015, 0.001, 2, False],
        ["VCB.VN", 0.0015, 0.001, 2, False],
    ]


# --- VNDIRECT, and why the adjusted price is the honest one ------------------------------

def test_vndirect_bars_open_at_nine_in_vietnam():
    got = out("H.parseVndirect(VNDIRECT).map((b) => new Date(b.t * 1000).toISOString())")
    assert got[0] == "2026-09-15T02:00:00.000Z" and got[-1] == "2026-09-23T02:00:00.000Z"
    assert got == sorted(got)


def test_vndirect_uses_the_adjusted_price():
    """FPT on 2026-09-18 traded 74.5 -> 71.7, then the next session opened at 66.5: a corporate
    action, not a crash. Scored on traded prices, a position held across it shows a loss the
    holder never had, because they received the new shares. The adjusted series is their P&L."""
    got = out("H.parseVndirect(VNDIRECT).filter((b) => b.t === sec('2026-09-18T02:00:00Z'))")
    assert got == [{"t": 1789696800, "o": 67.728, "c": 65.182}]


def test_vndirect_rejects_a_shape_it_does_not_send():
    got = out("[{}, {data: [{date: 'x'}]}, {data: [{date: '2026-09-18'}]}].map((p) => {"
              " try { H.parseVndirect(p); return false; } catch (e) { return true; } })")
    assert got == [True, True, True]


# --- baselines -----------------------------------------------------------------------------

def test_coin_is_deterministic_and_covers_all_five_tiers():
    got = out("""(() => {
      const day = (i) => new Date(Date.UTC(2000, 0, 1 + i)).toISOString().slice(0, 10);
      const a = [], b = [];
      for (let i = 0; i < 10000; i++) {
        a.push(H.coinRating('BTC-USD', day(i)));
        b.push(H.coinRating('BTC-USD', day(i)));
      }
      const counts = {};
      a.forEach((r) => { counts[r] = (counts[r] || 0) + 1; });
      return { same: JSON.stringify(a) === JSON.stringify(b), counts };
    })()""")
    assert got["same"] is True
    assert set(got["counts"]) == {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
    assert all(1800 <= n <= 2200 for n in got["counts"].values()), got["counts"]


def test_the_coin_depends_on_the_asset():
    got = out("""(() => {
      const d = [];
      for (let i = 0; i < 50; i++) d.push(new Date(Date.UTC(2026, 0, 1 + i)).toISOString());
      return JSON.stringify(d.map((x) => H.coinRating('BTC-USD', x))) !==
             JSON.stringify(d.map((x) => H.coinRating('FPT.VN', x)));
    })()""")
    assert got is True


def test_baselines_use_the_same_window_and_fees():
    got = out("""(() => {
      const bars = [daily('2026-09-21', 100, 100), daily('2026-09-22', 100, 110)];
      const [row] = H.scoreAsset([verdict('2026-09-21', 'Overweight')], bars, BTC,
                                 sec('2026-09-24T00:00:00Z')).rows;
      const coin = H.position(H.coinRating('BTC-USD', '2026-09-21'), BTC);
      return { row, want: [H.net(0.5, 0.1, BTC), H.net(1, 0.1, BTC), H.net(coin, 0.1, BTC)] };
    })()""")
    row = got["row"]
    assert [row["council"], row["alwaysBuy"], row["coin"]] == pytest.approx(got["want"])


def test_only_ok_verdicts_are_scored_and_the_rest_are_counted():
    got = out("""(() => {
      const bars = [daily('2026-09-21', 1, 1), daily('2026-09-22', 1, 2),
                    daily('2026-09-24', 1, 1), daily('2026-09-26', 1, 1)];
      return H.scoreAsset([
        verdict('2026-09-21'),
        verdict('2026-09-20', null, 'review'),
        verdict('2026-09-19', null, 'skipped_budget'),
        verdict('2026-09-18', null, 'failed'),
        verdict('2026-09-21', 'Buy', 'ok', 'FPT.VN'),
        verdict('2026-09-22'),
        verdict('2026-09-26'),
      ], bars, BTC, sec('2026-09-27T00:00:00Z')).counts;
    })()""")
    # 09-22's entry would be 09-23, which the feed skipped: a hole. 09-26 has nothing after it.
    assert got == {"scored": 1, "pending": 1, "gap": 1, "review": 1, "skipped_budget": 1,
                   "failed": 1}


# --- is it better than chance? --------------------------------------------------------

def test_p_is_null_below_thirty():
    got = out("[H.summarize(rowsOf(H.MIN_SCORED_FOR_P - 1, 's', false), BTC, 's').p,"
              " H.summarize(rowsOf(H.MIN_SCORED_FOR_P, 's', false), BTC, 's').p !== null]")
    assert got == [None, True]


def test_p_is_roughly_uniform_for_random_ratings():
    """Under the null the p-value must not lean toward 'significant' - otherwise the page would
    manufacture the very finding it exists to debunk."""
    got = out("""(() => {
      const ps = [];
      for (let i = 0; i < 200; i++) ps.push(H.permutationP(rowsOf(30, 't' + i, false), BTC,
                                                           'p' + i, 299));
      return { mean: ps.reduce((a, b) => a + b) / ps.length,
               low: ps.filter((p) => p < 0.05).length / ps.length };
    })()""")
    assert 0.40 <= got["mean"] <= 0.60
    assert got["low"] <= 0.10


def test_p_can_actually_detect_an_edge():
    """A test with no power would pass the uniformity check too. A council that is right every
    time must come back significant."""
    assert out("H.permutationP(rowsOf(40, 'a', true), BTC, 's', 999)") < 0.01


def test_summary_reports_all_three_side_by_side():
    got = out("H.summarize(rowsOf(5, 'x', false), BTC, 's')")
    assert got["n"] == 5
    for who in ("council", "alwaysBuy", "coin"):
        assert set(got[who]) == {"mean", "sum", "hitRate"}


# --- the page itself ----------------------------------------------------------------------

def test_the_trader_page_loads_the_council_before_trader_js():
    html = (SITE / "trader.html").read_text(encoding="utf-8")
    assert (html.index('src="./personal.js"') < html.index('src="./hoi-dong.js"')
            < html.index('src="./trader.js"'))


def test_the_page_labels_the_council_as_ai_and_says_it_reads_yahoo():
    """Every provider researched requires or recommends an AI-generated label, DeepSeek in these
    words - generated by AI, may contain errors, for reference only. And the Council's own data
    layer reads Yahoo automatically, which the page states rather than hides."""
    js = (SITE / "hoi-dong.js").read_text(encoding="utf-8")
    assert "do AI tạo" in js and "có thể sai" in js and "chỉ để tham khảo" in js
    assert "Yahoo" in js


def test_the_js_and_python_pin_the_same_upstream():
    """Two copies of one commit hash is how they drift; this is the check that they have not."""
    from tientrivutru.hoi_dong import UPSTREAM

    assert out("H.UPSTREAM") == UPSTREAM


def test_the_free_tier_is_named_and_its_data_use_disclosed():
    """No invented spend on a free key; and Google's free-tier data use said out loud."""
    got = out("[H.freeLine('google'), H.freeLine('deepseek')]")
    assert "không tốn đồng nào" in got[0] and "cải thiện sản phẩm" in got[0]
    assert "không tốn đồng nào" in got[1] and "Google" not in got[1]
