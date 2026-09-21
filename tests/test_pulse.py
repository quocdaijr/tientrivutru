"""Random pulses through the day. Two contracts: the schedule is reproducible, and
nothing here may leak a birth date or raise on missing data."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta

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


# --------------------------------------------------------------------------- schedule


def test_slots_are_stable_for_the_same_day():
    assert pulse.slots_for(A_DAY) == pulse.slots_for(A_DAY)


def test_bands_tile_the_window_exactly():
    """No gap between bands and no overlap, or the hours stop being sorted and distinct."""
    for count in range(pulse.MIN_PER_DAY, pulse.MAX_PER_DAY + 1):
        bands = pulse.bands_for(count)
        assert len(bands) == count
        covered = [hour for band in bands for hour in band]
        assert covered == list(range(pulse.FIRST_HOUR_VN, pulse.LAST_HOUR_VN + 1)), count


def test_slots_hold_their_invariants_across_a_year():
    for offset in range(365):
        day = A_DAY + timedelta(days=offset)
        slots = pulse.slots_for(day)

        assert pulse.MIN_PER_DAY <= len(slots) <= pulse.MAX_PER_DAY, day
        assert len(set(slots)) == len(slots), day
        assert list(slots) == sorted(slots), day
        # One pulse per band is what makes sorted-and-distinct true by construction.
        for hour, band in zip(slots, pulse.bands_for(len(slots)), strict=True):
            assert hour in band, (day, slots)


def test_slots_actually_move_around_the_day():
    """A schedule that always picked 09h would satisfy every invariant above."""
    seen = {hour for offset in range(365) for hour in pulse.slots_for(A_DAY + timedelta(offset))}
    assert len(seen) > 8


def hours_over(days: int) -> Counter:
    return Counter(
        hour
        for offset in range(days)
        for hour in pulse.slots_for(A_DAY + timedelta(days=offset))
    )


def test_hours_are_spread_evenly_over_the_window():
    """The regression this replaced: the closed-form min-gap sampler was uniform over
    valid *schedules*, not over hours, and edge hours sit in more valid schedules. It put
    08h and 22h 1.55x above 20h. Stratifying by band brings that to about 1.14x."""
    counts = hours_over(3650)
    per_hour = [counts[h] for h in range(pulse.FIRST_HOUR_VN, pulse.LAST_HOUR_VN + 1)]
    assert min(per_hour) > 0
    assert max(per_hour) / min(per_hour) < 1.25, dict(sorted(counts.items()))


def test_no_hour_outside_the_window_is_ever_used():
    counts = hours_over(3650)
    assert set(counts) == set(range(pulse.FIRST_HOUR_VN, pulse.LAST_HOUR_VN + 1))


def test_close_together_days_are_the_known_price_of_a_flat_spread():
    """Bands let two pulses land in adjacent hours across a band boundary. That is the
    trade an even spread costs, so it is measured rather than left to be discovered."""
    tight = sum(
        1
        for offset in range(3650)
        for slots in [pulse.slots_for(A_DAY + timedelta(days=offset))]
        if any(later - earlier < 3 for earlier, later in zip(slots, slots[1:], strict=False))
    )
    assert 0.10 < tight / 3650 < 0.20, tight / 3650


def test_slots_do_not_depend_on_python_hash_seed():
    """`hash()` is salted per process; the plan must survive a new runner."""

    def plan_with(seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "from datetime import date\n"
                "from tientrivutru.pulse import slots_for\n"
                "print(slots_for(date(2026, 8, 23)))",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout.strip()

    assert plan_with("0") == plan_with("1")


def test_should_fire_only_on_planned_hours():
    slots = pulse.slots_for(A_DAY)
    fired = tuple(hour for hour in range(24) if pulse.should_fire(at(hour)))
    assert fired == slots


def test_slot_index_counts_from_zero_and_is_none_off_plan():
    slots = pulse.slots_for(A_DAY)
    assert [pulse.slot_index(at(hour)) for hour in slots] == list(range(len(slots)))

    off_plan = next(hour for hour in range(24) if hour not in slots)
    assert pulse.slot_index(at(off_plan)) is None


def test_plan_is_pinned_so_a_seed_change_is_visible():
    """A regression pin, computed once from the implementation and then frozen.

    Changing the seed recipe or the sampling is a behaviour change - it should show up
    here rather than silently reshuffling every day's schedule.
    """
    assert pulse.slots_for(date(2026, 8, 23)) == pulse.PINNED_PLAN_2026_08_23


# ------------------------------------------------------------------------------ cards


def a_prophecy_with_sermons() -> Prophecy:
    return Prophecy(
        game=MEGA645.key,
        draw_id="01551",
        draw_date=A_DAY,
        numbers=tuple(range(1, 13)),
        seed="deadbeef" * 8,
        signals={},
        sermon={str(n): f"số {n} gọi tên anh" for n in range(1, 13)},
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


def test_sermon_card_quotes_one_line_from_the_pending_prophecy():
    card = pulse.card_sermon(MEGA645, a_prophecy_with_sermons(), pulse.day_rng(A_DAY))
    assert card is not None
    assert "gọi tên anh" in "\n".join(card.lines)


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


def test_a_day_never_repeats_a_kind_of_card():
    """Two `hot_cold` cards in one day read as the bot repeating itself, even when they
    are for different games - so the dedupe is on the kind, not on the object."""
    deck = a_realistic_deck()
    for offset in range(365):
        day = A_DAY + timedelta(days=offset)
        picked = [pulse.card_for_slot(deck, day, i) for i in range(pulse.MAX_PER_DAY)]
        assert len({card.key for card in picked}) == pulse.MAX_PER_DAY, day


def test_day_order_keeps_every_card_reachable():
    """Fronting one card per kind must not drop the others off the end."""
    deck = a_realistic_deck()
    order = pulse.day_order(deck, A_DAY)
    assert sorted(order, key=id) == sorted(deck, key=id)
    assert len(order) == len(deck)


def test_day_order_fronts_one_card_of_each_kind():
    deck = a_realistic_deck()
    kinds = {card.key for card in deck}
    front = pulse.day_order(deck, A_DAY)[: len(kinds)]
    assert {card.key for card in front} == kinds


def test_card_for_slot_is_stable_for_the_same_day_and_index():
    deck = a_realistic_deck()
    assert pulse.card_for_slot(deck, A_DAY, 1) == pulse.card_for_slot(deck, A_DAY, 1)


def test_card_for_slot_wraps_when_there_are_fewer_cards_than_slots():
    cards = (pulse.Card(key="only", title="t", lines=("x",)),)
    assert pulse.card_for_slot(cards, A_DAY, 2).key == "only"


def test_card_for_slot_is_none_with_no_cards():
    assert pulse.card_for_slot((), A_DAY, 0) is None


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


def test_cli_sends_nothing_off_plan(counting_send, monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    off_plan = next(h for h in range(24) if h not in pulse.slots_for(A_DAY))

    assert run_cli("--now", at(off_plan).isoformat(), "--offline") == 0
    assert counting_send.calls == 0


def test_cli_sends_on_a_planned_hour(counting_send, monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    on_plan = pulse.slots_for(A_DAY)[0]

    assert run_cli("--now", at(on_plan).isoformat(), "--offline") == 0
    assert counting_send.calls == 1
    assert notify.DISCLAIMER in counting_send.messages[0]


def test_cli_force_ignores_the_plan(counting_send, monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    off_plan = next(h for h in range(24) if h not in pulse.slots_for(A_DAY))

    assert run_cli("--force", "--now", at(off_plan).isoformat(), "--offline") == 0
    assert counting_send.calls == 1


def test_cli_reports_a_failed_send(counting_send, monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    counting_send.result = False

    assert run_cli("--force", "--offline") == 1


def test_cli_dry_run_sends_nothing(counting_send, monkeypatch, capsys):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    assert run_cli("--force", "--dry-run", "--offline") == 0
    assert counting_send.calls == 0
    assert capsys.readouterr().out.strip()


def test_cli_dry_run_needs_no_telegram_config(counting_send, capsys):
    """Previewing a pulse locally must not require anyone's bot token."""
    assert run_cli("--force", "--dry-run", "--offline") == 0
    assert counting_send.calls == 0


def test_cli_fails_loudly_without_telegram_config(counting_send):
    assert run_cli("--force", "--offline") == 1
    assert counting_send.calls == 0


def test_cli_plan_prints_the_hours_and_sends_nothing(counting_send, capsys):
    assert run_cli("--plan", "--now", at(10).isoformat()) == 0
    assert counting_send.calls == 0
    out = capsys.readouterr().out
    for hour in pulse.slots_for(A_DAY):
        assert f"{hour:02d}" in out


def test_cli_never_prints_the_birth_date(counting_send, monkeypatch, capsys):
    """Actions logs are public. The derived fortune may travel; the date may not."""
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "1996-04-15")
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    assert run_cli("--force", "--offline") == 0
    assert "1996-04-15" not in capsys.readouterr().out


def test_cli_warns_without_leaking_a_malformed_birth_date(counting_send, monkeypatch, capsys):
    monkeypatch.setenv(pulse.ENV_BIRTH_DATE, "sinh-nam-1996")
    assert run_cli("--force", "--dry-run", "--offline") == 0
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
