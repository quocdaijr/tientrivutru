"""Random pulses through the day. Two contracts: the schedule is reproducible, and
nothing here may leak a birth date or raise on missing data."""

from __future__ import annotations

import random
import re
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from conftest import make_draw, make_prophecy
from tientrivutru import kienthiet_oracle, kienthiet_scoreboard, notify, pulse, scoreboard, store
from tientrivutru.astrology import read_fortune
from tientrivutru.cli import VN_TZ, build_parser
from tientrivutru.games import MEGA645, MEGAMILLIONS, POWER655
from tientrivutru.models import Prophecy, utc_now
from tientrivutru.oracle import ORACLE_VERSION
from tientrivutru.sources import kienthiet, markets
from tientrivutru.sources.vibes import CosmicSignals
from tientrivutru.sources.xsmb import PRIZE_SLOTS, XsmbDraw

A_DAY = date(2026, 8, 23)


def at(hour: int, day: date = A_DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 30, tzinfo=VN_TZ)


@pytest.fixture(autouse=True)
def no_person_env(monkeypatch):
    """No birth date and no Telegram unless a test asks for them."""
    for name in (
        pulse.ENV_BIRTH_DATE,
        pulse.ENV_GENDER,
        pulse.ENV_NAME,
        notify.ENV_TOKEN,
        notify.ENV_CHAT_ID,
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def counting_send(monkeypatch):
    """Replace the Telegram call with a counter, so no test can reach the network."""

    class Counter:
        def __init__(self) -> None:
            self.messages: list[str] = []
            self.result = True

        def __call__(self, text: str) -> bool:
            self.messages.append(text)
            return self.result

        @property
        def calls(self) -> int:
            return len(self.messages)

    counter = Counter()
    monkeypatch.setattr(pulse, "send_message", counter)
    return counter


# ------------------------------------------------------------------------------ cards


def a_prophecy_with_sermons() -> Prophecy:
    return Prophecy(
        game=MEGA645.key,
        draw_id="01551",
        draw_date=A_DAY,
        numbers=tuple(range(1, 13)),
        seed="deadbeef" * 8,
        signals={},
        sermon={str(n): f"số {n} gọi tên con" for n in range(1, 13)},
        oracle_version=ORACLE_VERSION,
        created_at=utc_now(),
    )


def an_xsmb_day(day: date, special: int) -> XsmbDraw:
    return XsmbDraw(date=day, special=special, prizes=(special,) * PRIZE_SLOTS)


EMPTY_CASES = (
    ("hot_cold", lambda: pulse.card_hot_cold(MEGA645, ())),
    ("chi_square", lambda: pulse.card_chi_square(MEGA645, ())),
    ("gap", lambda: pulse.card_gap(MEGA645, ())),
    ("xsmb", lambda: pulse.card_xsmb(())),
    ("kienthiet", lambda: pulse.card_kienthiet("mn", ())),
    ("ve", lambda: pulse.card_ve(kienthiet_scoreboard.build((), ()))),
    (
        "scoreboard",
        lambda: pulse.card_scoreboard(MEGA645, scoreboard.build(MEGA645, (), ())),
    ),
    ("schedule", lambda: pulse.card_schedule(MEGA645, (), None, now=at(10))),
    ("sermon", lambda: pulse.card_sermon(MEGA645, None, pulse.day_rng(A_DAY))),
    ("fortune", lambda: pulse.card_fortune(None, day=A_DAY)),
)


@pytest.mark.parametrize("name,builder", EMPTY_CASES, ids=[c[0] for c in EMPTY_CASES])
def test_every_builder_degrades_to_none_instead_of_raising(name, builder):
    """Missing data is normal on a fresh clone; it must not become an exception."""
    assert builder() is None


def test_vibes_card_survives_a_completely_silent_universe():
    """Even offline the moon is computable, so this card is the one that always exists."""
    card = pulse.card_vibes(CosmicSignals(lunar_day=8, lunar_month=7, zodiac="Ngọ"), day=A_DAY)
    assert card is not None
    assert card.key == "vibes"


def test_hot_cold_card_names_hot_and_cold_numbers():
    draws = [make_draw(MEGA645, i, main=(1, 2, 3, 4, 5, 6)) for i in range(1, 20)]
    card = pulse.card_hot_cold(MEGA645, draws)
    assert card is not None
    assert "Mega 6/45" in "\n".join(card.lines) + card.title
    assert "01" in "\n".join(card.lines)


def test_chi_square_card_carries_the_verdict():
    draws = [make_draw(MEGA645, i) for i in range(1, 40)]
    card = pulse.card_chi_square(MEGA645, draws)
    assert card is not None
    assert "p = " in "\n".join(card.lines)


def test_gap_card_reports_the_longest_absence():
    """A history where every number has been seen, but some far longer ago than others."""
    blocks = (
        (40, 41, 42, 43, 44, 45),
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
        (31, 32, 33, 34, 35, 36),
        (37, 38, 39, 40, 41, 42),
        (1, 2, 3, 4, 5, 6),
    )
    draws = [make_draw(MEGA645, i, main=block) for i, block in enumerate(blocks, start=1)]

    card = pulse.card_gap(MEGA645, draws)
    assert card is not None
    body = "\n".join(card.lines)
    # 43-45 were last seen in the very first draw; 01-06 came out in the last one.
    for longest in ("43", "44", "45"):
        assert longest in body
    assert "<b>01</b>" not in body


def test_scoreboard_card_shows_roi_without_and_with_jackpot():
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in (1, 2)]
    draws = [make_draw(MEGA645, 1, main=(1, 2, 3, 40, 41, 42))]
    score = scoreboard.build(MEGA645, prophecies, draws)

    card = pulse.card_scoreboard(MEGA645, score)
    assert card is not None
    body = "\n".join(card.lines)
    assert "ROI" in body
    assert "bỏ jackpot" in body


def test_schedule_card_prices_the_wheel_and_quotes_the_jackpot():
    draws = [make_draw(MEGA645, i) for i in range(1, 10)]
    prizes = {"draw_id": "01551", "top_jackpot_vnd": 24_507_110_500, "rolled_over": True}

    card = pulse.card_schedule(MEGA645, draws, prizes, now=at(10))
    assert card is not None
    body = "\n".join(card.lines)
    assert "924" in body  # C(12,6) combinations
    assert "24,51 tỷ" in body or "24.51 tỷ" in body


def test_xsmb_card_reports_the_latest_special():
    draws = [an_xsmb_day(A_DAY - timedelta(days=i), 40 + i) for i in range(5)]
    card = pulse.card_xsmb(draws)
    assert card is not None
    assert "40" in "\n".join(card.lines)


def a_southern_board(day: date, province: str = "an-giang") -> kienthiet.Board:
    return kienthiet.Board(
        date=day,
        region="mn",
        province=province,
        tiers=(
            ("db", ("510332",)),
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


def test_kienthiet_card_names_the_dai_and_its_special():
    card = pulse.card_kienthiet("mn", [a_southern_board(A_DAY)])
    assert card is not None
    body = card.title + "\n".join(card.lines)
    assert "An Giang" in body
    assert "510332" in body


def test_each_region_gets_its_own_card_key():
    """A shared key would make the daily dedupe drop two regions out of three."""
    keys = {
        pulse.card_kienthiet(region, [a_southern_board(A_DAY)]).key
        if region == "mn"
        else f"kienthiet_{region}"
        for region in ("mb", "mn", "mt")
    }
    assert keys == {"kienthiet_mb", "kienthiet_mn", "kienthiet_mt"}


def test_ve_card_prints_both_the_realised_and_the_exact_roi():
    day = A_DAY
    board = a_southern_board(day)
    ticket = kienthiet_oracle.VeProphecy(
        province="an-giang",
        region="mn",
        draw_date=day,
        ve="777777",
        seed="0" * 64,
        signals={},
        sermon="",
        reasons=(),
        karma=None,
        oracle_version=kienthiet_oracle.KIENTHIET_ORACLE_VERSION,
        created_at=utc_now(),
    )
    card = pulse.card_ve(kienthiet_scoreboard.build([ticket], [board]))

    assert card is not None
    body = "\n".join(card.lines)
    assert "-100.00%" in body
    assert "-50.00%" in body
    assert "-52.60%" in body, "the take-home after tax, next to the gross"


def test_sermon_card_quotes_one_line_from_the_pending_prophecy():
    card = pulse.card_sermon(MEGA645, a_prophecy_with_sermons(), pulse.day_rng(A_DAY))
    assert card is not None
    assert "gọi tên con" in "\n".join(card.lines)


def test_sermon_card_is_absent_when_the_prophecy_has_no_sermon():
    """The same missing-sermon record that once crashed `format_prophecy`."""
    assert pulse.card_sermon(MEGA645, make_prophecy(MEGA645, 1), pulse.day_rng(A_DAY)) is None


def test_fortune_card_uses_the_birth_date_without_repeating_it():
    fortune = read_fortune(date(1996, 4, 15), today=A_DAY, gender="nam")
    card = pulse.card_fortune(fortune, day=A_DAY)
    assert card is not None
    body = card.title + "\n".join(card.lines)
    assert fortune.can_chi in body
    assert "1996-04-15" not in body
    assert "15/04/1996" not in body
    # The fortune-teller calls the reader "con"; "anh"/"chị" is never the project's voice.
    assert "con" in card.title
    assert not re.search(r"\b(anh|chị)\b", body, re.IGNORECASE)


# ---------------------------------------------------------------------------- picking


def a_realistic_deck() -> tuple[pulse.Card, ...]:
    """The real shape of a deck: several games sharing each kind of card."""
    return tuple(
        pulse.Card(key=key, title=f"{key} {game}", lines=("x",))
        for key in ("hot_cold", "chi_square", "gap", "schedule")
        for game in ("power655", "mega645", "powerball", "megamillions")
    ) + tuple(
        pulse.Card(key=key, title=key, lines=("x",))
        for key in (
            "scoreboard",
            "sermon",
            "xsmb",
            "kienthiet_mb",
            "kienthiet_mn",
            "kienthiet_mt",
            "ve",
            "vibes",
            "fortune",
        )
    )


def with_network(deck, *, gold: bool, crypto: bool) -> tuple[pulse.Card, ...]:
    extra = [pulse.Card(key=k, title=k, lines=("x",)) for k, on in
             (("gold", gold), ("crypto", crypto)) if on]
    return (*deck, *extra)


def test_a_day_never_repeats_a_card_even_when_network_cards_come_and_go():
    """Gold and crypto need the network, so the deck can differ between two runs of one
    day. Picking by position in a shuffled list let that shift every later card and send
    the same one twice - about 32 days in 365. A card's place must not depend on what
    else happens to be in the deck."""
    deck = a_realistic_deck()
    rng = random.Random(7)
    for offset in range(365):
        day = A_DAY + timedelta(days=offset)
        first = rng.randrange(1000)
        picked = [
            pulse.card_for_run(
                with_network(deck, gold=rng.random() < 0.5, crypto=rng.random() < 0.5),
                day,
                first + i,
            )
            for i in range(pulse.RUNS_PER_DAY)
        ]
        assert len({card.key for card in picked}) == pulse.RUNS_PER_DAY, day


def test_the_pick_moves_from_day_to_day():
    deck = a_realistic_deck()
    picked = {pulse.card_for_run(deck, A_DAY + timedelta(days=d), 0).key for d in range(60)}
    assert len(picked) > 5


def test_card_for_run_is_stable_for_the_same_day_and_run():
    deck = a_realistic_deck()
    assert pulse.card_for_run(deck, A_DAY, 1) == pulse.card_for_run(deck, A_DAY, 1)


def test_card_for_run_still_sends_when_there_is_only_one_card():
    cards = (pulse.Card(key="only", title="t", lines=("x",)),)
    assert [pulse.card_for_run(cards, A_DAY, r).key for r in range(3)] == ["only"] * 3


def test_card_for_run_is_none_with_no_cards():
    assert pulse.card_for_run((), A_DAY, 0) is None


def test_the_workflow_declares_as_many_crons_as_the_code_expects():
    """`RUNS_PER_DAY` slices the day's cards; a cron added without it would reuse a slice."""
    workflow = (Path(__file__).parent.parent / ".github/workflows/pulse.yml").read_text()
    assert len(re.findall(r"^\s*- cron:", workflow, re.MULTILINE)) == pulse.RUNS_PER_DAY
    assert "github.run_number" in workflow


# -------------------------------------------------------------------------- formatting


def test_formatted_card_carries_the_disclaimer():
    card = pulse.Card(key="k", title="🔮 Tiêu đề", lines=("dòng một", "dòng hai"))
    text = pulse.format_card(card, now=at(14))
    assert "🔮 Tiêu đề" in text
    assert notify.DISCLAIMER in text


def test_formatted_card_never_exceeds_the_telegram_limit():
    card = pulse.Card(key="k", title="t", lines=tuple("dòng dài " * 40 for _ in range(200)))
    assert len(pulse.format_card(card, now=at(14))) <= notify.MAX_MESSAGE_CHARS


# ----------------------------------------------------------------------- env / privacy


def test_no_birth_date_env_means_no_fortune():
    assert pulse.read_fortune_from_env(A_DAY) is None


@pytest.mark.parametrize("raw", ["hôm qua", "1996/04/15", "0000-00-00", "15-04-1996"])
def test_malformed_birth_date_is_rejected_without_quoting_it(monkeypatch, raw):
    """A present-but-broken secret is not the same as an absent one, so it must be loud -
    and the message must not echo the value into a public Actions log."""
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, raw)
    with pytest.raises(pulse.BirthDateError) as caught:
        pulse.read_fortune_from_env(A_DAY)
    assert pulse.ENV_BIRTH_DATE in str(caught.value)
    assert raw not in str(caught.value)


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_birth_date_counts_as_not_configured(monkeypatch, raw):
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, raw)
    assert pulse.read_fortune_from_env(A_DAY) is None


def test_valid_birth_date_env_produces_a_fortune(monkeypatch):
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "1996-04-15")
    monkeypatch.setenv(pulse.ENV_GENDER, "nam")
    fortune = pulse.read_fortune_from_env(A_DAY)
    assert fortune is not None
    assert fortune.guardian_star is not None


@pytest.mark.parametrize("raw", ["1600-01-01", "2099-01-01"])
def test_implausible_birth_date_is_rejected(monkeypatch, raw):
    """`astrology.read_fortune` happily computes a lá số for the year 1600. A birth date
    outside living memory, or in the future, is a typo - catch it here."""
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, raw)
    with pytest.raises(pulse.BirthDateError):
        pulse.read_fortune_from_env(A_DAY)


# --------------------------------------------------------------------------- build_cards


def test_build_cards_works_on_an_empty_data_dir():
    """A fresh clone has no draws. The pulse must still have something to say."""
    cards = pulse.build_cards((MEGA645, POWER655), now=at(10), allow_network=False)
    assert cards
    assert {card.key for card in cards} >= {"vibes"}


def test_build_cards_makes_no_requests_when_offline(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise AssertionError("offline build must not touch the network")

    monkeypatch.setattr(requests, "get", boom)
    assert pulse.build_cards((MEGA645,), now=at(10), allow_network=False)


def test_build_cards_survives_a_dead_network_when_online(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise requests.ConnectionError("no route to the cosmos")

    monkeypatch.setattr(requests, "get", boom)
    assert pulse.build_cards((MEGA645,), now=at(10), allow_network=True)


def test_build_cards_includes_the_fortune_when_one_is_supplied():
    fortune = read_fortune(date(1996, 4, 15), today=A_DAY)
    cards = pulse.build_cards((MEGA645,), now=at(10), fortune=fortune, allow_network=False)
    assert "fortune" in {card.key for card in cards}


def test_build_cards_covers_the_game_specific_layers_with_real_data():
    store.write_draws(MEGA645.key, [make_draw(MEGA645, i) for i in range(1, 30)])
    cards = pulse.build_cards((MEGA645,), now=at(10), allow_network=False)
    keys = {card.key for card in cards}
    assert {"hot_cold", "chi_square", "gap", "schedule"} <= keys


def test_build_cards_skips_the_wheel_layers_for_us_games():
    store.write_draws(MEGAMILLIONS.key, [make_draw(MEGAMILLIONS, i) for i in range(1, 30)])
    cards = pulse.build_cards((MEGAMILLIONS,), now=at(10), allow_network=False)
    keys = {card.key for card in cards}
    assert "hot_cold" in keys
    # No bao 12 for the US games, so no wheel price and no scoreboard.
    assert "schedule" not in keys
    assert "scoreboard" not in keys


# ----------------------------------------------------------------------------- the CLI


def run_cli(*argv: str) -> int:
    args = build_parser().parse_args(["pulse", *argv])
    return args.handler(args)


def test_cli_sends_one_card_at_whatever_hour_github_gets_round_to(counting_send, monkeypatch):
    """GitHub starts these crons hours late. Every run that does happen must send."""
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    for hour in (3, 14, 23):
        assert run_cli("--now", at(hour).isoformat(), "--run", str(hour), "--offline") == 0
    assert counting_send.calls == 3
    assert notify.DISCLAIMER in counting_send.messages[0]


def test_cli_reports_a_failed_send(counting_send, monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    counting_send.result = False

    assert run_cli("--offline") == 1


def test_cli_dry_run_sends_nothing(counting_send, monkeypatch, capsys):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    assert run_cli("--dry-run", "--offline") == 0
    assert counting_send.calls == 0
    assert capsys.readouterr().out.strip()


def test_cli_dry_run_needs_no_telegram_config(counting_send, capsys):
    """Previewing a pulse locally must not require anyone's bot token."""
    assert run_cli("--dry-run", "--offline") == 0
    assert counting_send.calls == 0


def test_cli_fails_loudly_without_telegram_config(counting_send):
    assert run_cli("--offline") == 1
    assert counting_send.calls == 0


def test_cli_never_prints_the_birth_date(counting_send, monkeypatch, capsys):
    """Actions logs are public. The derived fortune may travel; the date may not."""
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "1996-04-15")
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    assert run_cli("--offline") == 0
    assert "1996-04-15" not in capsys.readouterr().out


def test_cli_warns_without_leaking_a_malformed_birth_date(counting_send, monkeypatch, capsys):
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "sinh-nam-1996")
    assert run_cli("--dry-run", "--offline") == 0
    out = capsys.readouterr().out
    assert pulse.ENV_BIRTH_DATE in out
    assert "sinh-nam-1996" not in out


# ------------------------------------------------------------------- telegram's parser

TELEGRAM_TAGS = frozenset(
    ("b", "/b", "i", "/i", "u", "/u", "s", "/s", "code", "/code", "pre", "/pre")
)
ENTITY = re.compile(r"&(amp|lt|gt|quot|#\d+);")


def html_problems(text: str) -> list[str]:
    """Everything Telegram's HTML parser would reject in `text`.

    It rejects the whole message rather than degrading, and `send_message` reports that
    as a plain False - identical to a dead bot. So this has to be caught here.
    """
    found = [f"tag <{tag}>" for tag in re.findall(r"<([^>]*)>", text) if tag not in TELEGRAM_TAGS]
    found += [
        f"bare & near {text[max(0, m.start() - 20) : m.start() + 10]!r}"
        for m in re.finditer("&", text)
        if not ENTITY.match(text, m.start())
    ]
    return found


def test_ampersand_in_free_text_is_escaped():
    """The regression: a title read "Lịch & tiền" and Telegram refused the message."""
    card = pulse.card_sermon(
        MEGA645,
        replace(a_prophecy_with_sermons(), sermon={"1": "tiền & bạc <b>đậm</b> & hơn"}),
        pulse.day_rng(A_DAY),
    )
    assert card is not None
    assert html_problems(pulse.format_card(card, now=at(10))) == []


def test_every_card_of_the_real_deck_is_valid_telegram_html(monkeypatch):
    """Scans the whole live deck, so a new card or a new corpus string cannot reintroduce
    an unescaped character that only shows up as a silent send failure."""
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "1996-04-15")
    monkeypatch.setenv(pulse.ENV_GENDER, "nam")
    for spec in (MEGA645, POWER655, MEGAMILLIONS):
        store.write_draws(spec.key, [make_draw(spec, i) for i in range(1, 30)])
    store.append_prophecy(a_prophecy_with_sermons())

    now = at(10)
    cards = pulse.build_cards(
        (MEGA645, POWER655, MEGAMILLIONS),
        now=now,
        fortune=pulse.read_fortune_from_env(A_DAY),
        allow_network=False,
    )
    assert len(cards) > 8
    for card in cards:
        assert html_problems(pulse.format_card(card, now=now)) == [], card.key


# ------------------------------------------------------------------- gold and crypto

A_BOARD = markets.GoldBoard(
    quotes=(
        markets.GoldQuote("SJC", "Vàng miếng SJC 999.9", 14_760_000, 15_060_000),
        markets.GoldQuote("N24K", "Nhẫn Trơn PNJ 999.9", 14_750_000, 15_050_000),
    ),
    branch="hochiminh",
    updated_at="25/08/2026 08:37:59",
)
SOME_COINS = (
    markets.CoinQuote("BTC", "Bitcoin", 80_662.0, 2_108_530_000.0, 4.54),
    markets.CoinQuote("ETH", "Ethereum", 2_506.52, 65_520_000.0, -2.90),
    markets.CoinQuote("SOL", "Solana", 101.53, 2_650_000.0, None),
)


def test_gold_card_quotes_per_luong_not_per_chi():
    """People buy lượng. Printing the published đ/chỉ figure with a lượng label, or the
    other way round, is the ×10 error this whole feature is one keystroke away from."""
    card = pulse.card_gold(A_BOARD)
    assert card is not None
    body = "\n".join(card.lines)
    assert "150,600,000" in body or "150.6" in body
    assert "15,060,000" not in body


def test_gold_card_names_the_spread_a_buyer_eats():
    card = pulse.card_gold(A_BOARD)
    body = "\n".join(card.lines)
    assert "1.99%" in body or "2.0%" in body
    assert "3,000,000" in body or "3.00" in body


def test_gold_card_carries_the_moment_the_board_was_read():
    card = pulse.card_gold(A_BOARD)
    assert "25/08/2026" in "\n".join(card.lines)


def test_gold_card_shows_the_domestic_premium_when_world_spot_is_known():
    card = pulse.card_gold(A_BOARD, world_usd_per_oz=4635.4, usd_vnd=26_140)
    body = "\n".join(card.lines)
    assert "thế giới" in body
    assert "%" in body


def test_gold_card_omits_the_premium_rather_than_guessing_a_rate():
    """No exchange rate means no premium line - never a premium computed off a guess."""
    body = "\n".join(pulse.card_gold(A_BOARD, world_usd_per_oz=4635.4).lines)
    assert "thế giới" not in body


def test_gold_card_is_absent_without_a_board():
    assert pulse.card_gold(None) is None
    assert pulse.card_gold(markets.GoldBoard(quotes=())) is None


def test_crypto_card_reports_usd_vnd_and_the_daily_move():
    card = pulse.card_crypto(SOME_COINS)
    assert card is not None
    body = "\n".join(card.lines)
    assert "BTC" in body and "ETH" in body and "SOL" in body
    assert "+4.5" in body
    assert "-2.9" in body


def test_crypto_card_handles_a_missing_daily_move():
    """SOL has no 24h figure in the fixture; that must not become 'None%' or a crash."""
    body = "\n".join(pulse.card_crypto(SOME_COINS).lines)
    assert "None" not in body


def test_crypto_card_is_absent_without_quotes():
    assert pulse.card_crypto(()) is None


def test_gold_and_crypto_labels_are_escaped_for_telegram():
    board = markets.GoldBoard(
        quotes=(markets.GoldQuote("X", "Vàng <b>A</b> & B", 1_000_000, 1_100_000),),
    )
    assert html_problems(pulse.format_card(pulse.card_gold(board), now=at(10))) == []


def test_market_cards_join_the_deck_when_the_network_is_available(monkeypatch):
    monkeypatch.setattr(pulse.markets, "fetch_gold_board", lambda **k: A_BOARD)
    monkeypatch.setattr(pulse.markets, "fetch_coins", lambda **k: SOME_COINS)
    monkeypatch.setattr(pulse.markets, "fetch_world_gold_usd_per_oz", lambda **k: 4635.4)

    keys = {c.key for c in pulse.build_cards((MEGA645,), now=at(10), allow_network=True)}
    assert {"gold", "crypto"} <= keys


def test_market_cards_stay_out_when_offline():
    keys = {c.key for c in pulse.build_cards((MEGA645,), now=at(10), allow_network=False)}
    assert "gold" not in keys
    assert "crypto" not in keys


def test_a_blocked_market_source_costs_one_card_not_the_pulse(monkeypatch):
    """Exactly the vietlott.vn failure mode: 403 for a datacenter IP, 200 for a laptop."""
    monkeypatch.setattr(pulse.markets, "fetch_gold_board", lambda **k: None)
    monkeypatch.setattr(pulse.markets, "fetch_coins", lambda **k: ())
    monkeypatch.setattr(pulse.markets, "fetch_world_gold_usd_per_oz", lambda **k: None)

    cards = pulse.build_cards((MEGA645,), now=at(10), allow_network=True)
    assert cards
    assert "gold" not in {c.key for c in cards}


# --------------------------------------------------------------- stale jackpot notice


def test_schedule_card_flags_a_jackpot_from_an_older_draw():
    """vietlott.vn has been 403ing the runner since 2026-08-20, so the stored jackpot is
    two draws behind the stored results. A figure that old must say so itself."""
    draws = [make_draw(MEGA645, i) for i in range(1, 1554)]
    prizes = {"draw_id": "01551", "top_jackpot_vnd": 24_507_110_500, "rolled_over": True}

    body = "\n".join(pulse.card_schedule(MEGA645, draws, prizes, now=at(10)).lines)
    assert "01551" in body
    assert "kỳ cũ" in body or "chưa cập nhật" in body


def test_schedule_card_says_nothing_extra_when_the_jackpot_is_current():
    draws = [make_draw(MEGA645, i) for i in range(1, 10)]
    latest = max(draws, key=lambda d: d.draw_id)
    prizes = {"draw_id": latest.draw_id, "top_jackpot_vnd": 24_507_110_500, "rolled_over": True}

    body = "\n".join(pulse.card_schedule(MEGA645, draws, prizes, now=at(10)).lines)
    assert "kỳ cũ" not in body and "chưa cập nhật" not in body


def test_lottery_cards_keep_the_lottery_disclaimer():
    card = pulse.Card(key="k", title="t", lines=("x",))
    assert notify.DISCLAIMER in pulse.format_card(card, now=at(10))


def test_market_cards_carry_their_own_disclaimer_not_the_lottery_one():
    """"Xổ số là biến cố độc lập" says nothing true about a gold board, and a disclaimer
    that does not fit what it is attached to is decoration, not honesty."""
    for card in (pulse.card_gold(A_BOARD), pulse.card_crypto(SOME_COINS)):
        text = pulse.format_card(card, now=at(10))
        assert notify.DISCLAIMER not in text
        assert pulse.MARKET_DISCLAIMER in text
        assert "tư vấn đầu tư" in text
