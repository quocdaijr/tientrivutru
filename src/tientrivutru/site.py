"""Builds the single JSON bundle the static site reads.

Why a bundle instead of fetching data/ directly: GitHub Pages serves one directory, and
the raw history is megabytes of JSONL the browser has no use for. This writes exactly
what the page renders - and nothing else - next to the HTML, so the site is
self-contained and loads in one request.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import astrology, kienthiet_scoreboard, prize_health, scoreboard, stats, store, tax, wheel
from .games import PROPHECY_GAMES, GameSpec
from .kienthiet_oracle import VeProphecy
from .models import Draw, Prophecy, utc_now
from .sources import kienthiet

SITE_DIR = Path(__file__).resolve().parents[2] / "site"
BUNDLE_NAME = "data.json"
RECENT_DRAWS = 12
TOP_N = 8
# Starts a year before the earliest supported birth year: someone born in January
# before Tết belongs to the PREVIOUS lunar year, so that year's row must exist too.
EARLIEST_BIRTH_YEAR = 1930
LUNAR_TABLE_START = EARLIEST_BIRTH_YEAR - 1
LUNAR_TABLE_END = 2035

DISCLAIMER = (
    "Xổ số là biến cố độc lập. Mỗi kỳ quay reset về 0. Không có số nóng, không có số "
    "lạnh. Phần mềm này không dự đoán được gì — nó chỉ tự tin quá mức và tự chấm điểm "
    "độ sai của chính mình. Bảng Phong Thần là paper-trading: tiền đốt trên giấy."
)


def _prizes_payload(spec: GameSpec, draws: Sequence[Draw]) -> dict[str, Any] | None:
    """The stored jackpot, tagged with whether it still describes the newest draw.

    `matches_latest_draw` is the whole point of this function. If the prize fetch failed
    on the last run, the stored figure belongs to an older draw - and a jackpot labelled
    as current when it is not would be exactly the kind of number this project refuses to
    print. The renderer must read this flag before it words anything.

    `draws_behind` is the part a boolean cannot carry. One draw behind is a single failed
    run; eight is what the 2026-08-25 Cloudflare block actually produced. The freshness
    judgement comes from `prize_health` rather than being recomputed here, so the page and
    the ingest log can never disagree about whether the number has gone stale.
    """
    stored = store.read_prizes(spec.key)
    if not stored:
        return None
    latest_id = draws[-1].draw_id if draws else None
    fresh = prize_health.freshness(stored, latest_id)
    top = int(stored.get("top_jackpot_vnd") or 0)
    return {
        **stored,
        "matches_latest_draw": fresh.matches_latest_draw,
        "draws_behind": fresh.draws_behind,
        "is_stale": fresh.is_stale,
        "latest_draw_id": latest_id,
        # The announced figure is not what a winner receives. Printing one without the
        # other is the shape of an advert, and this page is not one.
        "top_jackpot_tax_vnd": tax.withheld_vnd(top),
        "top_jackpot_take_home_vnd": tax.take_home_vnd(top),
    }


def _payout_if_hit(
    spec: GameSpec, prizes: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    """What a bao-12 ticket actually pays for each possible number of hits.

    This is the question a jackpot figure makes people ask - "so what do I get if it
    comes in tonight?" - and unlike the next draw's estimated pot, it is fully derivable:
    `wheel.prize_counts` already knows how many of the 924 tickets win each tier when k
    of the twelve are drawn, and the prize values are the real ones off the page.

    The jackpot used is the scraped figure when we have it, the published floor when we
    do not, and `uses_live_jackpot` says which. Falling back silently would understate
    the pot by more than half, which is as dishonest as overstating it.

    The bonus number is deliberately left out: including it would double every row, and
    for Power it only changes the five-hit case. The page says so in words instead.
    """
    live = None
    if prizes and prizes.get("jackpots"):
        live = {
            label.lower().replace(" ", ""): value
            for label, value in prizes["jackpots"].items()
        }
        if set(live) - set(spec.jackpot_floor):
            live = None  # figures from a different game's page; refuse rather than guess

    cost = wheel.wheel_cost_vnd(spec)
    rows: list[dict[str, Any]] = []
    for k in range(spec.pick + 1):
        counts = wheel.prize_counts(spec, k)
        # Only the rows that actually reach a jackpot tier are priced off the live figure;
        # the lower rows are the same either way, and flagging them would overstate what
        # the scrape contributed.
        wins_jackpot = counts.get("jackpot", counts.get("jackpot1", 0)) > 0
        paid = wheel.payout_vnd(spec, counts, jackpots=live)
        probability = wheel.hit_probability(spec, k)
        rows.append(
            {
                "hits": k,
                "probability": round(probability, 9),
                "one_in": round(1 / probability) if probability else None,
                "counts": {tier: n for tier, n in counts.items() if n},
                "payout_vnd": paid,
                "net_vnd": paid - cost,
                "uses_live_jackpot": bool(live) and wins_jackpot,
            }
        )
    return rows


def _payout_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The four facts the page actually shows, derived from the rows it no longer draws.

    The full seven-row table was cut on request - for a joke about a jackpot, a ledger of
    small prizes is noise. But a jackpot figure with only its odds beside it reads exactly
    like a lottery advert, so what stays is the counterweight: how often the wheel pays
    nothing at all, and how rarely it clears its own stake.

    Derived from the same rows rather than recomputed, because a summary that drifts from
    the table it summarises is worse than no summary, and this is where that would hide.
    """
    nothing = sum(r["probability"] for r in rows if r["payout_vnd"] == 0)
    profit = sum(r["probability"] for r in rows if r["net_vnd"] > 0)
    return {
        "nothing_probability": round(nothing, 9),
        "profit_probability": round(profit, 9),
        "profit_one_in": round(1 / profit) if profit else None,
        # Read off the row, never recomputed from the rounded probability beside it. At
        # 3.19e-5 the nine-decimal rounding is enough to move 1-in-31,374 to 31,375, and a
        # figure that is wrong by one is still a figure that is wrong.
        "jackpot_one_in": rows[-1]["one_in"] if rows else None,
    }


def _game_payload(
    spec: GameSpec,
    draws: Sequence[Draw],
    prophecies: Sequence[Prophecy],
    score: scoreboard.GameScore,
) -> dict[str, Any]:
    chi = stats.chi_square_uniform(draws, spec) if draws else None
    frequencies = stats.frequency(draws, spec) if draws else {}
    settled = {d.draw_id for d in draws}
    pending = [p for p in prophecies if p.game == spec.key and p.draw_id not in settled]
    prizes = _prizes_payload(spec, draws)
    payout_rows = _payout_if_hit(spec, prizes)

    return {
        "key": spec.key,
        "display": spec.display,
        "pool": spec.pool,
        "pick": spec.pick,
        "has_bonus": spec.has_bonus,
        "wheel": {
            "combinations": wheel.total_combinations(spec),
            "cost_vnd": wheel.wheel_cost_vnd(spec),
            "expected_roi": round(wheel.expected_roi(spec), 6),
            "expected_roi_excluding_jackpot": round(
                wheel.expected_roi(spec, include_jackpot=False), 6
            ),
        },
        "draw_count": len(draws),
        "latest": draws[-1].to_dict() if draws else None,
        "recent": [d.to_dict() for d in draws[-RECENT_DRAWS:]],
        "frequency": {str(n): c for n, c in frequencies.items()},
        "chi_square": (
            {
                "statistic": round(chi.statistic, 3),
                "degrees_of_freedom": chi.degrees_of_freedom,
                "p_value": round(chi.p_value, 4),
                "observations": chi.observations,
                "rejects_uniform": chi.rejects_uniform,
                "verdict": stats.verdict(chi),
            }
            if chi
            else None
        ),
        "pending_prophecy": pending[0].to_dict() if pending else None,
        "score": score.to_dict(),
        "prizes": prizes,
        "payout_if_hit": payout_rows,
        "payout_summary": _payout_summary(payout_rows),
    }


def _chi_payload(chi: stats.ChiSquareResult) -> dict[str, Any]:
    return {
        "statistic": round(chi.statistic, 3),
        "degrees_of_freedom": chi.degrees_of_freedom,
        "p_value": round(chi.p_value, 4),
        "observations": chi.observations,
        "rejects_uniform": chi.rejects_uniform,
        "verdict": stats.verdict(chi),
    }


def _kienthiet_payload(
    region: str, boards: Sequence[kienthiet.Board], tickets: Sequence[VeProphecy]
) -> dict[str, Any] | None:
    """One region of xổ số kiến thiết: the honest layer, plus its vé if it has one.

    The value space is the 00-99 tail of every prize slot, exactly as XSMB's was, so the
    page's existing 10x10 heatmap renders this unchanged.
    """
    if not boards:
        return None
    spec = kienthiet.REGIONS[region]
    report = kienthiet.summarise(boards)
    latest = max(boards, key=lambda b: b.date)
    payload: dict[str, Any] = {
        "region": region,
        "display": f"Kiến thiết {spec.display}",
        "draw_count": len(boards),
        "provinces": report["provinces"],
        "first_date": report["first_date"],
        "last_date": report["last_date"],
        "prophesiable": spec.prophesiable,
        "latest": {
            "date": latest.date.isoformat(),
            "province": kienthiet.PROVINCES[latest.province].display,
            "special": latest.special,
        },
        "frequency": {f"{n:02d}": c for n, c in kienthiet.frequency(boards).items()},
        "chi_square": _chi_payload(kienthiet.chi_square_uniform(boards)),
    }
    if spec.prophesiable:
        payload["ve"] = kienthiet_scoreboard.build(tickets, boards, region=region).to_dict()
    return payload


def _astrology_payload() -> dict[str, Any]:
    """Every constant and table the browser needs to read a fortune.

    The browser gets DATA, not a second implementation: the lunar algorithm, the
    sexagenary cycle and the nạp âm table are all resolved here in Python and shipped
    as a lookup, so a birth date can be placed in its lunar year with one date
    comparison. That keeps the two sides from drifting apart, and keeps the birth date
    itself on the device.
    """
    table = astrology.lunar_year_table(LUNAR_TABLE_START, LUNAR_TABLE_END)
    return {
        "lunar_years": {str(year): entry for year, entry in table.items()},
        "zodiac_bounds": [
            {"month": month, "day": day, "name": name}
            for month, day, name in astrology.ZODIAC_BOUNDS
        ],
        "stars_male": list(astrology.STARS_MALE),
        "stars_female": list(astrology.STARS_FEMALE),
        "star_base_age": astrology.STAR_BASE_AGE,
        "tam_hop": [list(group) for group in astrology.TAM_HOP],
        "tu_hanh_xung": [list(group) for group in astrology.TU_HANH_XUNG],
        "pythagorean_rows": list(astrology.PYTHAGOREAN_ROWS),
        "master_numbers": list(astrology.MASTER_NUMBERS),
        "elements": list(astrology.ELEMENTS),
    }


def build_bundle() -> dict[str, Any]:
    """Assemble everything the page needs from stored data."""
    prophecies = store.read_prophecies()
    games = []
    for spec in PROPHECY_GAMES.values():
        draws = store.read_draws(spec.key)
        score = scoreboard.build(spec, prophecies, draws)
        games.append(_game_payload(spec, draws, prophecies, score))

    tickets = store.read_ve()
    kien_thiet = [
        payload
        for region in kienthiet.REGIONS
        if (payload := _kienthiet_payload(region, store.read_boards(region), tickets))
    ]

    return {
        "generated_at": utc_now().isoformat(),
        "disclaimer": DISCLAIMER,
        "games": games,
        "kienthiet": kien_thiet,
        "top_n": TOP_N,
        "astrology": _astrology_payload(),
        "privacy": (
            "Ngày sinh, tên và giới tính chỉ nằm trong trình duyệt của bạn "
            "(localStorage). Không có server, không có tài khoản, không request nào "
            "mang dữ liệu đó đi. Xoá lúc nào cũng được."
        ),
    }


def write_bundle(bundle: Mapping[str, Any], *, site_dir: Path | None = None) -> Path:
    """Write the bundle, skipping the write when only the timestamp would change."""
    target = (site_dir or SITE_DIR) / BUNDLE_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    store.write_json_if_changed(target, dict(bundle), indent=1)
    return target
