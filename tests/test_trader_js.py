"""The trader page detects candlestick patterns in the browser, then grades them on the very
same candles, so the detector and the grader are tested here rather than trusted.

Two things make that grading valid, and both are pinned below. The thresholds are ratios, so
multiplying every price by a thousand must not move a single count - otherwise the shuffled
series, which re-chains at a different price level, would be compared unfairly. And the
shuffle must move order and nothing else, so the multiset of candle shapes has to come back
identical.

Fixtures are a real Binance response recorded 2026-09-22 plus hand-built bars whose geometry
is stated in the comments. Following the convention the rest of the suite uses, the fetch is
never exercised - trader.js splits parse from fetch precisely so these run offline with no
HTTP mocking library.

Skipped when Node is unavailable, same as test_finance_js.py.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# --- a real response, trimmed to three rows -----------------------------------------

KLINES = [
    [1790070900000, "86172.00000000", "86176.01000000", "86132.00000000", "86142.00000000",
     "15.88714000", 1790070959999, "1368831.29934210", 2703, "9.79877000",
     "844215.46949110", "0"],
    [1790070960000, "86142.01000000", "86271.21000000", "86142.01000000", "86188.00000000",
     "23.89171000", 1790071019999, "2059747.61720930", 5843, "16.37529000",
     "1411669.01485530", "0"],
    [1790071020000, "86188.00000000", "86188.00000000", "86136.00000000", "86140.00000000",
     "6.24942000", 1790071079999, "538400.27497880", 1443, "2.09727000",
     "180671.26848260", "0"],
]

WS_TICK = {
    "e": "kline", "E": 1790069752031, "s": "BTCUSDT",
    "k": {"t": 1790069700000, "T": 1790069759999, "s": "BTCUSDT", "i": "1m",
          "o": "85916.77000000", "c": "85894.20000000", "h": "85916.77000000",
          "l": "85850.00000000", "v": "6.30170000", "n": 3695, "x": False},
}


def _bar(i, o, h, low, c):
    return {"t": 1790000000 + i * 60, "o": o, "h": h, "l": low, "c": c, "v": 1.0}


# Hand-built, one geometry per line. Indices are quoted by the tests, so this list is
# append-only in spirit: inserting a bar renumbers every expectation below it.
BARS = [
    _bar(0, 100.0, 101.0, 99.0, 100.05),    # 0  doji: body 0.05 of range 2.00 = 2.5%
    _bar(1, 100.0, 101.0, 99.0, 100.22),    # 1  NOT a doji: body 11% of range
    _bar(2, 100.0, 100.3, 99.0, 100.2),     # 2  hammer: body 0.20, lower wick 1.00 = 5x
    _bar(3, 100.0, 100.3, 99.62, 100.2),    # 3  NOT a hammer: lower wick 1.9x the body
    _bar(4, 100.15, 100.8, 99.8, 100.0),    # 4  a small red bar, the one about to be engulfed
    _bar(5, 99.9, 101.6, 99.8, 101.5),      # 5  bullish engulfing of bar 4
    _bar(6, 101.0, 101.2, 99.8, 100.0),     # 6  red again
    _bar(7, 100.1, 101.6, 99.8, 101.5),     # 7  NOT engulfing: opens 0.10 above bar 6 close
    _bar(8, 100.0, 102.2, 99.8, 101.0),     # 8  a plain green bar
    _bar(9, 101.2, 101.4, 99.4, 99.6),      # 9  bearish engulfing of bar 8
    _bar(10, 110.0, 110.2, 107.8, 108.0),   # 10 crow 1: solid red, body 83% of range
    _bar(11, 109.5, 109.6, 105.8, 106.0),   # 11 crow 2: opens inside bar 10's body
    _bar(12, 107.0, 107.1, 103.8, 104.0),   # 12 crow 3 -> three black crows lands here
    _bar(13, 104.0, 104.0, 104.0, 104.0),   # 13 a minute with no range at all
    # 14-19 are filler, shaped so that nothing fires: the indicators need a window,
    # and a stray engulfing here would make the counts below mean two things at once.
    _bar(14, 104.0, 105.0, 103.5, 104.8),
    _bar(15, 104.8, 105.4, 104.2, 104.4),
    _bar(16, 104.5, 106.0, 104.3, 105.9),
    _bar(17, 105.9, 106.1, 104.9, 105.1),
    _bar(18, 105.1, 105.6, 104.6, 105.5),
    _bar(19, 105.5, 106.4, 105.3, 106.2),
]


def _run(body: str):
    """trader.js needs dom.js and personal.js on window; it boots only when a DOM exists."""
    script = f"""
    global.window = {{}};
    global.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
    require({str(SITE / "dom.js")!r});
    require({str(SITE / "personal.js")!r});
    require({str(SITE / "trader.js")!r});
    const X = window.TienTriVuTruTrader;
    const KLINES = {json.dumps(KLINES)};
    const WS_TICK = {json.dumps(WS_TICK)};
    const BARS = {json.dumps(BARS)};
    {body}
    """
    result = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=120, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


def test_trader_js_loads_without_a_dom():
    """It must not build a chart when required from Node, and it must not reach for a canvas
    at load either - that guard is what makes the rest of this file possible."""
    assert _run("console.log(JSON.stringify(Object.keys(X).length > 0));") is True


# --- the two unit traps -------------------------------------------------------------

def test_kline_prices_are_numbers_not_strings():
    """Binance sends "86172.00000000". A string reaches the chart as NaN, silently."""
    got = _run("console.log(JSON.stringify(X.parseKlines(KLINES)[0]));")
    for k in ("o", "h", "l", "c", "v"):
        assert isinstance(got[k], (int, float)), f"{k} came back as {type(got[k])}"
    assert got["o"] == pytest.approx(86172.0)


def test_kline_time_is_seconds_not_milliseconds():
    """Lightweight Charts wants epoch seconds. Feeding it milliseconds renders the year
    50000 with no error anywhere, which is the most expensive silent bug on this page."""
    got = _run("console.log(JSON.stringify(X.parseKlines(KLINES).map(b => b.t)));")
    assert got == [1790070900, 1790070960, 1790071020]


def test_klines_come_back_strictly_ascending():
    """setData throws on a non-monotonic series, and so does update after a reconnect."""
    got = _run("""
      const t = X.parseKlines(KLINES).map(b => b.t);
      console.log(JSON.stringify(t.every((v, i) => i === 0 || v > t[i - 1])));
    """)
    assert got is True


def test_klines_throw_on_a_shape_binance_does_not_send():
    """A dead block beats a chart full of NaN candles."""
    got = _run("""
      const bad = [{}, [[1, 2]], [["x", "y", "z", "w", "v", "u"]], [[1, "0", "0", "0", "0", "1"]]];
      console.log(JSON.stringify(bad.map((b) => {
        try { X.parseKlines(b); return false; } catch (e) { return true; }
      })));
    """)
    assert got == [True, True, True, True]


def test_ws_event_only_closes_a_bar_when_x_is_true():
    got = _run("""
      const open = X.parseKlineEvent(WS_TICK);
      const shut = X.parseKlineEvent({ k: Object.assign({}, WS_TICK.k, { x: true }) });
      console.log(JSON.stringify({ t: open.bar.t, c: open.bar.c,
                                   openClosed: open.closed, shutClosed: shut.closed }));
    """)
    assert got == {"t": 1790069700, "c": pytest.approx(85894.2),
                   "openClosed": False, "shutClosed": True}


def test_ws_event_throws_on_a_frame_that_is_not_a_kline():
    got = _run("""
      console.log(JSON.stringify([{}, { e: 'trade' }, null].map((m) => {
        try { X.parseKlineEvent(m); return false; } catch (e) { return true; }
      })));
    """)
    assert got == [True, True, True]


# --- the detector: one function, two stages -----------------------------------------

def test_each_pattern_fires_on_its_textbook_candle():
    got = _run("console.log(JSON.stringify(BARS.map((_, i) => X.patternsAt(BARS, i))));")
    assert "doji" in got[0]
    assert "bua" in got[2]
    assert "nhanChimTang" in got[5]
    assert "nhanChimGiam" in got[9]
    assert "baConQua" in got[12]


def test_each_pattern_rejects_its_near_miss():
    """These are the exact thresholds, pinned one at a time. A body at 11% of the range is
    not a doji; a lower wick at 1.9x the body is not a hammer; a bar that opens above the
    previous close has not engulfed it."""
    got = _run("console.log(JSON.stringify(BARS.map((_, i) => X.patternsAt(BARS, i))));")
    assert "doji" not in got[1]
    assert "bua" not in got[3]
    assert "nhanChimTang" not in got[7]


def test_a_flat_bar_is_not_a_pattern():
    """high === low means range 0, which every ratio in the detector divides by."""
    got = _run("console.log(JSON.stringify(X.patternsAt(BARS, 13)));")
    assert got == []


def test_patterns_are_scale_invariant():
    """Every threshold is a ratio, never an absolute price. The whole of stage 02 rests on
    this: the shuffled series re-chains at a different price level, and if a single count
    moved with the level the comparison would be measuring the level, not the pattern."""
    got = _run("""
      const big = BARS.map((b) => ({ t: b.t, o: b.o * 1000, h: b.h * 1000,
                                     l: b.l * 1000, c: b.c * 1000, v: b.v }));
      console.log(JSON.stringify({ small: X.detectPatterns(BARS),
                                   big: X.detectPatterns(big) }));
    """)
    assert got["small"] == got["big"]


def test_detect_patterns_is_stable_on_the_fixture():
    got = _run("console.log(JSON.stringify(X.detectPatterns(BARS)));")
    assert got == {"doji": 1, "bua": 1, "nhanChimTang": 1,
                   "nhanChimGiam": 1, "baConQua": 1}


def test_the_detector_and_the_flags_agree():
    """Stage 00 calls patternsAt, stage 02 calls patternFlags. Two readings of one detector
    that disagreed would mean the honest table grades something the fortune-teller never
    said."""
    got = _run("""
      const flags = X.patternFlags(BARS);
      const direct = BARS.map((_, i) => X.patternsAt(BARS, i));
      console.log(JSON.stringify(JSON.stringify(flags) === JSON.stringify(direct)));
    """)
    assert got is True


# --- the shuffle ---------------------------------------------------------------------

def test_shuffle_is_deterministic_for_one_seed():
    """Same window, same printed numbers on a reload - the same rule the prophecy seeds
    live under."""
    got = _run("""
      const a = X.shuffledBars(BARS, 'seed-a');
      const b = X.shuffledBars(BARS, 'seed-a');
      const c = X.shuffledBars(BARS, 'seed-b');
      console.log(JSON.stringify({ same: JSON.stringify(a) === JSON.stringify(b),
                                   differs: JSON.stringify(a) !== JSON.stringify(c) }));
    """)
    assert got == {"same": True, "differs": True}


def test_shuffle_keeps_every_candle_shape():
    """The null hypothesis is 'order carries no information', so the shuffle must move order
    and nothing else. Every synthetic candle is a real candle, which is what makes the
    comparison unarguable - a normal draw would invite 'your fake data has thin tails'."""
    got = _run("""
      const shape = (bs) => bs.filter((b) => b.h > b.l)
        .map((b) => Math.abs(b.c - b.o) / (b.h - b.l)).sort((x, y) => x - y);
      const real = shape(BARS), fake = shape(X.shuffledBars(BARS, 's'));
      console.log(JSON.stringify({
        n: real.length === fake.length,
        max: Math.max(...real.map((v, i) => Math.abs(v - fake[i]))),
      }));
    """)
    assert got["n"] is True
    assert got["max"] < 1e-9


def test_single_bar_patterns_survive_the_shuffle_exactly():
    """Not 'about the same' - identical. A doji is a property of one candle standing alone,
    so reordering cannot touch it. This is pinned so that nobody later 'fixes' the tautology
    into a claim the data does not support; the page prints it as the point, not the flaw."""
    got = _run("""
      const real = X.detectPatterns(BARS);
      const fake = X.detectPatterns(X.shuffledBars(BARS, 's'));
      console.log(JSON.stringify({ doji: [real.doji, fake.doji],
                                   bua: [real.bua, fake.bua] }));
    """)
    assert got["doji"][0] == got["doji"][1]
    assert got["bua"][0] == got["bua"][1]


def test_compare_to_random_averages_over_every_shuffle():
    got = _run("""
      const cmp = X.compareToRandom(BARS);
      console.log(JSON.stringify({
        shuffles: cmp.shuffles, bars: cmp.bars,
        finite: Object.keys(X.PATTERNS).every((k) => Number.isFinite(cmp.random[k])),
        realMatches: JSON.stringify(cmp.real) === JSON.stringify(X.detectPatterns(BARS)),
      }));
    """)
    assert got == {"shuffles": 20, "bars": len(BARS), "finite": True, "realMatches": True}


# --- the statistic that actually answers the question --------------------------------

def test_forward_returns_refuse_to_speak_for_too_small_a_sample():
    """Five firings is not a p-value. It reports the count and null, not a number dressed up
    as evidence."""
    got = _run("""
      const s = X.forwardReturnStats(BARS, X.patternFlags(BARS));
      console.log(JSON.stringify(s.rows.map((r) => ({ key: r.key, n: r.n, p: r.p }))));
    """)
    for row in got:
        assert row["n"] < 10
        assert row["p"] is None


def test_forward_returns_do_not_throw_without_any_pattern():
    """A series where nothing ever fires still has to render a table."""
    got = _run("""
      const flat = [];
      for (let i = 0; i < 40; i++)
        flat.push({ t: i * 60, o: 100 + i, h: 100 + i + 1, l: 100 + i - 1,
                    c: 100 + i + 0.8, v: 1 });
      const s = X.forwardReturnStats(flat, flat.map(() => []));
      console.log(JSON.stringify({ rows: s.rows.length,
                                   allNull: s.rows.every((r) => r.p === null),
                                   base: Number.isFinite(s.base) }));
    """)
    assert got == {"rows": 5, "allNull": True, "base": True}


def test_forward_returns_report_a_p_value_once_the_sample_is_big_enough():
    """A long series of real-shaped dojis: the statistic must run, and on a series built with
    no relationship between the pattern and what follows it, it must not find one."""
    got = _run("""
      const rnd = window.TienTriVuTruPersonal.seededRandom('fixture');
      const bars = [];
      let px = 100;
      for (let i = 0; i < 600; i++) {
        const o = px, c = o * (1 + (rnd() - 0.5) * 0.004);
        const hi = Math.max(o, c) * 1.002, lo = Math.min(o, c) * 0.998;
        bars.push({ t: i * 60, o, h: hi, l: lo, c, v: 1 });
        px = c;
      }
      const s = X.forwardReturnStats(bars, X.patternFlags(bars));
      const doji = s.rows.find((r) => r.key === 'doji');
      console.log(JSON.stringify({
        n: doji.n, p: doji.p, alpha: s.alpha, fee: s.roundTripFee,
        inRange: doji.p >= 0 && doji.p <= 1,
      }));
    """)
    assert got["n"] >= 10
    assert got["inRange"] is True
    assert got["alpha"] == pytest.approx(0.01)
    assert got["fee"] == pytest.approx(0.002)


def test_the_bonferroni_divisor_is_the_number_of_patterns_actually_tested():
    """Five thresholds swept at once is five chances at a pretty number. The page divides by
    what it tested, and the divisor is read from the detector rather than typed twice."""
    got = _run("""
      console.log(JSON.stringify({ divisor: X.PATTERN_COUNT,
                                   patterns: Object.keys(X.PATTERNS).length }));
    """)
    assert got["divisor"] == got["patterns"]


# --- indicators the page teaches, then dismantles ------------------------------------

def test_rsi_stays_in_range_and_is_null_before_it_is_defined():
    got = _run("""
      const r = X.rsi14(BARS);
      console.log(JSON.stringify({
        early: r.slice(0, 14).every((v) => v === null),
        later: r.slice(14).every((v) => v === null || (v >= 0 && v <= 100)),
        len: r.length,
      }));
    """)
    assert got == {"early": True, "later": True, "len": len(BARS)}


def test_sma_is_null_until_the_window_is_full():
    got = _run("""
      console.log(JSON.stringify({ short: X.sma(BARS, 3, 20),
                                   full: X.sma(BARS, 19, 20) }));
    """)
    assert got["short"] is None
    assert got["full"] == pytest.approx(
        sum(b["c"] for b in BARS) / len(BARS), rel=1e-9
    )


# --- the socket ----------------------------------------------------------------------

def test_backoff_is_monotone_and_capped():
    """Binance drops a connection at about 24 hours, so this path runs in normal operation,
    not only when something is broken."""
    got = _run("""
      const d = [];
      for (let i = 0; i <= 12; i++) d.push(X.backoffDelay(i));
      d.push(X.backoffDelay(99));
      console.log(JSON.stringify(d));
    """)
    assert got[0] == 1000
    assert got == sorted(got)
    assert got[-1] == 30000


# --- the page itself -----------------------------------------------------------------

def test_the_trader_page_loads_the_scripts_it_needs_in_order():
    """trader.js reads the TienTriVuTru* namespaces at load, and builds the chart against
    window.LightweightCharts, so all of them have to be on the page before it."""
    html = (SITE / "trader.html").read_text(encoding="utf-8")
    local = ("dom.js", "thay.js", "warning.js", "theme.js", "personal.js", "trader.js")
    # src="./x", not a bare substring: "theme.js" also appears inside the anti-FOUC
    # localStorage key at the top of the document.
    order = [s for s in local if f'src="./{s}"' in html]
    assert order == list(local)
    assert (html.index('src="./personal.js"')
            < html.index("lightweight-charts@")
            < html.index('src="./trader.js"'))


def test_the_chart_library_is_pinned_and_credited():
    """Apache-2.0's NOTICE asks for the attribution and a link where users can see it, and
    this is the only third-party script on the site - so it is also the only one whose exact
    bytes need pinning."""
    html = (SITE / "trader.html").read_text(encoding="utf-8")
    assert 'integrity="sha384-' in html
    assert 'crossorigin="anonymous"' in html
    assert "lightweight-charts@5.2.1" in html, "an unpinned version invalidates the hash"
    assert "tradingview.com" in html
    assert "Apache-2.0" in html


def test_the_trader_page_declares_its_own_warning_gate():
    """gateCopy() falls back to the lottery gate for an unknown data-page, which would put a
    lottery warning on a page about leverage - and anyone who already dismissed the lottery
    one would never see a warning at all."""
    html = (SITE / "trader.html").read_text(encoding="utf-8")
    js = (SITE / "warning.js").read_text(encoding="utf-8")
    assert 'data-page="trader"' in html
    assert "trader: {" in js
    assert "tientrivutru.ack.trader.v1" in js


def test_every_page_carries_the_same_three_item_nav():
    """One current page per page. Two links both claiming aria-current is the copy-paste
    failure this catches, and a browser sweep of one page never would."""
    for name in ("index.html", "tai-chinh.html", "trader.html"):
        html = (SITE / name).read_text(encoding="utf-8")
        assert html.count('class="slab__to"') == 3, name
        assert html.count('aria-current="page"') == 1, name
        for target in ("./index.html", "./tai-chinh.html", "./trader.html"):
            assert f'class="slab__to" href="{target}"' in html, (name, target)


def test_no_market_data_is_committed():
    """Same rule as the money page: Binance's klines carry no licence that would allow this
    repo to redistribute them, so the browser fetches and the tab forgets."""
    assert not (SITE / "klines.json").exists()
    assert not (ROOT / "data" / "binance.jsonl").exists()


def test_the_page_never_promises_a_direction():
    """CONTEXT.md's banned list, applied to the one page where the temptation is real.

    "cam kết" and "chắc chắn" are allowed exactly once each way round: negated. The money
    page already says "khong tai lieu, khong cam ket" about its sources, and that sentence
    is the opposite of a promise. What is banned is the affirmative, so the test checks the
    negation rather than the word."""
    js = (SITE / "trader.js").read_text(encoding="utf-8")
    html = (SITE / "trader.html").read_text(encoding="utf-8")
    for text, name in ((js, "trader.js"), (html, "trader.html")):
        assert "soi cầu" not in text, name
        assert "số nóng" not in text and "số lạnh" not in text, name
        for banned in ("chắc chắn", "cam kết"):
            for m in re.finditer(re.escape(banned), text):
                before = text[max(0, m.start() - 8):m.start()]
                assert "không " in before, f"{name}: {banned!r} not negated"
