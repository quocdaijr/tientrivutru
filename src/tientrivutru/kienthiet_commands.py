"""The `tientrivutru` subcommands for xổ số kiến thiết, lifted out of cli.py.

Adding a third lottery family pushed cli.py past the size where it still read as a
dispatcher, so the kiến thiết half lives here. Each function takes the console it prints
to rather than making its own, so the CLI keeps exactly one.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import requests
from rich.console import Console

from . import kienthiet_ingest as ingest
from . import kienthiet_report as report
from . import kienthiet_scoreboard as scoreboard
from . import notify, store
from .kienthiet_oracle import latest_special_before
from .kienthiet_oracle import prophesy as prophesy_ve
from .schedule import today_vn
from .sources import kienthiet
from .sources.vibes import gather
from .store import ProphecyConflict

RECENT_DAYS = 21
"""How far back a routine ingest looks: three weekly pages, enough to catch a late đài."""


def regions(region: str | None) -> tuple[str, ...]:
    """Resolve which kiến thiết regions a command acts on. None means all three."""
    if region:
        if region not in kienthiet.REGIONS:
            raise SystemExit(
                f"Không có miền {region!r}. Chọn: {', '.join(sorted(kienthiet.REGIONS))}"
            )
        return (region,)
    return tuple(kienthiet.REGIONS)


def prophesiable(region: str | None) -> tuple[str, ...]:
    """Regions that can be phán. Miền Bắc is deliberately not one of them."""
    return tuple(r for r in regions(region) if kienthiet.REGIONS[r].prophesiable)


def _ingest_start(args: argparse.Namespace, region: str) -> date:
    """Where this run starts. --backfill goes to the region's first recorded draw."""
    if args.since:
        return date.fromisoformat(args.since)
    if args.backfill:
        return kienthiet.ARCHIVE_START[region]
    return today_vn() - timedelta(days=RECENT_DAYS)


def run_ingest(console: Console, args: argparse.Namespace) -> int:
    """Ingest xổ số kiến thiết. Returns how many regions ended with a problem."""
    problems = 0
    end = today_vn()
    session = requests.Session()
    for region in regions(args.region):
        spec = kienthiet.REGIONS[region]
        start = _ingest_start(args, region)
        console.print(
            f"[bold]Kiến thiết {spec.display}[/bold] — {start} → {end} "
            f"(trang tuần, {ingest.DEFAULT_PAUSE_SECONDS}s/lần)…"
        )
        outcome = ingest.ingest_region(
            region,
            start=start,
            end=end,
            session=session,
            on_week=(lambda r: _render_week(console, r)) if args.backfill else None,
        )
        console.print(
            f"  bảng mới: [green]{outcome.added:,}[/green] · tổng: [bold]{outcome.total:,}[/bold]"
            f" · tuần đã tải: {outcome.requested_weeks} · bỏ qua: {outcome.skipped_weeks}"
        )
        for failure in outcome.failures:
            problems += 1
            console.print(f"  [red]tuần {failure.anchor} thất bại:[/red] {failure.error}")

        if outcome.no_draw:
            days = sorted({day for day, _ in outcome.no_draw})
            console.print(
                f"  [dim]{len(days)} ngày đài không quay (Tết) — bỏ qua, không lưu[/dim]"
            )
        gaps = ingest.missing_days(
            region, start=start, end=end, known_no_draw={d for d, _ in outcome.no_draw}
        )
        if gaps:
            shown = ", ".join(d.isoformat() for d in gaps[:8])
            more = f" (+{len(gaps) - 8} ngày nữa)" if len(gaps) > 8 else ""
            console.print(f"  [yellow]ngày thiếu đài:[/yellow] {shown}{more}")
    return problems


def _render_week(console: Console, result: ingest.WeekResult) -> None:
    if result.error:
        console.print(f"  [red]{result.anchor}[/red] {result.error}")
    else:
        console.print(f"  [dim]tuần đến {result.anchor} · {result.fetched} bảng[/dim]")


def run_oracle(console: Console, args: argparse.Namespace, *, offline: bool) -> None:
    """Commit one vé for each đài drawing today.

    Only today's đài, never next week's: committing a week of tickets in one run would
    leave the next six runs with nothing to do and every đài prophesied from a single
    day's signals.
    """
    today = today_vn()
    for region in prophesiable(args.region):
        boards = store.read_boards(region)
        if not boards:
            console.print(f"[dim]kiến thiết {region}: chưa có data — bỏ qua[/dim]")
            continue
        drawing = [
            slug
            for slug in kienthiet.dai_on(boards, today)
            if kienthiet.next_draw_date(boards, slug, on=today) == today
        ]
        if not drawing:
            console.print(
                f"[dim]kiến thiết {kienthiet.REGIONS[region].display}: "
                "hôm nay không đài nào chờ phán[/dim]"
            )
            continue
        signals = gather(today, allow_network=not offline)
        for province in drawing:
            karma = latest_special_before(boards, province, today)
            prophecy = prophesy_ve(province, today, signals, karma=karma)
            report.render_ve(console, prophecy)
            if args.dry_run:
                console.print("  [dim](dry-run — không ghi vào ve.jsonl)[/dim]")
                continue
            try:
                store.append_ve(prophecy)
                console.print("  [green]đã ghi vào ve.jsonl[/green]")
            except ProphecyConflict as exc:
                console.print(f"  [yellow]bỏ qua:[/yellow] {exc}")


def run_score(console: Console, args: argparse.Namespace) -> None:
    """Settle every committed vé that now has a board, and write its own scoreboard."""
    tickets = store.read_ve()
    boards = [b for region in prophesiable(args.region) for b in store.read_boards(region)]
    scores = scoreboard.build_all(tickets, boards)
    for key in sorted(scores):
        report.render_score(console, scores[key])
    store.write_ve_scoreboard(scoreboard.as_json(scores))
    console.print(f"[dim]đã ghi {store.ve_scoreboard_path()}[/dim]")


def run_backtest(console: Console, args: argparse.Namespace) -> None:
    """Replay one vé per đài per kỳ across the whole archive. Never written to disk."""
    for region in prophesiable(args.region):
        boards = store.read_boards(region)
        if not boards:
            console.print(f"[dim]kiến thiết {region}: chưa có data[/dim]")
            continue
        start = max(0, len(boards) - args.limit) if args.limit else 0
        window = boards[start:]
        console.print(
            f"[bold]Kiến thiết {kienthiet.REGIONS[region].display}[/bold] — "
            f"backtest {len(window):,} bảng…"
        )

        # Karma is the đài's own previous đặc biệt, carried forward per đài as the replay
        # walks history - the same numbers as a lookup, without the quadratic scan.
        karma: dict[str, str] = {}
        signals_by_day: dict[date, object] = {}
        prophecies = []
        for index, board in enumerate(boards):
            if index >= start:
                if board.date not in signals_by_day:
                    signals_by_day[board.date] = gather(board.date, allow_network=False)
                prophecies.append(
                    prophesy_ve(
                        board.province,
                        board.date,
                        signals_by_day[board.date],
                        karma=karma.get(board.province),
                    )
                )
            karma[board.province] = board.special

        report.render_score(
            console, scoreboard.build(prophecies, window, region=region)
        )


def run_notify(console: Console, args: argparse.Namespace) -> tuple[int, int]:
    """One kiến thiết message per run: every đài of the day in a single card."""
    tickets = store.read_ve()
    boards = [b for region in prophesiable(args.region) for b in store.read_boards(region)]
    score = scoreboard.build(tickets, boards)

    if args.kind == "prophecy":
        settled = {b.key for b in boards}
        pending = [t for t in tickets if t.key not in settled]
        if not pending:
            console.print("[dim]kiến thiết: không có vé nào đang chờ[/dim]")
            return 0, 0
        day = max(t.draw_date for t in pending)
        message = notify.format_ve_prophecy(
            sorted((t for t in pending if t.draw_date == day), key=lambda t: t.province), score
        )
    else:
        rows = scoreboard.score_rows(tickets, boards)
        if not rows:
            console.print("[dim]kiến thiết: chưa có vé nào chấm được[/dim]")
            return 0, 0
        day = max(r.draw_date for r in rows)
        message = notify.format_ve_result([r for r in rows if r.draw_date == day], score)

    if notify.send_message(message):
        console.print("[green]kiến thiết: đã gửi Telegram[/green]")
        return 1, 0
    console.print("[red]kiến thiết: gửi Telegram thất bại[/red]")
    return 0, 1
