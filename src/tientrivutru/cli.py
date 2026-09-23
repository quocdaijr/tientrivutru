"""Terminal interface. Every command prints the disclaimer, no exceptions."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date, datetime, timedelta

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import (
    hoi_dong,
    kienthiet_commands,
    kienthiet_report,
    notify,
    prize_health,
    pulse,
    scoreboard,
    site,
    stats,
    store,
    wheel,
)
from .games import GAMES, PROPHECY_GAMES, GameSpec, get_game
from .models import Draw, Prophecy, utc_now
from .oracle import prophesy
from .schedule import VN_TZ, draw_has_happened, next_target, now_vn, today_vn
from .sources import kienthiet, us_lottery, vietlott_live, vietlott_prizes, xsmb
from .sources import vietlott_mirror as mirror
from .sources.vibes import gather
from .sources.vietlott_live import LiveFetchError
from .sources.vietlott_prizes import PrizeParseError
from .store import ProphecyConflict

DISCLAIMER = (
    "[dim]Xổ số là biến cố độc lập. Phần mềm này không dự đoán được gì. "
    "Bảng Phong Thần là paper-trading — đốt tiền trên giấy.[/dim]"
)

console = Console()


def _specs(game: str | None, *, prophecy_only: bool = False) -> tuple[GameSpec, ...]:
    """Resolve the games a command should act on.

    `prophecy_only` filters out the US games: bao 12 is a Vietlott product, so
    prophecies, wheels and scoreboards simply do not apply to them.
    """
    available = PROPHECY_GAMES if prophecy_only else GAMES
    if game:
        spec = get_game(game)
        if prophecy_only and not spec.wheel_playable:
            raise SystemExit(
                f"{spec.display} không đánh bao 12 được — game này chỉ dùng để thống kê. "
                f"Chọn một trong: {', '.join(sorted(PROPHECY_GAMES))}"
            )
        return (spec,)
    return tuple(available.values())


def _games_for(args: argparse.Namespace, *, prophecy_only: bool = False) -> tuple[GameSpec, ...]:
    """The Vietlott/US games a command acts on.

    `--region` names a kiến thiết miền, so it means that miền and nothing else - asking
    for `--region mn` must not also drag four ball-draw games through the command.
    """
    if getattr(args, "region", None):
        return ()
    return _specs(args.game, prophecy_only=prophecy_only)


def _fetch_for(spec: GameSpec) -> tuple[Draw, ...]:
    """Route a game to the source module that owns its upstream."""
    if spec.wheel_playable:
        return mirror.fetch_draws(spec)
    return us_lottery.fetch_draws(spec)


def _try_live_fallback(spec: GameSpec, missing: Sequence[str]) -> bool:
    """Patch a lagging mirror from vietlott.vn. Returns True if a gap remains.

    Only the newest draw is available live, so this closes the common case (mirror one
    draw behind) and reports honestly when it cannot close the rest.
    """
    try:
        live = vietlott_live.fetch_latest(spec)
    except (LiveFetchError, requests.RequestException) as exc:
        console.print(f"  [red]dự phòng vietlott.vn thất bại:[/red] {exc}")
        return True

    if live.date.isoformat() not in missing:
        console.print(
            f"  [dim]dự phòng: trang chính thức đang ở kỳ #{live.draw_id} "
            f"({live.date}) — không vá được ngày còn thiếu[/dim]"
        )
        return True

    added, _ = store.merge_draws(spec.key, [live])
    if added:
        console.print(
            f"  [green]đã vá từ vietlott.vn:[/green] kỳ #{live.draw_id} ({live.date}) "
            f"→ {' '.join(f'{n:02d}' for n in live.main)}"
            + (f" | phụ {live.bonus:02d}" if live.bonus is not None else "")
        )
    remaining = [d for d in missing if d != live.date.isoformat()]
    if remaining:
        console.print(f"  [yellow]vẫn thiếu:[/yellow] {', '.join(remaining)}")
    return bool(remaining)


def _refresh_prizes(spec: GameSpec, latest_draw_id: str) -> bool:
    """Read the jackpot for the newest draw and store it. Returns whether it is stuck.

    Never fatal. The prize figures are commentary on the draw, not part of it, so a
    layout change on vietlott.vn must not take the whole ingest down - it reports, keeps
    whatever was stored last, and the site labels that figure with the draw it belongs to
    so a stale number can never pass itself off as the current one.

    But not fatal is not the same as not worth mentioning, and that distinction cost
    eighteen days. From 2026-08-25 vietlott.vn answered the GitHub Actions runner with a
    Cloudflare managed challenge; this function caught the 403 exactly as designed,
    printed one yellow line and returned - and every run stayed green while the figure
    sat still. So a failed fetch now asks how far behind the stored number actually is,
    and a real gap comes back as a problem the caller must account for.
    """
    try:
        prizes = vietlott_prizes.fetch_prizes(spec, latest_draw_id)
    except (PrizeParseError, LiveFetchError, requests.RequestException) as exc:
        console.print(f"  [yellow]không đọc được giải thưởng:[/yellow] {exc}")
        fresh = prize_health.freshness(store.read_prizes(spec.key), latest_draw_id)
        if not fresh.is_stale:
            return False
        console.print(f"  [red]{prize_health.describe(fresh)}[/red]")
        return True

    changed = store.write_prizes(prizes)
    billions = prizes.top_jackpot_vnd / 1_000_000_000
    state = "cộng dồn sang kỳ sau" if prizes.rolled_over else "đã có người trúng"
    console.print(
        f"  jackpot kỳ #{prizes.draw_id}: [bold]{billions:,.2f} tỷ[/bold] — {state}"
        + ("" if changed else " [dim](không đổi)[/dim]")
    )
    return False


def _money(value: float) -> str:
    return f"{value:,.0f}đ"


def cmd_ingest(args: argparse.Namespace) -> int:
    today = today_vn()
    problems = 0
    # --region asks for kiến thiết alone; --game asks for one Vietlott/US game alone;
    # neither flag means everything.
    for spec in _games_for(args):
        console.print(f"[bold]{spec.display}[/bold] — tải từ mirror…")
        draws = _fetch_for(spec)
        added, total = store.merge_draws(spec.key, draws)
        stored = store.read_draws(spec.key)
        report = mirror.summarise(spec, stored, today)

        console.print(f"  kỳ mới: [green]{added}[/green] · tổng: [bold]{total}[/bold]")
        console.print(f"  mới nhất: #{report['last_id']} ngày {report['last_date']}")

        # Jackpot lives on the same vietlott.vn page as the draw, and only for Vietlott
        # games - the US files carry no prize pool we can read.
        if spec.wheel_playable and report["last_id"]:
            problems += _refresh_prizes(spec, report["last_id"])

        # Gap and lag checks assume a Vietlott draw calendar and a real draw number.
        # The US files carry neither, so applying them there would invent problems.
        if args.check_gaps and spec.wheel_playable:
            if report["gap_ids"]:
                problems += 1
                console.print(f"  [red]thiếu kỳ (gap id):[/red] {', '.join(report['gap_ids'])}")
            missing = [
                d
                for d in report["missing_draw_dates"]
                if draw_has_happened(date.fromisoformat(d))
            ]
            if missing:
                console.print(
                    "  [yellow]upstream lag — ngày quay chưa có data:[/yellow] "
                    f"{', '.join(missing)}"
                )
                if _try_live_fallback(spec, missing):
                    problems += 1
            if not report["gap_ids"] and not missing:
                console.print("  [green]không gap, không lag[/green]")

    if args.game is None:
        problems += kienthiet_commands.run_ingest(console, args)

    console.print(DISCLAIMER)
    return 1 if problems else 0


def cmd_stats(args: argparse.Namespace) -> int:
    missing_data = False
    for spec in _games_for(args):
        draws = store.read_draws(spec.key)
        if not draws:
            console.print(f"[red]chưa có data {spec.key} — chạy `tientrivutru ingest`[/red]")
            missing_data = True
            continue

        result = stats.chi_square_uniform(draws, spec)
        table = Table(title=f"{spec.display} — {len(draws)} kỳ", title_style="bold")
        table.add_column("hạng mục")
        table.add_column("giá trị", justify="right")
        table.add_row("số kỳ", f"{len(draws):,}")
        table.add_row("lượt số quan sát", f"{result.observations:,}")
        table.add_row("chi-square", f"{result.statistic:.3f}")
        table.add_row("bậc tự do", str(result.degrees_of_freedom))
        table.add_row("p-value", f"{result.p_value:.4f}")
        console.print(table)

        hot = ", ".join(f"{n}({c})" for n, c in stats.hottest(draws, spec))
        cold = ", ".join(f"{n}({c})" for n, c in stats.coldest(draws, spec))
        console.print(f'  ra nhiều nhất: {hot}\n  ra ít nhất  : {cold}')
        console.print(Panel(stats.verdict(result), title="Phán quyết", border_style="yellow"))

    if args.game is None:
        missing_data |= _render_xsmb_stats()
        for region in kienthiet_commands.regions(args.region):
            missing_data |= kienthiet_report.render_stats(
                console, region, store.read_boards(region)
            )

    console.print(DISCLAIMER)
    return 1 if missing_data else 0


def _render_xsmb_stats() -> bool:
    """XSMB gets its own renderer because it is not a pick-N game.

    Returns True when data is missing, matching cmd_stats' contract.
    """
    draws = store.read_xsmb()
    if not draws:
        console.print("[red]chưa có data XSMB — chạy `tientrivutru ingest`[/red]")
        return True

    result = xsmb.chi_square_uniform(draws)
    report = xsmb.summarise(draws)
    table = Table(title=f"XSMB Miền Bắc — {len(draws):,} kỳ", title_style="bold")
    table.add_column("hạng mục")
    table.add_column("giá trị", justify="right")
    table.add_row("khoảng thời gian", f"{report['first_date']} → {report['last_date']}")
    table.add_row("lượt số quan sát", f"{result.observations:,}")
    table.add_row("không gian số", "00–99 (100 giá trị)")
    table.add_row("chi-square", f"{result.statistic:.3f}")
    table.add_row("bậc tự do", str(result.degrees_of_freedom))
    table.add_row("p-value", f"{result.p_value:.4f}")
    console.print(table)

    ranked = sorted(xsmb.frequency(draws).items(), key=lambda kv: (-kv[1], kv[0]))
    hot = ", ".join(f"{n:02d}({c})" for n, c in ranked[:5])
    cold = ", ".join(f"{n:02d}({c})" for n, c in ranked[-5:])
    console.print(f"  ra nhiều nhất: {hot}\n  ra ít nhất  : {cold}")
    console.print(Panel(stats.verdict(result), title="Phán quyết", border_style="yellow"))
    return False


def _render_prophecy(spec: GameSpec, prophecy: Prophecy) -> None:
    numbers = "  ".join(f"[bold cyan]{n:02d}[/bold cyan]" for n in prophecy.numbers)
    console.print(
        Panel(
            numbers,
            title=f"{spec.display} — kỳ #{prophecy.draw_id} ngày {prophecy.draw_date}",
            subtitle=f"bao 12 = {wheel.total_combinations(spec)} tổ hợp = "
            f"{_money(wheel.wheel_cost_vnd(spec))}",
            border_style="cyan",
        )
    )
    for n in prophecy.numbers:
        sermon = prophecy.sermon.get(str(n))
        if sermon:
            console.print(f"  [cyan]{n:02d}[/cyan] — [italic]{sermon}[/italic]")
    console.print(f"  [dim]seed {prophecy.seed[:16]}… · oracle v{prophecy.oracle_version}[/dim]")


def cmd_oracle(args: argparse.Namespace) -> int:
    xsmb_special = store.latest_xsmb_special()
    for spec in _games_for(args, prophecy_only=True):
        draws = store.read_draws(spec.key)
        try:
            draw_id, draw_date = next_target(spec, draws)
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
        if args.draw_id:
            draw_id = args.draw_id

        signals = gather(
            draw_date, allow_network=not args.offline, xsmb_special=xsmb_special
        )
        prophecy = prophesy(spec, draw_id, draw_date, signals, draws)
        _render_prophecy(spec, prophecy)

        if signals.silent_count:
            console.print(f"  [dim]{signals.silent_count} tín hiệu im lặng hôm nay[/dim]")

        if args.dry_run:
            console.print("  [dim](dry-run — không ghi vào predictions.jsonl)[/dim]")
        else:
            try:
                store.append_prophecy(prophecy)
                console.print("  [green]đã ghi vào predictions.jsonl[/green]")
            except ProphecyConflict as exc:
                console.print(f"  [yellow]bỏ qua:[/yellow] {exc}")

    if args.game is None:
        kienthiet_commands.run_oracle(console, args, offline=args.offline)

    console.print(DISCLAIMER)
    return 0


def _render_score(score: scoreboard.GameScore) -> None:
    if not score.draws_scored:
        console.print(f"[dim]{score.display}: chưa có kỳ nào để chấm[/dim]")
        return

    delta = score.hits_per_draw_actual - score.hits_per_draw_expected
    verdict = "may hơn ngẫu nhiên 🍀" if delta > 0 else "tệ hơn cả ngẫu nhiên 💀"

    table = Table(title=f"Bảng Phong Thần — {score.display}", title_style="bold red")
    table.add_column("hạng mục")
    table.add_column("giá trị", justify="right")
    table.add_row("số kỳ đã chấm", f"{score.draws_scored:,}")
    table.add_row("trúng / kỳ (thực tế)", f"{score.hits_per_draw_actual:.3f}")
    table.add_row("trúng / kỳ (ngẫu nhiên)", f"{score.hits_per_draw_expected:.3f}")
    table.add_row("chênh lệch", f"{delta:+.3f} — {verdict}")
    table.add_row("đã đốt (giấy)", _money(score.paper_burned_vnd))
    table.add_row("thắng (giấy)", _money(score.paper_won_vnd))
    roi_colour = "green" if score.roi > 0 else "red"
    table.add_row("ROI", f"[bold {roi_colour}]{score.roi * 100:.2f}%[/bold {roi_colour}]")
    table.add_row(
        "ROI (bỏ jackpot)",
        f"[bold red]{score.roi_excluding_jackpot * 100:.2f}%[/bold red]",
    )
    if score.best_draw:
        table.add_row("kỳ đỉnh nhất", f"#{score.best_draw.draw_id} — {score.best_draw.hits}/12 số")
    if score.jackpot_hits:
        table.add_row("jackpot", f"[bold green]{score.jackpot_hits}[/bold green] 🎉")
    console.print(table)

    if score.jackpot_hits and score.roi > 0:
        console.print(
            Panel(
                f"ROI dương [bold]chỉ nhờ {score.jackpot_hits} kỳ trúng jackpot[/bold]. "
                f"Bỏ jackpot ra thì ROI là {score.roi_excluding_jackpot * 100:.2f}%, "
                f"và tỉ lệ trúng {score.hits_per_draw_actual:.3f} vẫn đúng bằng mức ngẫu nhiên "
                f"{score.hits_per_draw_expected:.3f}.\n"
                "Đây chính là cách mọi 'hệ thống đánh xổ số' tự lừa mình: một cú may "
                "che hết phần còn lại.",
                title="⚠️ Đừng để một kỳ may mắn kể chuyện thay dữ liệu",
                border_style="yellow",
            )
        )


def cmd_score(args: argparse.Namespace) -> int:
    prophecies = store.read_prophecies()
    draws_by_game = {
        spec.key: store.read_draws(spec.key)
        for spec in _games_for(args, prophecy_only=True)
    }
    scores = scoreboard.build_all(prophecies, draws_by_game)

    for score in scores.values():
        _render_score(score)
    if scores:
        store.write_scoreboard(scoreboard.as_json(scores))
        console.print(f"[dim]đã ghi {store.scoreboard_path()}[/dim]")

    if args.game is None:
        kienthiet_commands.run_score(console, args)

    console.print(DISCLAIMER)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    """Replay the oracle over history. Counterfactual - never written to disk."""
    for spec in _games_for(args, prophecy_only=True):
        draws = store.read_draws(spec.key)
        if not draws:
            console.print(f"[red]chưa có data {spec.key} — chạy `tientrivutru ingest`[/red]")
            return 1

        start = max(1, len(draws) - args.limit) if args.limit else 0
        window = draws[start:]
        console.print(f"[bold]{spec.display}[/bold] — backtest {len(window)} kỳ…")

        # Use the XSMB special from the day before each historical draw, so the
        # replay sees the signal the oracle would actually have seen back then.
        xsmb_by_date = {d.date: d.special for d in store.read_xsmb()}

        prophecies = []
        for index, draw in enumerate(window, start=start):
            signals = gather(
                draw.date,
                allow_network=False,
                xsmb_special=xsmb_by_date.get(draw.date - timedelta(days=1)),
            )
            prophecies.append(prophesy(spec, draw.draw_id, draw.date, signals, draws[:index]))

        _render_score(scoreboard.build(spec, prophecies, window))
        console.print(
            f"  [dim]ROI kỳ vọng lý thuyết: {wheel.expected_roi(spec) * 100:.2f}% "
            f"(bỏ jackpot: {wheel.expected_roi(spec, include_jackpot=False) * 100:.2f}%)[/dim]"
        )
    if args.game is None:
        kienthiet_commands.run_backtest(console, args)

    console.print("[dim]Backtest là phản thực — không phải tiên tri đã cam kết.[/dim]")
    console.print(DISCLAIMER)
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    now = now_vn()
    console.print(f"[bold]Hôm nay {now.date()} ({now.strftime('%H:%M')} giờ VN)[/bold]\n")

    for spec in _games_for(args, prophecy_only=True):
        draws = store.read_draws(spec.key)
        if not draws:
            console.print(f"[dim]{spec.display}: chưa có data[/dim]")
            continue
        draw_id, draw_date = next_target(spec, draws)
        last = max(draws, key=lambda d: d.draw_id)
        console.print(
            f"[bold]{spec.display}[/bold] — kỳ gần nhất #{last.draw_id} ({last.date}): "
            f"{' '.join(f'{n:02d}' for n in last.main)}"
            + (f" | phụ {last.bonus:02d}" if last.bonus is not None else "")
        )
        console.print(f"  kỳ tới: [cyan]#{draw_id}[/cyan] ngày [cyan]{draw_date}[/cyan] lúc 18h00")

        pending = [p for p in store.read_prophecies(spec.key) if p.draw_id == draw_id]
        if pending:
            picks = " ".join(f"{n:02d}" for n in pending[0].numbers)
            console.print(f"  đã tiên tri: [bold cyan]{picks}[/bold cyan]")
        else:
            console.print("  [dim]chưa tiên tri — chạy `tientrivutru oracle`[/dim]")

        # The Oracle workflow pipes this command into its step summary, which is the one
        # place a frozen jackpot becomes visible in CI without dropping the `|| true`
        # that deliberately tolerates a lagging mirror.
        if spec.wheel_playable:
            fresh = prize_health.freshness(store.read_prizes(spec.key), last.draw_id)
            if fresh.is_stale:
                console.print(f"  [red]{prize_health.describe(fresh)}[/red]")

    if args.game is None:
        console.print()
        committed = store.read_ve()
        for region in kienthiet_commands.regions(args.region):
            kienthiet_report.render_today(
                console, region, store.read_boards(region), now.date(), committed
            )
    console.print()
    console.print(DISCLAIMER)
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    """Write the JSON bundle the static page reads."""
    bundle = site.build_bundle()
    target = site.write_bundle(bundle)
    games = ", ".join(g["display"] for g in bundle["games"])
    kien_thiet = ", ".join(k["display"] for k in bundle["kienthiet"])
    console.print(f"[green]đã ghi[/green] {target}")
    console.print(f"  game: {games}")
    console.print(f"  kiến thiết: {kien_thiet or '—'}")
    console.print(f"  [dim]xem thử: python3 -m http.server -d {target.parent} 8000[/dim]")
    console.print(DISCLAIMER)
    return 0


def _stale_prizes(
    args: argparse.Namespace,
) -> tuple[tuple[GameSpec, prize_health.PrizeFreshness], ...]:
    """The Vietlott games whose stored jackpot has stopped tracking the newest draw.

    Computed independently of whether there was a prophecy or a result to announce: the
    2026-08-25 outage would have gone unheard on any day with nothing else to send.
    """
    stale = []
    for spec in _games_for(args, prophecy_only=True):
        if not spec.wheel_playable:
            continue
        draws = store.read_draws(spec.key)
        latest_id = draws[-1].draw_id if draws else None
        fresh = prize_health.freshness(store.read_prizes(spec.key), latest_id)
        if fresh.is_stale:
            stale.append((spec, fresh))
    return tuple(stale)


def cmd_notify(args: argparse.Namespace) -> int:
    """Push prophecies or results to Telegram.

    Exits non-zero only when Telegram is misconfigured or a send fails, and the
    workflow calls it in a way that cannot fail the data pipeline.
    """
    try:
        notify.require_config()
    except notify.TelegramNotConfigured as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    prophecies = store.read_prophecies()
    sent = failed = 0

    for spec in _games_for(args, prophecy_only=True):
        draws = store.read_draws(spec.key)
        score = scoreboard.build(spec, prophecies, draws)

        if args.kind == "prophecy":
            pending = notify.pending_prophecies(
                [p for p in prophecies if p.game == spec.key], draws
            )
            if not pending:
                console.print(f"[dim]{spec.display}: không có tiên tri nào đang chờ[/dim]")
                continue
            message = notify.format_prophecy(spec, pending[0], score)
        else:
            rows = scoreboard.score_rows(spec, prophecies, draws)
            if not rows:
                console.print(f"[dim]{spec.display}: chưa có kỳ nào chấm được[/dim]")
                continue
            latest = rows[-1]
            draw = next(d for d in draws if d.draw_id == latest.draw_id)
            message = notify.format_result(spec, draw, latest, score)

        if notify.send_message(message):
            sent += 1
            console.print(f"[green]{spec.display}: đã gửi Telegram[/green]")
        else:
            failed += 1
            console.print(f"[red]{spec.display}: gửi Telegram thất bại[/red]")

    # One alert per run, not one per game: the point is to break the silence, not to
    # fill it. It goes out even on a day with no prophecy and no result to announce.
    stale = _stale_prizes(args)
    if stale:
        if notify.send_message(notify.format_prize_alert(stale)):
            sent += 1
            console.print("[yellow]đã báo Telegram: jackpot đứng im[/yellow]")
        else:
            failed += 1
            console.print("[red]gửi cảnh báo jackpot thất bại[/red]")

    if args.game is None:
        ok, bad = kienthiet_commands.run_notify(console, args)
        sent += ok
        failed += bad

    console.print(f"[dim]gửi được {sent}, thất bại {failed}[/dim]")
    console.print(DISCLAIMER)
    return 1 if failed else 0


def _parse_now(raw: str | None) -> datetime:
    """`--now` for testing a specific hour. A naive value is read as Vietnam time."""
    if not raw:
        return now_vn()
    moment = datetime.fromisoformat(raw)
    return moment if moment.tzinfo else moment.replace(tzinfo=VN_TZ)


def cmd_pulse(args: argparse.Namespace) -> int:
    """Push one random card at a randomly-chosen hour of the day.

    Called hourly by `pulse.yml` and exits 0 without sending on the hours that are not
    in today's plan, so the cron can stay dumb and stateless.
    """
    now = _parse_now(args.now)
    day = now.astimezone(VN_TZ).date()
    plan = ", ".join(f"{hour:02d}h" for hour in pulse.slots_for(day))

    if args.plan:
        console.print(f"Kế hoạch {day}: [cyan]{plan}[/cyan]")
        console.print(DISCLAIMER)
        return 0

    index = pulse.slot_index(now)
    if index is None and not args.force:
        console.print(f"[dim]giờ này không có tin (kế hoạch hôm nay: {plan})[/dim]")
        console.print(DISCLAIMER)
        return 0

    # A dry run is a local preview, so it must not demand anybody's bot token.
    if not args.dry_run:
        try:
            notify.require_config()
        except notify.TelegramNotConfigured as exc:
            console.print(f"[red]{exc}[/red]")
            return 1

    # A typo in one secret costs one card, not the whole pulse - and the warning names
    # the variable without echoing it, because Actions logs are public.
    fortune = None
    try:
        fortune = pulse.read_fortune_from_env(day)
    except pulse.BirthDateError as exc:
        console.print(f"[yellow]bỏ qua lá số:[/yellow] {exc}")

    cards = pulse.build_cards(
        _games_for(args),
        now=now,
        fortune=fortune,
        allow_network=not args.offline,
    )
    # `--force` off-plan has no slot number; the hour stands in for one so that forcing
    # at different times previews different cards instead of the same one all day.
    card = pulse.card_for_slot(cards, day, index if index is not None else now.hour)
    if card is None:
        console.print("[yellow]không dựng được thẻ nào — chạy `tientrivutru ingest` trước[/yellow]")
        console.print(DISCLAIMER)
        return 0

    # List the kinds, not just the count. A price source that answers a laptop with 200
    # and a datacenter IP with 403 - which is what vietlott.vn does - shows up here as a
    # missing kind, and there is no other way to see it from an Actions log.
    kinds = " ".join(sorted({c.key for c in cards}))
    console.print(f"[dim]{len(cards)} thẻ ({kinds}) · chọn[/dim] [bold]{card.key}[/bold]")
    if args.dry_run:
        console.print(Panel(pulse.format_card(card, now=now), border_style="cyan"))
        console.print(DISCLAIMER)
        return 0

    if pulse.send_card(card, now=now):
        console.print(f"[green]đã gửi Telegram:[/green] {card.key}")
        console.print(DISCLAIMER)
        return 0

    console.print(f"[red]gửi Telegram thất bại:[/red] {card.key}")
    console.print(DISCLAIMER)
    return 1


def cmd_council(args: argparse.Namespace) -> int:
    """One sitting of the Council for every asset that is due today.

    Refuses outright - exit 2, nothing spent - unless the model, its looked-up price and a
    monthly cap are all set. A day that cannot be afforded is still written, as skipped_budget,
    so the page can say the Council stopped rather than silently going quiet. Exit 1 if any
    sitting failed: its row is still written (the tokens were bought), and the workflow commits
    it before going red.
    """
    import os
    from dataclasses import replace

    from .hoi_dong_run import council_settings, run_verdict

    now = utc_now()
    model, cap, problems = council_settings(os.environ, now.date())
    if problems:
        for problem in problems:
            console.print(f"[red]không họp:[/red] {problem}")
        return 2

    verdicts = list(store.read_verdicts())
    month = now.strftime("%Y-%m")
    due = hoi_dong.due_assets(verdicts, now)
    if not due:
        console.print("Hôm nay không có mã nào đến lượt Hội đồng họp.")
        return 0

    failed = 0
    for asset in due:
        day = hoi_dong.local_date(asset, now)
        if hoi_dong.can_afford(verdicts, cap, model.deep, month):
            verdict = run_verdict(asset, day, model=model)
        else:
            verdict = hoi_dong.Verdict(asset=asset.key, trade_date=day, committed_at=utc_now(),
                                       status="skipped_budget", model=model.as_dict(),
                                       usage={"cost_usd": 0.0})
        verdict = replace(verdict, usage={**(verdict.usage or {}), "cap_usd": cap})
        store.append_verdict(verdict)
        verdicts.append(verdict)
        failed += verdict.status == "failed"
        console.print(
            f"{asset.key:8s} {day}  {verdict.status:15s} {verdict.rating or '—':12s} "
            f"${verdict.cost_usd:.4f}"
        )
    console.print(
        f"Tháng {month}: đã đốt ${hoi_dong.month_spend(verdicts, month):.4f} / trần ${cap:.2f}."
    )
    console.print(DISCLAIMER)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tientrivutru", description="Máy tiên tri xổ số tự vả mặt. Không dự đoán được gì."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str, handler) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--game", choices=sorted(GAMES), help="chỉ một game (mặc định: cả hai)")
        p.add_argument(
            "--region",
            choices=sorted(kienthiet.REGIONS),
            help="chỉ một miền kiến thiết (mặc định: cả ba)",
        )
        p.set_defaults(handler=handler)
        return p

    ingest = add("ingest", "tải kết quả từ mirror về data/draws/", cmd_ingest)
    ingest.add_argument("--check-gaps", action="store_true", help="báo gap và lag upstream")
    ingest.add_argument(
        "--backfill", action="store_true", help="kéo toàn bộ lịch sử kiến thiết (chậm)"
    )
    ingest.add_argument("--since", help="kiến thiết: ngày bắt đầu (YYYY-MM-DD)")

    add("stats", "Tầng Thật: tần suất, chi-square, phán quyết", cmd_stats)

    oracle_cmd = add("oracle", "Tầng Tà Đạo: 12 số cho kỳ tới", cmd_oracle)
    oracle_cmd.add_argument("--draw-id", help="ghi đè kỳ mục tiêu")
    oracle_cmd.add_argument("--dry-run", action="store_true", help="in ra, không ghi file")
    oracle_cmd.add_argument("--offline", action="store_true", help="bỏ tín hiệu cần mạng")

    add("score", "dựng lại Bảng Phong Thần", cmd_score)

    backtest = add("backtest", "tiên tri lại lịch sử (phản thực)", cmd_backtest)
    backtest.add_argument("--limit", type=int, default=0, help="chỉ N kỳ gần nhất")

    add("today", "dashboard kỳ quay tới", cmd_today)

    add("site", "sinh site/data.json cho trang tĩnh", cmd_site)

    add("council", "Hội đồng TradingAgents họp một phiên cho các mã đến lượt", cmd_council)

    notify_cmd = add("notify", "đẩy tiên tri / kết quả lên Telegram", cmd_notify)
    notify_cmd.add_argument(
        "--kind",
        choices=("prophecy", "result"),
        default="prophecy",
        help="prophecy = 12 số trước kỳ quay · result = kết quả sau kỳ quay",
    )

    pulse_cmd = add("pulse", "tin random trong ngày lên Telegram", cmd_pulse)
    pulse_cmd.add_argument(
        "--plan", action="store_true", help="chỉ in các giờ đã chọn cho hôm nay"
    )
    pulse_cmd.add_argument("--force", action="store_true", help="gửi bất kể giờ nào")
    pulse_cmd.add_argument("--dry-run", action="store_true", help="in tin ra, không gửi")
    pulse_cmd.add_argument("--offline", action="store_true", help="bỏ tín hiệu cần mạng")
    pulse_cmd.add_argument("--now", help="ghi đè thời điểm (ISO 8601, mặc định giờ VN)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
