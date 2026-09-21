"""Gold and crypto quotes.

The contract that matters here is the *unit*. PNJ publishes thousands of dong per chỉ,
Vietnamese gold is talked about per lượng, and a lượng is ten chỉ - so the whole thing
sits one factor of ten away from a number that is wrong and still looks believable. The
tests below pin that factor from both ends: against the published dong figure and against
world spot converted independently.
"""

from __future__ import annotations

import pytest
import requests

from tientrivutru.sources import markets

# The real payload, trimmed. `giaban`/`giamua` are thousands of dong per chỉ - webgia.com
# publishes the same board as "Đơn vị: đồng / chỉ" with 14.760.000 / 15.060.000.
PNJ_PAYLOAD = {
    "data": [
        {"masp": "SJC", "tensp": "Vàng miếng SJC 999.9", "giaban": 15060, "giamua": 14760},
        {"masp": "N24K", "tensp": "Nhẫn Trơn PNJ 999.9", "giaban": 15050, "giamua": 14750},
        {"masp": "24K", "tensp": "Vàng nữ trang 999.9", "giaban": 14950, "giamua": 14450},
    ],
    "chinhanh": "hochiminh",
    "updateDate": "25/08/2026 08:37:59",
}

COINGECKO_PAYLOAD = {
    "bitcoin": {
        "usd": 80759,
        "vnd": 2111077904,
        "usd_24h_change": 4.630248863351408,
    },
    "ethereum": {"usd": 2509.54, "vnd": 65600227, "usd_24h_change": 3.0308454876828157},
    "solana": {"usd": 101.39, "vnd": 2650315, "usd_24h_change": 7.986830613264978},
}

GOLD_API_PAYLOAD = {
    "currency": "USD",
    "name": "Gold",
    "price": 4636.0,
    "symbol": "XAU",
    "updatedAt": "2026-08-25T03:18:47Z",
}


class FakeResponse:
    def __init__(self, payload, *, status_ok: bool = True):
        self._payload = payload
        self._ok = status_ok

    def raise_for_status(self):
        if not self._ok:
            raise requests.HTTPError("403 Client Error: Forbidden")

    def json(self):
        return self._payload


@pytest.fixture
def no_network(monkeypatch):
    """Any un-stubbed request is a bug in the test, not a slow test."""

    def boom(*args, **kwargs):
        raise AssertionError("unstubbed request")

    monkeypatch.setattr(requests, "get", boom)


def stub(monkeypatch, payload, *, status_ok: bool = True):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(payload, status_ok=status_ok)
    )


# -------------------------------------------------------------------------------- units


def test_a_luong_is_ten_chi():
    assert markets.CHI_PER_LUONG == 10


def test_pnj_figures_are_thousands_of_dong_per_chi(monkeypatch):
    """The published board reads 15.060.000 đồng/chỉ for SJC. Anything else is the ×10 bug."""
    stub(monkeypatch, PNJ_PAYLOAD)
    board = markets.fetch_gold_board()
    assert board is not None

    sjc = board.by_code("SJC")
    assert sjc is not None
    assert sjc.sell_vnd_per_chi == 15_060_000
    assert sjc.buy_vnd_per_chi == 14_760_000


def test_per_luong_is_ten_times_per_chi(monkeypatch):
    stub(monkeypatch, PNJ_PAYLOAD)
    sjc = markets.fetch_gold_board().by_code("SJC")
    assert sjc.sell_vnd_per_luong == 150_600_000
    assert sjc.buy_vnd_per_luong == 147_600_000


def test_world_spot_converts_into_the_same_order_of_magnitude(monkeypatch):
    """The independent end of the pin. World gold at $4636/oz is about 146 million dong
    per lượng, so a domestic quote belongs near 150 million - never near 15 million."""
    stub(monkeypatch, GOLD_API_PAYLOAD)
    world = markets.fetch_world_gold_usd_per_oz()
    assert world == pytest.approx(4636.0)

    per_luong = markets.world_gold_vnd_per_luong(world, usd_vnd=26_136)
    assert 140_000_000 < per_luong < 155_000_000

    # And the domestic board must sit above it, not an order of magnitude below.
    stub(monkeypatch, PNJ_PAYLOAD)
    sjc = markets.fetch_gold_board().by_code("SJC")
    assert 1.0 < sjc.sell_vnd_per_luong / per_luong < 1.3


def test_grams_per_luong_and_troy_ounce_are_the_real_constants():
    # Exact, not approx: both are float literals in the module, and a lượng being 37.5g
    # is a definition rather than a measurement.
    assert markets.GRAMS_PER_LUONG == 37.5
    assert markets.GRAMS_PER_TROY_OUNCE == 31.1034768


def test_premium_is_domestic_minus_world(monkeypatch):
    stub(monkeypatch, PNJ_PAYLOAD)
    sjc = markets.fetch_gold_board().by_code("SJC")
    world = markets.world_gold_vnd_per_luong(4636.0, usd_vnd=26_136)

    premium = sjc.sell_vnd_per_luong - world
    assert 0 < premium < 20_000_000
    assert premium / world < 0.20


# --------------------------------------------------------------------------------- gold


def test_gold_board_keeps_the_reported_moment_and_branch(monkeypatch):
    """A price without the moment it was read is a claim the source cannot support -
    the same rule `vietlott_prizes` already enforces for the jackpot."""
    stub(monkeypatch, PNJ_PAYLOAD)
    board = markets.fetch_gold_board()
    assert board.updated_at == "25/08/2026 08:37:59"
    assert board.branch == "hochiminh"


def test_gold_board_preserves_order_and_labels(monkeypatch):
    stub(monkeypatch, PNJ_PAYLOAD)
    board = markets.fetch_gold_board()
    assert [q.code for q in board.quotes] == ["SJC", "N24K", "24K"]
    assert board.quotes[0].label == "Vàng miếng SJC 999.9"


def test_spread_is_what_a_buyer_loses_instantly(monkeypatch):
    stub(monkeypatch, PNJ_PAYLOAD)
    sjc = markets.fetch_gold_board().by_code("SJC")
    assert sjc.spread_vnd_per_luong == 3_000_000
    assert sjc.spread_pct == pytest.approx(3_000_000 / 150_600_000 * 100, abs=1e-9)


def test_by_code_is_none_for_a_product_the_board_does_not_carry(monkeypatch):
    stub(monkeypatch, PNJ_PAYLOAD)
    assert markets.fetch_gold_board().by_code("KHONG-CO") is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{"masp": "SJC"}]},
        {"data": [{"masp": "SJC", "giaban": "không phải số", "giamua": 1}]},
        {"data": "not a list"},
    ],
)
def test_unusable_gold_payloads_degrade_to_none(monkeypatch, payload):
    """A layout change upstream must cost one card, never an exception."""
    stub(monkeypatch, payload)
    assert markets.fetch_gold_board() is None


def test_gold_skips_a_broken_row_but_keeps_the_good_ones(monkeypatch):
    stub(
        monkeypatch,
        {
            "data": [
                {"masp": "SJC", "tensp": "SJC", "giaban": 15060, "giamua": 14760},
                {"masp": "BAD", "tensp": "BAD", "giaban": None, "giamua": 1},
            ]
        },
    )
    board = markets.fetch_gold_board()
    assert [q.code for q in board.quotes] == ["SJC"]


def test_a_403_from_the_gold_source_is_not_an_exception(monkeypatch):
    """Exactly what vietlott.vn does to a GitHub runner: 200 from a laptop, 403 from CI."""
    stub(monkeypatch, PNJ_PAYLOAD, status_ok=False)
    assert markets.fetch_gold_board() is None


def test_a_dead_network_is_not_an_exception(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("x"))
    )
    assert markets.fetch_gold_board() is None
    assert markets.fetch_world_gold_usd_per_oz() is None
    assert markets.fetch_coins() == ()


# ------------------------------------------------------------------------------- crypto


def test_coins_carry_usd_vnd_and_the_daily_move(monkeypatch):
    stub(monkeypatch, COINGECKO_PAYLOAD)
    coins = markets.fetch_coins()

    assert [c.symbol for c in coins] == ["BTC", "ETH", "SOL"]
    btc = coins[0]
    assert btc.usd == pytest.approx(80759)
    assert btc.vnd == pytest.approx(2_111_077_904)
    assert btc.change_24h_pct == pytest.approx(4.630248863351408)


def test_implied_exchange_rate_comes_from_the_same_response(monkeypatch):
    """Deriving USD/VND from the pair CoinGecko already returned keeps the premium
    honest: one source, one moment, rather than two rates from two times."""
    stub(monkeypatch, COINGECKO_PAYLOAD)
    coins = markets.fetch_coins()
    rate = markets.implied_usd_vnd(coins)
    assert rate == pytest.approx(2_111_077_904 / 80759, rel=1e-9)
    assert 20_000 < rate < 35_000


def test_implied_exchange_rate_is_none_without_quotes():
    assert markets.implied_usd_vnd(()) is None


def test_coins_ignore_an_entry_missing_a_price(monkeypatch):
    stub(monkeypatch, {"bitcoin": {"usd": 80759, "vnd": 2_111_077_904}, "ethereum": {}})
    coins = markets.fetch_coins()
    assert [c.symbol for c in coins] == ["BTC"]
    assert coins[0].change_24h_pct is None


@pytest.mark.parametrize("payload", [{}, [], "nope", {"bitcoin": "nope"}])
def test_unusable_crypto_payloads_degrade_to_empty(monkeypatch, payload):
    stub(monkeypatch, payload)
    assert markets.fetch_coins() == ()


def test_world_gold_rejects_a_nonsense_price(monkeypatch):
    stub(monkeypatch, {"symbol": "XAU", "price": 0})
    assert markets.fetch_world_gold_usd_per_oz() is None


def test_world_gold_requires_the_symbol_it_asked_for(monkeypatch):
    """A silver price rendered as gold would be a plausible wrong number - the worst kind."""
    stub(monkeypatch, {"symbol": "XAG", "price": 67.96})
    assert markets.fetch_world_gold_usd_per_oz() is None


def test_nothing_here_touches_the_network_unless_asked(no_network):
    """`no_network` makes any real request explode; importing and doing arithmetic must not."""
    assert markets.world_gold_vnd_per_luong(4636.0, usd_vnd=26_136) > 0
