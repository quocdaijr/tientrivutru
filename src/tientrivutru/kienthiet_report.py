"""Terminal rendering for xổ số kiến thiết, kept out of cli.py so neither file sprawls.

Every function here takes data and prints it. None of them fetch, compute a prophecy, or
write to disk - that separation is what lets cli.py stay a dispatcher.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import kienthiet_prizes as prizes
from . import stats
from .kienthiet_oracle import VeProphecy
from .kienthiet_scoreboard import VeScore
from .sources import kienthiet as kt

TOP_N = 5


def render_stats(console: Console, region: str, boards: Sequence[kt.Board]) -> bool:
    """Chi-square over the 00-99 tail space. Returns True when data is missing."""
    spec = kt.REGIONS[region]
    if not boards:
        console.print(
            f"[red]chưa có data kiến thiết {spec.display} — chạy `tientrivutru ingest`[/red]"
        )
        return True

    result = kt.chi_square_uniform(boards)
    report = kt.summarise(boards)
    table = Table(
        title=f"Kiến thiết {spec.display} — {len(boards):,} bảng · {report['provinces']} đài",
        title_style="bold",
    )
    table.add_column("hạng mục")
    table.add_column("giá trị", justify="right")
    table.add_row("khoảng thời gian", f"{report['first_date']} → {report['last_date']}")
    table.add_row("lượt số quan sát", f"{result.observations:,}")
    table.add_row("không gian số", "00–99 (hai số cuối mỗi giải)")
    table.add_row("chi-square", f"{result.statistic:.3f}")
    table.add_row("bậc tự do", str(result.degrees_of_freedom))
    table.add_row("p-value", f"{result.p_value:.4f}")
    console.print(table)

    ranked = sorted(kt.frequency(boards).items(), key=lambda kv: (-kv[1], kv[0]))
    hot = ", ".join(f"{n:02d}({c:,})" for n, c in ranked[:TOP_N])
    cold = ", ".join(f"{n:02d}({c:,})" for n, c in ranked[-TOP_N:])
    console.print(f"  ra nhiều nhất: {hot}\n  ra ít nhất  : {cold}")
    console.print(Panel(stats.verdict(result), title="Phán quyết", border_style="yellow"))
    return False


def render_ve(console: Console, prophecy: VeProphecy) -> None:
    digits = " ".join(f"[bold cyan]{d}[/bold cyan]" for d in prophecy.ve)
    body = [digits, ""]
    body.extend(f"[dim]· {reason}[/dim]" for reason in prophecy.reasons)
    body.append("")
    body.append(f"[italic]{prophecy.sermon}[/italic]")
    console.print(
        Panel(
            "\n".join(body),
            title=f"{prophecy.display} — vé ngày {prophecy.draw_date}",
            subtitle=f"[dim]seed {prophecy.seed[:16]}… · {prizes.TICKET_PRICE_VND:,}đ[/dim]",
            border_style="magenta",
        )
    )


def render_score(console: Console, score: VeScore) -> None:
    if not score.tickets:
        console.print(f"[dim]{score.display}: chưa có vé nào được chấm[/dim]")
        return

    table = Table(title=f"Bảng Phong Thần vé số — {score.display}", title_style="bold")
    table.add_column("hạng mục")
    table.add_column("giá trị", justify="right")
    table.add_row("vé đã chấm", f"{score.tickets:,}")
    table.add_row("vé trúng gì đó", f"{score.winning_tickets:,}")
    table.add_row("tiền vé (giấy)", f"{score.paper_burned_vnd:,}đ")
    table.add_row("tiền trúng (giấy)", f"{score.paper_won_vnd:,}đ")
    table.add_row("ROI", f"{score.roi * 100:+.2f}%")
    table.add_row("ROI lý thuyết", f"{score.theoretical_roi * 100:+.2f}%")
    table.add_row("ROI bỏ ĐB & phụ ĐB", f"{score.roi_excluding_headline * 100:+.2f}%")
    table.add_row(
        "  lý thuyết", f"{score.theoretical_roi_excluding_headline * 100:+.2f}%"
    )
    console.print(table)

    if score.prize_counts_total:
        won = " · ".join(
            f"{prizes.BY_KEY[tier].display} ×{count:,}"
            for tier in (t.key for t in prizes.PRIZES)
            if (count := score.prize_counts_total.get(tier, 0))
        )
        console.print(f"  đã trúng: {won}")
    if score.best is not None and score.best.payout_vnd:
        best = score.best
        console.print(
            f"  vé đẹp nhất: [bold]{best.ve}[/bold] · "
            f"{kt.PROVINCES[best.province].display} {best.draw_date} · "
            f"ĐB {best.special} · {prizes.describe(best.prize_counts)} · "
            f"{best.payout_vnd:,}đ"
        )
    console.print(
        Panel(_verdict(score), title="Phán quyết", border_style="yellow")
    )


def _verdict(score: VeScore) -> str:
    """Say what the number means, including when it flatters the oracle."""
    if score.roi > score.theoretical_roi:
        return (
            f"ROI {score.roi * 100:+.2f}% đang cao hơn mức lý thuyết −50%. "
            "Đừng mừng: giải đặc biệt chiếm 40% quỹ giải, trúng một lần là cả bảng "
            f"lệch. Bỏ nó ra thì còn {score.roi_excluding_headline * 100:+.2f}%."
        )
    return (
        f"ROI {score.roi * 100:+.2f}%. Mức lý thuyết là −50,00% và nó không phải ước "
        "lượng — cơ cấu giải trả về đúng 5 tỷ trên 10 tỷ doanh thu mỗi đài mỗi kỳ. "
        "Thầy phán hay con tự bốc thì con số vẫn thế."
    )


def render_today(
    console: Console,
    region: str,
    boards: Sequence[kt.Board],
    day: date,
    committed: Sequence[VeProphecy],
) -> None:
    spec = kt.REGIONS[region]
    if not boards:
        console.print(f"[dim]Kiến thiết {spec.display}: chưa có data[/dim]")
        return

    latest = max(boards, key=lambda b: b.date)
    where = (
        f"{kt.PROVINCES[latest.province].display} "
        if len(kt.provinces_in(region)) > 1
        else ""
    )
    console.print(
        f"[bold]Kiến thiết {spec.display}[/bold] — bảng gần nhất {latest.date}: "
        f"{where}ĐB [bold]{latest.special}[/bold]"
    )

    today_dai = kt.dai_on(boards, day)
    if not today_dai:
        console.print("  [dim]hôm nay không có đài nào quay[/dim]")
        return
    names = ", ".join(kt.PROVINCES[slug].display for slug in today_dai)
    console.print(f"  đài hôm nay: [cyan]{names}[/cyan]")

    if not spec.prophesiable:
        console.print("  [dim]miền này không phán vé — chỉ Tầng Thật[/dim]")
        return

    by_province = {p.province: p for p in committed if p.draw_date == day}
    for slug in today_dai:
        prophecy = by_province.get(slug)
        if prophecy is None:
            console.print(f"    {kt.PROVINCES[slug].display}: [dim]chưa phán[/dim]")
        else:
            console.print(
                f"    {kt.PROVINCES[slug].display}: [bold cyan]{prophecy.ve}[/bold cyan]"
            )
