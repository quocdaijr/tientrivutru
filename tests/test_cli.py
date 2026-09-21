"""CLI wiring, and the draw-targeting logic that keeps the oracle honest."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from conftest import make_draw
from tientrivutru import cli, store
from tientrivutru.games import MEGA645, POWER655
from tientrivutru.sources import kienthiet

VN = cli.VN_TZ


def _mega_history():
    """Real upstream state on 2026-08-19: last stored draw #1549 on Fri 14 Aug."""
    return [make_draw(MEGA645, 1549, main=(7, 9, 13, 31, 35, 44), day=date(2026, 8, 14))]


def test_next_target_skips_the_draw_upstream_missed():
    """Upstream lacks Sun 16 Aug (#1550), so Wed 19 Aug must be #1551, not #1550.

    Getting this wrong would make the oracle "predict" a draw that already happened.
    """
    now = datetime(2026, 8, 19, 10, 0, tzinfo=VN)
    draw_id, draw_date = cli.next_target(MEGA645, _mega_history(), now=now)

    assert draw_date == date(2026, 8, 19)
    assert draw_id == "01551"


def test_next_target_moves_on_after_the_draw_time():
    """After 18:00 the day's draw is gone; target the next draw day."""
    now = datetime(2026, 8, 19, 19, 30, tzinfo=VN)
    draw_id, draw_date = cli.next_target(MEGA645, _mega_history(), now=now)

    assert draw_date == date(2026, 8, 21)  # Friday
    assert draw_id == "01552"


def test_next_target_before_draw_time_targets_today():
    now = datetime(2026, 8, 19, 17, 59, tzinfo=VN)
    _, draw_date = cli.next_target(MEGA645, _mega_history(), now=now)
    assert draw_date == date(2026, 8, 19)


def test_next_target_on_a_non_draw_day():
    """Power 6/55 draws Tue/Thu/Sat, so from Wednesday the target is Thursday."""
    history = [
        make_draw(
            POWER655, 1386, main=(3, 15, 18, 38, 41, 48), bonus=30, day=date(2026, 8, 18)
        )
    ]
    now = datetime(2026, 8, 19, 10, 0, tzinfo=VN)
    draw_id, draw_date = cli.next_target(POWER655, history, now=now)

    assert draw_date == date(2026, 8, 20)
    assert draw_id == "01387"


def test_next_target_requires_history():
    with pytest.raises(RuntimeError, match="run `tientrivutru ingest`"):
        cli.next_target(MEGA645, [])


def test_next_target_returns_a_zero_padded_id():
    """Regression: an unpadded '1551' silently fails every == against stored '01551'."""
    draw_id, _ = cli.next_target(
        MEGA645, _mega_history(), now=datetime(2026, 8, 19, 10, 0, tzinfo=VN)
    )
    assert len(draw_id) == 5
    assert draw_id.startswith("0")


def test_today_shows_the_prophecy_that_oracle_just_wrote(capsys):
    """Regression: `today` reported "chưa tiên tri" straight after `oracle` wrote one,
    because the two sides compared a padded id against an unpadded one.
    """
    store.write_draws("mega645", _mega_history())

    oracle_args = cli.build_parser().parse_args(["oracle", "--game", "mega645", "--offline"])
    oracle_args.handler(oracle_args)
    written = store.read_prophecies("mega645")[0]
    capsys.readouterr()

    today_args = cli.build_parser().parse_args(["today", "--game", "mega645"])
    today_args.handler(today_args)
    out = capsys.readouterr().out

    assert "chưa tiên tri" not in out
    assert "đã tiên tri" in out
    assert f"{written.numbers[0]:02d}" in out


@pytest.mark.parametrize(
    "now,expected",
    [
        (datetime(2026, 8, 19, 17, 59, tzinfo=VN), False),
        (datetime(2026, 8, 19, 18, 0, tzinfo=VN), True),
        (datetime(2026, 8, 20, 1, 0, tzinfo=VN), True),
    ],
)
def test_draw_has_happened(now, expected):
    assert cli.draw_has_happened(date(2026, 8, 19), now) is expected


def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


@pytest.mark.parametrize(
    "argv",
    [
        ["ingest", "--check-gaps"],
        ["stats", "--game", "mega645"],
        ["oracle", "--dry-run", "--offline"],
        ["score"],
        ["backtest", "--limit", "10"],
        ["today"],
        ["ingest", "--region", "mn", "--since", "2026-08-01"],
        ["ingest", "--backfill"],
        ["stats", "--region", "mb"],
        ["oracle", "--region", "mt", "--dry-run", "--offline"],
    ],
)
def test_every_command_parses(argv):
    args = cli.build_parser().parse_args(argv)
    assert callable(args.handler)


def test_unknown_game_is_rejected():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["stats", "--game", "keno"])


def test_unknown_region_is_rejected():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["stats", "--region", "mien-tay"])


def test_stats_reports_missing_data_instead_of_crashing(capsys):
    args = cli.build_parser().parse_args(["stats", "--game", "mega645"])
    assert args.handler(args) == 1
    assert "ingest" in capsys.readouterr().out


def test_oracle_dry_run_writes_nothing(capsys):
    store.write_draws("mega645", _mega_history())
    args = cli.build_parser().parse_args(["oracle", "--game", "mega645", "--dry-run", "--offline"])

    assert args.handler(args) == 0
    assert store.read_prophecies() == ()
    assert "dry-run" in capsys.readouterr().out


def test_oracle_writes_then_refuses_duplicate(capsys):
    store.write_draws("mega645", _mega_history())
    args = cli.build_parser().parse_args(["oracle", "--game", "mega645", "--offline"])

    assert args.handler(args) == 0
    assert len(store.read_prophecies()) == 1
    capsys.readouterr()

    assert args.handler(args) == 0
    assert len(store.read_prophecies()) == 1, "a second run must not append a duplicate"
    assert "bỏ qua" in capsys.readouterr().out


def test_score_writes_scoreboard_file(capsys):
    history = _mega_history()
    store.write_draws("mega645", history)
    oracle_args = cli.build_parser().parse_args(["oracle", "--game", "mega645", "--offline"])
    oracle_args.handler(oracle_args)
    capsys.readouterr()

    score_args = cli.build_parser().parse_args(["score", "--game", "mega645"])
    assert score_args.handler(score_args) == 0

    payload = store.read_scoreboard()
    assert payload is not None
    assert "mega645" in payload["per_game"]
    # The prophecy targets an unfinished draw, so nothing is scorable yet.
    assert payload["per_game"]["mega645"]["draws_scored"] == 0


def test_today_runs_with_history(capsys):
    store.write_draws("mega645", _mega_history())
    args = cli.build_parser().parse_args(["today", "--game", "mega645"])

    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "Mega 6/45" in out
    assert "01549" in out


def test_backtest_scores_history_without_writing(capsys):
    draws = [
        make_draw(MEGA645, i, main=(1, 2, 3, 40, 41, 42), day=date(2026, 1, 1) + timedelta(days=i))
        for i in range(1, 21)
    ]
    store.write_draws("mega645", draws)
    args = cli.build_parser().parse_args(["backtest", "--game", "mega645", "--limit", "10"])

    assert args.handler(args) == 0
    assert store.read_prophecies() == (), "backtest is counterfactual and must not persist"
    assert "phản thực" in capsys.readouterr().out


def test_every_command_prints_the_disclaimer(capsys):
    store.write_draws("mega645", _mega_history())
    commands = (
        ["today", "--game", "mega645"],
        ["oracle", "--game", "mega645", "--dry-run", "--offline"],
    )
    for argv in commands:
        args = cli.build_parser().parse_args(argv)
        args.handler(args)
        assert "paper-trading" in capsys.readouterr().out


# --------------------------------------------------------------- xổ số kiến thiết


def _a_southern_board(day: date, province: str = "an-giang") -> kienthiet.Board:
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


def test_region_narrows_stats_to_one_mien(capsys):
    store.write_boards("mn", [_a_southern_board(date(2026, 8, 20))])
    args = cli.build_parser().parse_args(["stats", "--region", "mn"])
    args.handler(args)

    out = capsys.readouterr().out
    assert "Miền Nam" in out
    assert "Miền Trung" not in out


def test_ingest_with_a_region_leaves_the_vietlott_games_alone(monkeypatch, capsys):
    """--region means kiến thiết only; nothing should reach for a Vietlott mirror."""
    from tientrivutru import kienthiet_ingest

    def explode(*_a, **_k):  # pragma: no cover - the point is that it never runs
        raise AssertionError("a Vietlott mirror was fetched for a --region run")

    monkeypatch.setattr(cli, "_fetch_for", explode)
    monkeypatch.setattr(
        kienthiet_ingest,
        "ingest_region",
        lambda region, **_k: kienthiet_ingest.IngestReport(region=region),
    )

    args = cli.build_parser().parse_args(["ingest", "--region", "mn"])
    assert args.handler(args) == 0
    assert "Mega 6/45" not in capsys.readouterr().out


def test_oracle_writes_a_ve_then_refuses_a_second(capsys):
    """The vé guard is the ticket half of the append-only rule."""
    today = cli.today_vn()
    store.write_boards("mn", [_a_southern_board(today - timedelta(days=7))])

    argv = ["oracle", "--region", "mn", "--offline"]
    cli.build_parser().parse_args(argv).handler(cli.build_parser().parse_args(argv))
    first = len(store.read_ve())

    args = cli.build_parser().parse_args(argv)
    args.handler(args)

    assert first == len(store.read_ve())
    assert first >= 1
    assert "bỏ qua" in capsys.readouterr().out


def test_mien_bac_is_never_phan(capsys):
    args = cli.build_parser().parse_args(["oracle", "--region", "mb", "--offline"])
    args.handler(args)

    assert store.read_ve() == ()


# ------------------------------------------------- jackpot refresh must never be fatal


def test_prize_failure_does_not_break_ingest(monkeypatch, capsys):
    """The jackpot is commentary on a draw, not part of it. A vietlott.vn layout change
    must cost us the figure, not the whole ingest run."""
    from tientrivutru.sources import vietlott_prizes

    def explode(*_args, **_kwargs):
        raise vietlott_prizes.PrizeParseError("power655: no gt_jackpot block")

    monkeypatch.setattr(cli.vietlott_prizes, "fetch_prizes", explode)

    cli._refresh_prizes(POWER655, "01386")

    assert "không đọc được giải thưởng" in capsys.readouterr().out
    assert store.read_prizes("power655") is None


def test_prize_refresh_stores_and_reports(monkeypatch, capsys):
    from tientrivutru.sources.vietlott_prizes import DrawPrizes, PrizeTier

    fake = DrawPrizes(
        game="power655",
        draw_id="01386",
        jackpots={"Jackpot 1": 34_897_731_150},
        tiers=(PrizeTier("Jackpot 1", 0, 34_897_731_150),),
        fetched_at="2026-08-20T07:00:00+00:00",
    )
    monkeypatch.setattr(cli.vietlott_prizes, "fetch_prizes", lambda *a, **k: fake)

    cli._refresh_prizes(POWER655, "01386")

    out = capsys.readouterr().out
    assert "34,90 tỷ" in out or "34.90 tỷ" in out
    assert "cộng dồn sang kỳ sau" in out
    assert store.read_prizes("power655")["top_jackpot_vnd"] == 34_897_731_150


# ------------------------------------------- ...but it must stop being silent about it


def _explode_prizes(monkeypatch):
    from tientrivutru.sources import vietlott_prizes

    def explode(*_args, **_kwargs):
        raise vietlott_prizes.PrizeParseError("power655: no gt_jackpot block")

    monkeypatch.setattr(cli.vietlott_prizes, "fetch_prizes", explode)


def _store_stale_prize(game: str, draw_id: str):
    from tientrivutru.sources.vietlott_prizes import DrawPrizes, PrizeTier

    store.write_prizes(
        DrawPrizes(
            game=game,
            draw_id=draw_id,
            jackpots={"Jackpot 1": 34_897_731_150},
            tiers=(PrizeTier("Jackpot 1", 0, 34_897_731_150),),
            fetched_at="2026-08-25T03:46:51+00:00",
        )
    )


def test_one_draw_behind_is_reported_but_not_a_problem(monkeypatch, capsys):
    """A single failed fetch between two draws is a transient, and an alert that fires
    on transients is an alert nobody reads."""
    _store_stale_prize("power655", "01385")
    _explode_prizes(monkeypatch)

    stale = cli._refresh_prizes(POWER655, "01386")

    assert stale is False
    assert "không đọc được giải thưởng" in capsys.readouterr().out


def test_prizes_stuck_for_several_draws_is_reported_as_a_problem(monkeypatch, capsys):
    """The 2026-08-25 outage: the figure sat eight draws behind for eighteen days while
    every run stayed green. `_refresh_prizes` must now say so out loud."""
    _store_stale_prize("power655", "01388")
    _explode_prizes(monkeypatch)

    stale = cli._refresh_prizes(POWER655, "01396")

    out = capsys.readouterr().out
    assert stale is True
    assert "8 kỳ" in out


def test_never_fetched_prize_is_a_problem(monkeypatch, capsys):
    _explode_prizes(monkeypatch)

    stale = cli._refresh_prizes(POWER655, "01396")

    assert stale is True
    assert "chưa đọc được" in capsys.readouterr().out


def test_ingest_exits_non_zero_when_the_jackpot_is_stuck(monkeypatch, capsys):
    """The exit code is the part CI can act on, so staleness has to reach it."""
    from tientrivutru.models import Draw

    _store_stale_prize("power655", "01388")
    _explode_prizes(monkeypatch)
    monkeypatch.setattr(
        cli,
        "_fetch_for",
        lambda spec: (
            Draw(
                game=spec.key,
                draw_id="01396",
                date=date(2026, 9, 10),
                main=(2, 5, 28, 32, 51, 53),
                bonus=50 if spec.has_bonus else None,
                source="test",
            ),
        ),
    )

    args = cli.build_parser().parse_args(["ingest", "--game", "power655"])

    assert cli.cmd_ingest(args) == 1
    assert "8 kỳ" in capsys.readouterr().out


def test_notify_sends_one_alert_when_the_jackpot_is_stuck(monkeypatch, capsys):
    """The exit code reaches CI; this reaches a phone. Both were missing during the
    eighteen-day silence."""
    from tientrivutru import notify
    from tientrivutru.models import Draw

    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    _store_stale_prize("power655", "01388")
    store.write_draws(
        "power655",
        [
            Draw(
                game="power655",
                draw_id=f"0{n}",
                date=date(2026, 9, 1),
                main=(2, 5, 28, 32, 51, 53),
                bonus=50,
                source="test",
            )
            for n in range(1388, 1397)
        ],
    )

    sent: list[str] = []
    monkeypatch.setattr(notify, "send_message", lambda text, **_k: sent.append(text) or True)
    monkeypatch.setattr(cli.notify, "send_message", lambda text, **_k: sent.append(text) or True)

    args = cli.build_parser().parse_args(["notify", "--kind", "result", "--game", "power655"])
    cli.cmd_notify(args)

    alerts = [m for m in sent if "Jackpot đứng im" in m]
    assert len(alerts) == 1
    assert "8 kỳ" in alerts[0]


def test_notify_stays_quiet_when_the_jackpot_is_current(monkeypatch):
    from tientrivutru import notify
    from tientrivutru.models import Draw

    monkeypatch.setenv(notify.ENV_TOKEN, "tok")
    monkeypatch.setenv(notify.ENV_CHAT_ID, "42")

    _store_stale_prize("power655", "01396")
    store.write_draws(
        "power655",
        [
            Draw(
                game="power655",
                draw_id="01396",
                date=date(2026, 9, 10),
                main=(2, 5, 28, 32, 51, 53),
                bonus=50,
                source="test",
            )
        ],
    )

    sent: list[str] = []
    monkeypatch.setattr(cli.notify, "send_message", lambda text, **_k: sent.append(text) or True)

    args = cli.build_parser().parse_args(["notify", "--kind", "result", "--game", "power655"])
    cli.cmd_notify(args)

    assert not [m for m in sent if "Jackpot đứng im" in m]


def test_today_names_a_stuck_jackpot(capsys):
    """`tientrivutru today` is what the Oracle workflow pipes into its step summary, so this
    is the line that makes an eighteen-day freeze visible in CI without having to drop
    the `|| true` that deliberately tolerates a lagging mirror."""
    from tientrivutru.models import Draw

    _store_stale_prize("power655", "01388")
    store.write_draws(
        "power655",
        [
            Draw(
                game="power655",
                draw_id=f"0{n}",
                date=date(2026, 9, 1),
                main=(2, 5, 28, 32, 51, 53),
                bonus=50,
                source="test",
            )
            for n in range(1388, 1397)
        ],
    )

    cli.cmd_today(cli.build_parser().parse_args(["today", "--game", "power655"]))

    assert "8 kỳ" in capsys.readouterr().out


def test_today_says_nothing_when_the_jackpot_is_current(capsys):
    from tientrivutru.models import Draw

    _store_stale_prize("power655", "01396")
    store.write_draws(
        "power655",
        [
            Draw(
                game="power655",
                draw_id="01396",
                date=date(2026, 9, 10),
                main=(2, 5, 28, 32, 51, 53),
                bonus=50,
                source="test",
            )
        ],
    )

    cli.cmd_today(cli.build_parser().parse_args(["today", "--game", "power655"]))

    assert "đang chậm" not in capsys.readouterr().out
