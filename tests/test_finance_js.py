"""The finance page parses live money data in the browser, so the parsers are tested there.

Nothing on that page is committed to the repo - every figure is fetched client-side - which
means there is no Python step to assert against and no bundle to inspect. What can still be
pinned is the part that turns a third-party payload into a number, and that is where the
expensive mistakes live: a gold quote read at the wrong denomination is wrong by a factor
of ten while looking entirely plausible.

Fixtures are real responses, recorded 2026-08-22. Following the convention the rest of the
suite uses, the fetch is never exercised - finance.js splits parse from fetch precisely so
these can run offline with no HTTP mocking library.

Skipped when Node is unavailable, same as test_js_python_parity.py.
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

# --- real payloads, trimmed to the fields the parsers read -------------------------

PNJ = {
    "data": [
        {"masp": "SJC", "tensp": "Vàng miếng SJC 999.9", "giaban": 14760, "giamua": 14460},
        {"masp": "N24K", "tensp": "Nhẫn Trơn PNJ 999.9", "giaban": 14750, "giamua": 14400},
        {"masp": "24K", "tensp": "Vàng nữ trang 999.9", "giaban": 14650, "giamua": 14150},
    ]
}

XAU = {
    "currency": "USD", "name": "Gold", "price": 4604.399902, "symbol": "XAU",
    "updatedAt": "2026-08-22T04:16:40Z",
}

INDICES = {
    "data": [
        {"code": "VNINDEX", "price": 1768.12, "change": 33.88,
         "changePct": 1.9535935049358797, "lastUpdated": "2026-08-21 20:59"},
        {"code": "UPCOM", "price": 127.52, "change": 0.28,
         "changePct": 0.22005658597925182, "lastUpdated": "2026-08-21 20:59"},
        {"code": "HNX", "price": 284.07, "change": 5.52,
         "changePct": 1.9816908992999462, "lastUpdated": "2026-08-21 20:59"},
    ]
}

# Two sessions, on purpose: the parser must keep only the newest one.
FOREIGN = {
    "data": [
        {"code": "FPT", "tradingDate": "2026-08-21", "floor": "HOSE", "netVal": 9.2699085e9},
        {"code": "VNM", "tradingDate": "2026-08-21", "floor": "HOSE", "netVal": 3.4920266e9},
        {"code": "HPG", "tradingDate": "2026-08-21", "floor": "HOSE", "netVal": -2.914128485e10},
        {"code": "FPT", "tradingDate": "2026-08-20", "floor": "HOSE", "netVal": 3.46997e10},
    ]
}

CRYPTO = {
    "bitcoin": {"usd": 78344, "usd_24h_change": 4.7197397290706595,
                "vnd": 2046613132, "vnd_24h_change": 4.91125500906392,
                "last_updated_at": 1787372150},
    "ethereum": {"usd": 2517.92, "usd_24h_change": 7.357888970259897,
                 "vnd": 65776460, "vnd_24h_change": 7.554228993820111,
                 "last_updated_at": 1787372150},
}


def _run(body: str) -> dict:
    """finance.js needs dom.js and personal.js on window; it boots only when a DOM exists."""
    script = f"""
    global.window = {{}};
    global.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
    require({str(SITE / "dom.js")!r});
    require({str(SITE / "personal.js")!r});
    require({str(SITE / "finance.js")!r});
    const F = window.TienTriVuTruFinance;
    const PNJ = {json.dumps(PNJ)};
    const XAU = {json.dumps(XAU)};
    const INDICES = {json.dumps(INDICES)};
    const FOREIGN = {json.dumps(FOREIGN)};
    const CRYPTO = {json.dumps(CRYPTO)};
    {body}
    """
    result = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


def test_finance_js_loads_without_a_dom():
    """It must not try to render when required from Node - that guard is what makes the
    rest of this file possible."""
    got = _run("console.log(JSON.stringify(Object.keys(F).length > 0));")
    assert got is True


# --- gold: the factor-of-ten trap -------------------------------------------------

def test_gold_is_read_per_chi_not_per_luong():
    """PNJ quotes thousands of dong per chỉ (3.75g). Reading 14760 as dong-per-lượng would
    price Vietnamese gold at a tenth of the world price, which arbitrage does not allow.

    Cross-checked at the time of recording: world spot 4604.40 USD/oz at CoinGecko's own
    USD/VND cross is 14,501,916 d/chi, and PNJ's SJC ask sits just above it on the usual
    SJC premium."""
    got = _run("console.log(JSON.stringify(F.parseGold(PNJ)));")
    sjc = next(r for r in got if r["code"] == "SJC")
    assert sjc["sellChi"] == 14_760_000
    assert sjc["buyChi"] == 14_460_000
    assert sjc["sellLuong"] == 147_600_000
    assert sjc["buyLuong"] == 144_600_000


def test_gold_agrees_with_world_spot_within_a_plausible_premium():
    """A regression here means the denomination drifted: the two are independent sources,
    so they can only agree if both are read in the same unit."""
    got = _run(
        "const g = F.parseGold(PNJ), x = F.parseXau(XAU), c = F.parseCrypto(CRYPTO);"
        "const rate = F.impliedUsdVnd(c);"
        "const world = x.usdPerOzt * F.OZT_PER_LUONG * rate;"
        "const sjc = g.find((r) => r.code === 'SJC');"
        "console.log(JSON.stringify({premium: sjc.sellLuong / world - 1}));"
    )
    # SJC bars carry a real premium over world spot, but it is percent, not multiples.
    assert 0 < got["premium"] < 0.25


def test_gold_keeps_only_the_two_quotes_the_page_shows():
    got = _run("console.log(JSON.stringify(F.parseGold(PNJ).map((r) => r.code)));")
    assert got == ["SJC", "N24K"]


def test_gold_throws_when_neither_quote_is_listed():
    got = _run(
        "let msg = null;"
        "try { F.parseGold({data: [{masp: 'X', giaban: 1, giamua: 1}]}); }"
        "catch (e) { msg = e.message; }"
        "console.log(JSON.stringify(msg));"
    )
    assert got and "SJC" in got


def test_gold_throws_on_a_non_numeric_price():
    """Degrading to a dead block beats printing NaN dong per luong."""
    got = _run(
        "let msg = null;"
        "try { F.parseGold({data: [{masp: 'SJC', giaban: 'liên hệ', giamua: 1}]}); }"
        "catch (e) { msg = e.message; }"
        "console.log(JSON.stringify(msg));"
    )
    assert got and "không phải số" in got


# --- indices ----------------------------------------------------------------------

def test_indices_come_back_in_the_order_the_page_prints_them():
    """The payload arrives VNINDEX, UPCOM, HNX; the page reads VNINDEX, HNX, UPCOM."""
    got = _run("console.log(JSON.stringify(F.parseIndices(INDICES).map((r) => r.code)));")
    assert got == ["VNINDEX", "HNX", "UPCOM"]


def test_index_percent_is_a_ratio_not_a_percentage():
    got = _run("console.log(JSON.stringify(F.parseIndices(INDICES)[0]));")
    assert got["price"] == 1768.12
    assert got["change"] == 33.88
    assert abs(got["changePct"] - 0.019535935049358797) < 1e-15
    assert got["lastUpdated"] == "2026-08-21 20:59"


def test_indices_throw_when_the_feed_is_empty():
    got = _run(
        "let msg = null;"
        "try { F.parseIndices({data: []}); } catch (e) { msg = e.message; }"
        "console.log(JSON.stringify(msg));"
    )
    assert got


# --- foreign flows ----------------------------------------------------------------

def test_foreign_keeps_only_the_newest_session():
    """Two dates in one column is the kind of quiet error nobody catches by looking."""
    got = _run("console.log(JSON.stringify(F.parseForeign(FOREIGN)));")
    assert got["tradingDate"] == "2026-08-21"
    assert [r["code"] for r in got["rows"]] == ["FPT", "VNM", "HPG"]


def test_foreign_reads_exponent_notation_as_a_number():
    """VNDIRECT serialises net value as 9.2699085E9. Read as text it sorts as a string."""
    got = _run("console.log(JSON.stringify(F.parseForeign(FOREIGN).rows));")
    assert got[0]["netVal"] == 9_269_908_500.0
    assert got[-1]["netVal"] == -29_141_284_850.0
    assert all(isinstance(r["netVal"], float | int) for r in got)


def test_foreign_sorts_buyers_above_sellers():
    got = _run(
        "console.log(JSON.stringify(F.parseForeign(FOREIGN).rows.map((r) => r.netVal)));"
    )
    assert got == sorted(got, reverse=True)


# --- crypto -----------------------------------------------------------------------

def test_crypto_carries_both_currencies_and_the_daily_move():
    got = _run("console.log(JSON.stringify(F.parseCrypto(CRYPTO)));")
    assert [c["ticker"] for c in got] == ["BTC", "ETH"]
    assert got[0]["usd"] == 78344
    assert got[0]["vnd"] == 2046613132
    assert abs(got[0]["change24h"] - 0.047197397290706595) < 1e-15


def test_crypto_throws_on_a_payload_with_no_coins():
    got = _run(
        "let msg = null;"
        "try { F.parseCrypto({garbage: 1}); } catch (e) { msg = e.message; }"
        "console.log(JSON.stringify(msg));"
    )
    assert got and "CoinGecko" in got


def test_implied_rate_is_the_cross_of_the_two_quotes():
    """Recovered from one provider quoting one coin twice. Not a bank rate, and the page
    says so - it is used only to check gold against world spot."""
    got = _run("console.log(JSON.stringify(F.impliedUsdVnd(F.parseCrypto(CRYPTO))));")
    assert abs(got - 2046613132 / 78344) < 1e-6
    assert 20_000 < got < 35_000


# --- the cursed layer -------------------------------------------------------------

def _settled(*ok_keys: str) -> str:
    """Build the shape render() passes around: every source present, some of them dead."""
    parts = []
    for key, payload in (
        ("gold", "F.parseGold(PNJ)"),
        ("xau", "F.parseXau(XAU)"),
        ("indices", "F.parseIndices(INDICES)"),
        ("foreign", "F.parseForeign(FOREIGN)"),
        ("crypto", "F.parseCrypto(CRYPTO)"),
    ):
        if key in ok_keys:
            parts.append(f"{key}: {{ok: true, value: {payload}}}")
        else:
            parts.append(f"{key}: {{ok: false, error: 'chết'}}")
    return "{" + ", ".join(parts) + "}"


ALL = ("gold", "xau", "indices", "foreign", "crypto")


def test_a_silent_source_is_a_dash_not_a_gap():
    """vibes.py renders a missing signal as '-' so the oracle still runs and the absence
    is visible. The browser side has to mean the same thing."""
    got = _run(
        f"const d = {_settled('crypto')};"
        "console.log(JSON.stringify(F.canonical(d)));"
    )
    assert got.startswith("gold=-|xau=-|idx=-|fx=-|coin=")
    assert got.count("-") >= 4


def test_the_sermon_is_stable_for_the_same_market():
    got = _run(
        f"const d = {_settled(*ALL)};"
        "console.log(JSON.stringify([F.marketRoot(d), F.marketRoot(d)]));"
    )
    assert got[0] == got[1]


def test_the_sermon_moves_when_the_market_does():
    """Stability must not come from ignoring the input."""
    got = _run(
        f"const a = {_settled(*ALL)};"
        f"const b = {_settled(*ALL)};"
        "b.indices.value[0].price = 999.99;"
        "console.log(JSON.stringify([F.canonical(a) === F.canonical(b)]));"
    )
    assert got == [False]


def test_market_root_is_a_single_digit():
    got = _run(
        f"const d = {_settled(*ALL)};"
        "console.log(JSON.stringify(F.marketRoot(d)));"
    )
    assert 1 <= got <= 9


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 9), (9, 9), (10, 1), (18, 9), (1768, 4), (-1768, 4), (147600000, 9)],
)
def test_digit_root(value: int, expected: int):
    got = _run(f"console.log(JSON.stringify(F.digitRoot({value})));")
    assert got == expected


def test_silent_count_matches_the_number_of_dead_sources():
    got = _run(
        f"const none = {_settled()};"
        f"const some = {_settled('crypto', 'gold')};"
        f"const all = {_settled(*ALL)};"
        "console.log(JSON.stringify(["
        "F.silentCount(none), F.silentCount(some), F.silentCount(all)]));"
    )
    assert got == [5, 3, 0]


# --- which session the numbers belong to -------------------------------------------

def test_a_stale_session_is_labelled_as_the_latest_one_not_as_today():
    """The weekend case, and the only one reachable when this suite runs on a Saturday."""
    got = _run(
        "console.log(JSON.stringify(F.sessionLabel('2026-08-21 20:59', '2026-08-22')));"
    )
    assert "phiên gần nhất" in got
    assert "2026-08-21 20:59" in got


def test_a_same_day_session_is_labelled_as_an_update_time():
    """The trading-day branch. It is passed `today` rather than reading the clock precisely
    so this can be exercised on any day of the week."""
    got = _run(
        "console.log(JSON.stringify(F.sessionLabel('2026-08-21 15:08', '2026-08-21')));"
    )
    assert "Cập nhật lúc" in got
    assert "phiên gần nhất" not in got


def test_no_timestamp_means_no_claim_about_when():
    got = _run("console.log(JSON.stringify(F.sessionLabel(null, '2026-08-21')));")
    assert got is None


def test_today_is_computed_in_vietnam_not_utc():
    """VNDIRECT writes dates in +07. Comparing against a UTC date would call a fresh
    session stale for the first seven hours of every Vietnamese day."""
    got = _run(
        "const t = F.todayHcm();"
        "const utc = new Date().toISOString().slice(0, 10);"
        "const vn = new Intl.DateTimeFormat('en-CA', "
        "  {timeZone: 'Asia/Ho_Chi_Minh'}).format(new Date());"
        "console.log(JSON.stringify({t, matchesVn: t === vn, utc}));"
    )
    assert got["matchesVn"], f"todayHcm() returned {got['t']}, Vietnam is on a different date"
    assert len(got["t"]) == 10 and got["t"][4] == "-", "must match the API's YYYY-MM-DD"


# --- the page itself ---------------------------------------------------------------

def test_the_finance_page_loads_the_scripts_it_needs_in_order():
    """finance.js destructures window.TienTriVuTruDom and reads TienTriVuTruPersonal.seededRandom at
    load, so both have to be on the page before it."""
    html = (SITE / "tai-chinh.html").read_text(encoding="utf-8")
    order = [s for s in ("dom.js", "thay.js", "theme.js", "personal.js", "finance.js")
             if f'src="./{s}"' in html]
    assert order == ["dom.js", "thay.js", "theme.js", "personal.js", "finance.js"]


def test_the_finance_page_credits_coingecko_next_to_the_data():
    """CoinGecko's attribution guide asks for the credit beside the figures, and it applies
    to the keyless API too. It is rendered with the crypto block, not in the footer."""
    js = (SITE / "finance.js").read_text(encoding="utf-8")
    assert "Powered by " in js and "coingecko.com" in js
    footer = (SITE / "tai-chinh.html").read_text(encoding="utf-8")
    assert "CoinGecko" in footer


def test_both_pages_declare_which_warning_they_carry():
    """The gate copy and its acknowledgement key are chosen from body[data-page]; an
    untagged page would silently show the lottery warning on the money page."""
    assert 'data-page="xoso"' in (SITE / "index.html").read_text(encoding="utf-8")
    assert 'data-page="taichinh"' in (SITE / "tai-chinh.html").read_text(encoding="utf-8")


def test_no_finance_data_is_committed():
    """The whole architecture rests on this: the page fetches in the browser precisely
    because these sources carry no licence that would allow redistributing them."""
    root = SITE.parent
    assert not (SITE / "finance.json").exists()
    assert not (root / "data" / "finance.jsonl").exists()
