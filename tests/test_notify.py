"""Telegram delivery. The contract that matters: it can fail without breaking anything."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import make_draw, make_prophecy
from tientrivutru import kienthiet_oracle, kienthiet_scoreboard, notify, scoreboard
from tientrivutru.games import MEGA645, POWER655
from tientrivutru.models import utc_now
from tientrivutru.sources import kienthiet


@pytest.fixture(autouse=True)
def no_telegram_env(monkeypatch):
    monkeypatch.delenv(notify.ENV_TOKEN, raising=False)
    monkeypatch.delenv(notify.ENV_CHAT_ID, raising=False)


def test_unconfigured_send_returns_false_without_network():
    """No token, no request, no exception - just a False."""
    assert notify.send_message("xin chào") is False


@pytest.mark.parametrize(
    "token,chat", [("", "123"), ("abc", ""), ("", ""), ("   ", "123")]
)
def test_partial_config_is_treated_as_unconfigured(monkeypatch, token, chat):
    monkeypatch.setenv(notify.ENV_TOKEN, token)
    monkeypatch.setenv(notify.ENV_CHAT_ID, chat)
    assert notify.read_config() is None
    assert notify.send_message("x") is False


def test_full_config_is_read(monkeypatch):
    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    assert notify.read_config() == ("tok", "42")


def test_require_config_raises_when_absent():
    with pytest.raises(notify.TelegramNotConfigured, match="TELEGRAM_BOT_TOKEN"):
        notify.require_config()


def test_send_swallows_network_errors(monkeypatch):
    """A dead Telegram must never propagate into the pipeline."""
    import requests

    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    def boom(*args, **kwargs):
        raise requests.ConnectionError("telegram is down")

    monkeypatch.setattr(requests, "post", boom)
    assert notify.send_message("x") is False


def test_send_returns_false_on_api_not_ok(monkeypatch):
    import requests

    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": False, "description": "chat not found"}

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse())
    assert notify.send_message("x") is False


def test_message_is_truncated_to_telegram_limit(monkeypatch):
    import requests

    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def capture(url, json, timeout):
        captured.update(json)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", capture)
    assert notify.send_message("x" * 9000) is True
    assert len(captured["text"]) == notify.MAX_MESSAGE_CHARS


def test_prophecy_message_carries_numbers_and_disclaimer():
    prophecy = make_prophecy(MEGA645, 1551, numbers=tuple(range(1, 13)))
    text = notify.format_prophecy(MEGA645, prophecy)

    assert "Mega 6/45" in text
    assert "01551" in text
    assert "<b>07</b>" in text
    assert "biến cố độc lập" in text


def test_prophecy_message_includes_running_roi_when_scored():
    prophecies = [make_prophecy(MEGA645, i, numbers=tuple(range(1, 13))) for i in (1, 2)]
    draws = [make_draw(MEGA645, 1, main=(1, 2, 3, 40, 41, 42))]
    score = scoreboard.build(MEGA645, prophecies, draws)

    text = notify.format_prophecy(MEGA645, prophecies[1], score)
    assert "ROI" in text
    assert "bỏ jackpot" in text


def test_result_message_reports_hits_against_chance():
    prophecy = make_prophecy(POWER655, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(POWER655, 1, main=(1, 2, 3, 50, 51, 52), bonus=55)
    row = scoreboard.score_one(POWER655, prophecy, draw)

    text = notify.format_result(POWER655, draw, row)
    assert "3/12" in text
    assert "Power 6/55" in text
    assert "phụ <b>55</b>" in text
    assert "biến cố độc lập" in text


def test_result_message_says_zero_when_nothing_won():
    prophecy = make_prophecy(MEGA645, 1, numbers=tuple(range(1, 13)))
    draw = make_draw(MEGA645, 1, main=(20, 21, 22, 23, 24, 25))
    row = scoreboard.score_one(MEGA645, prophecy, draw)

    text = notify.format_result(MEGA645, draw, row)
    assert "0đ trên" in text
    assert "💀" in text


def test_pending_prophecies_excludes_settled_draws():
    prophecies = [make_prophecy(MEGA645, i) for i in (1, 2, 3)]
    draws = [make_draw(MEGA645, 1), make_draw(MEGA645, 2)]

    pending = notify.pending_prophecies(prophecies, draws)
    assert [p.draw_id for p in pending] == ["00003"]


# ------------------------------------------------------------------- xổ số kiến thiết

KT_TIERS = (
    ("db", ("510332",)),
    ("g1", ("89516",)),
    ("g2", ("44895",)),
    ("g3", ("52640", "02439")),
    ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
    ("g5", ("1635",)),
    ("g6", ("9670", "9023", "3404")),
    ("g7", ("516",)),
    ("g8", ("54",)),
)
KT_DAY = date(2026, 8, 20)


def a_board(province: str = "an-giang") -> kienthiet.Board:
    return kienthiet.Board(date=KT_DAY, region="mn", province=province, tiers=KT_TIERS)


def a_ve(ve: str, province: str = "an-giang") -> kienthiet_oracle.VeProphecy:
    return kienthiet_oracle.VeProphecy(
        province=province,
        region="mn",
        draw_date=KT_DAY,
        ve=ve,
        seed="0" * 64,
        signals={},
        sermon="Một vé thôi. Tham là mất lộc.",
        reasons=(),
        karma=None,
        oracle_version=kienthiet_oracle.KIENTHIET_ORACLE_VERSION,
        created_at=utc_now(),
    )


def test_ve_prophecy_message_lists_every_dai_of_the_day():
    message = notify.format_ve_prophecy([a_ve("111111"), a_ve("222222", "tay-ninh")])

    assert "An Giang" in message
    assert "Tây Ninh" in message
    assert "111111" in message and "222222" in message
    assert "10.000" in message or "10,000" in message


def test_ve_prophecy_message_carries_the_disclaimer():
    assert notify.DISCLAIMER in notify.format_ve_prophecy([a_ve("111111")])


def test_ve_prophecy_message_refuses_an_empty_list():
    with pytest.raises(ValueError, match="empty"):
        notify.format_ve_prophecy([])


def test_ve_result_message_reports_the_special_and_the_payout():
    rows = kienthiet_scoreboard.score_rows([a_ve("510332")], [a_board()])
    score = kienthiet_scoreboard.build([a_ve("510332")], [a_board()])
    message = notify.format_ve_result(rows, score)

    assert "510332" in message
    assert "2.000.000.000" in message or "2,000,000,000" in message


def test_ve_result_message_says_truot_when_nothing_won():
    rows = kienthiet_scoreboard.score_rows([a_ve("777777")], [a_board()])
    message = notify.format_ve_result(rows)

    assert "trượt" in message


def test_ve_result_message_states_the_exact_theoretical_roi():
    """The one number on the page that is arithmetic rather than a sample."""
    tickets, boards = [a_ve("777777")], [a_board()]
    message = notify.format_ve_result(
        kienthiet_scoreboard.score_rows(tickets, boards),
        kienthiet_scoreboard.build(tickets, boards),
    )
    assert "-50.0%" in message


# -------------------------------------------------------- the jackpot went quiet alert


def test_prize_alert_names_the_game_the_gap_and_the_cause():
    """Written for the 2026-08-25 outage. An alert that says only "stale" sends its
    reader digging; this one has to carry the draw ids and the number that is being
    shown in the meantime."""
    from tientrivutru import prize_health
    from tientrivutru.games import MEGA645, POWER655

    message = notify.format_prize_alert(
        (
            (POWER655, prize_health.freshness({"draw_id": "01388"}, "01396")),
            (MEGA645, prize_health.freshness({"draw_id": "01553"}, "01560")),
        )
    )

    assert "Power 6/55" in message
    assert "Mega 6/45" in message
    assert "8 kỳ" in message
    assert "7 kỳ" in message
    assert "#01388" in message
    assert "#01560" in message


def test_prize_alert_says_when_nothing_was_ever_read():
    from tientrivutru import prize_health
    from tientrivutru.games import MEGA645

    message = notify.format_prize_alert(((MEGA645, prize_health.freshness(None, "01560")),))

    assert "chưa đọc được" in message


def test_prize_alert_refuses_an_empty_list():
    """No stale game means no message. Building one anyway would produce an alert about
    nothing, which is how alerts get muted."""
    import pytest

    with pytest.raises(ValueError, match="không có game nào"):
        notify.format_prize_alert(())
