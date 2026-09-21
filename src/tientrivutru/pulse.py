"""Random pulses through the day: one small piece of the project, pushed to Telegram.

Two halves, kept apart on purpose.

*The schedule* is random but not unpredictable-to-itself. A day's firing hours come from
a seed derived from the date, so any process on any runner computes the same plan for
that day - which is what makes an hourly cron with no state file work, and what makes it
testable. `random.Random` seeded from sha256, never the global `random` and never
`hash()`, which is salted per process.

*The cards* are the content. Every builder returns `Card | None`, where None means "no
data for this today" - a fresh clone with no draws still has a moon and a birth date to
talk about, and must not raise on the way there.

Delivery is `notify.send_message`, unchanged: it swallows every failure and returns a
bool, so a dead Telegram cannot cost anything upstream.
"""

from __future__ import annotations

import hashlib
import os
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from . import kienthiet_scoreboard, stats, store, wheel
from .astrology import Fortune, read_fortune
from .games import GameSpec
from .kienthiet_scoreboard import VeScore
from .models import Draw, Prophecy
from .notify import DISCLAIMER, MAX_MESSAGE_CHARS, send_message
from .schedule import VN_TZ, next_target
from .scoreboard import GameScore
from .scoreboard import build as build_score
from .sources import kienthiet, markets
from .sources import xsmb as xsmb_source
from .sources.vibes import CosmicSignals, gather

FIRST_HOUR_VN = 8
LAST_HOUR_VN = 22
"""Inclusive: 22 is a legal slot, 23 is not."""
MIN_PER_DAY = 2
MAX_PER_DAY = 3

TOP_N = 5

ENV_BIRTH_DATE = "TIENTRIVUTRU_BIRTH_DATE"
ENV_GENDER = "TIENTRIVUTRU_GENDER"
ENV_NAME = "TIENTRIVUTRU_NAME"

MARKET_DISCLAIMER = (
    "Giá tham khảo, đọc từ nguồn công khai đúng lúc gửi tin. Không phải tư vấn đầu tư."
)
"""The lottery disclaimer says nothing true about a gold board, so the market cards carry
their own. A disclaimer that does not fit what it is attached to is decoration."""

MIN_BIRTH_YEAR = 1900
"""Anything earlier is a typo, not a person. The env var is untrusted input."""

PINNED_PLAN_2026_08_23 = (12, 20)
"""A regression pin for the seed recipe - see `tests/test_pulse.py`."""


class BirthDateError(ValueError):
    """A malformed `TIENTRIVUTRU_BIRTH_DATE`. Carries no copy of the offending value."""


# ------------------------------------------------------------------------ the schedule


def _seed_int(*parts: str) -> int:
    """A process-independent seed. sha256 for the same reason `oracle.make_seed` uses it."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def day_rng(day: date, *, salt: str = "") -> random.Random:
    """An RNG fixed to one day: the same day always yields the same decisions."""
    return random.Random(_seed_int("pulse", day.isoformat(), salt))


def bands_for(count: int) -> tuple[range, ...]:
    """The window cut into `count` equal bands, one pulse to a band."""
    span = LAST_HOUR_VN - FIRST_HOUR_VN + 1

    def edge(index: int) -> int:
        return FIRST_HOUR_VN + index * span // count

    return tuple(range(edge(index), edge(index + 1)) for index in range(count))


def slots_for(day: date) -> tuple[int, ...]:
    """The VN hours on `day` that get a pulse: one per band, uniform inside its band.

    Stratifying like this is what keeps the hours spread evenly over the window, and the
    obvious alternative does not. Sampling `count` hours and re-rolling until they are
    all >= 3h apart - or the closed-form equivalent, which is what this used to do - is
    uniform over *valid schedules*, not over hours, and an hour near the edge of the
    window sits in more valid schedules than one in the middle. Measured over 3650 days
    that made 08h and 22h come up 1.55x as often as 20h.

    A flat spread and a hard minimum gap are not both available in a fifteen-hour window
    with three pulses, so this keeps the spread: bands make the typical gap `span/count`
    hours and leave adjacent-band pairs able to land close, which happens on about 15% of
    days. Sorted and distinct still hold, by construction - the bands do not overlap.
    """
    rng = day_rng(day, salt="slots")
    count = rng.randint(MIN_PER_DAY, MAX_PER_DAY)
    return tuple(rng.choice(band) for band in bands_for(count))


def slot_index(now: datetime) -> int | None:
    """Which pulse of the day this is (0-based), or None outside the plan."""
    moment = now.astimezone(VN_TZ)
    slots = slots_for(moment.date())
    return slots.index(moment.hour) if moment.hour in slots else None


def should_fire(now: datetime) -> bool:
    return slot_index(now) is not None


# ----------------------------------------------------------------------------- content


@dataclass(frozen=True, slots=True)
class Card:
    """One thing worth saying.

    `key` is the kind, not the identity: four games each produce a `hot_cold`, so keys
    repeat inside one build. `day_order` uses that on purpose - it is the kind, not the
    game, that makes two pulses in a day feel like the same message twice.
    """

    key: str
    title: str
    lines: tuple[str, ...]
    disclaimer: str | None = None
    """Overrides the lottery disclaimer for cards that are not about the lottery."""


def _safe(value: str) -> str:
    """Escape free text for Telegram's HTML parser.

    `parse_mode=HTML` rejects the whole message on a bare `&` or `<`, and a rejected
    message is indistinguishable from a dead bot: `send_message` just returns False.
    The tags in this module are written by hand and stay literal; everything that comes
    from a corpus, a spec or an environment variable goes through here.
    """
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _numbers(pairs: Sequence[tuple[int, int]]) -> str:
    return ", ".join(f"<b>{n:02d}</b> ({c})" for n, c in pairs)


def _money(value: float) -> str:
    return f"{value:,.0f}đ"


def _billions(value: float) -> str:
    return f"{value / 1_000_000_000:,.2f} tỷ"


def card_hot_cold(spec: GameSpec, draws: Sequence[Draw]) -> Card | None:
    if not draws:
        return None
    return Card(
        key="hot_cold",
        title=f"📊 Nóng lạnh — {_safe(spec.display)}",
        lines=(
            f"Trên {len(draws):,} kỳ đã lưu:",
            f"ra nhiều nhất: {_numbers(stats.hottest(draws, spec, TOP_N))}",
            f"ra ít nhất: {_numbers(stats.coldest(draws, spec, TOP_N))}",
            "",
            "<i>Và đây là phần quan trọng: hai dòng trên không nói gì về kỳ tới. "
            "Quả cầu không có bộ nhớ.</i>",
        ),
    )


def card_chi_square(spec: GameSpec, draws: Sequence[Draw]) -> Card | None:
    if not draws:
        return None
    result = stats.chi_square_uniform(draws, spec)
    return Card(
        key="chi_square",
        title=f"🧪 Kiểm định đều — {_safe(spec.display)}",
        lines=(
            f"{len(draws):,} kỳ · {result.observations:,} lượt số",
            f"chi-square <b>{result.statistic:.2f}</b> · {result.degrees_of_freedom} bậc tự do",
            "",
            _safe(stats.verdict(result)),
        ),
    )


def card_gap(spec: GameSpec, draws: Sequence[Draw]) -> Card | None:
    if not draws:
        return None
    gaps = stats.gaps_since_last(draws, spec)
    ranked = sorted(gaps.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    return Card(
        key="gap",
        title=f"⏳ Lâu chưa thấy mặt — {_safe(spec.display)}",
        lines=(
            "Số kỳ đã trôi qua kể từ lần cuối mỗi số xuất hiện:",
            ", ".join(f"<b>{n:02d}</b> ({g} kỳ)" for n, g in ranked),
            "",
            "<i>Không có số nào 'đến hẹn'. Cái gọi là số gan chỉ là tên khác của "
            "ngẫu nhiên đã xảy ra rồi.</i>",
        ),
    )


def card_scoreboard(spec: GameSpec, score: GameScore) -> Card | None:
    if not score.draws_scored:
        return None
    delta = score.hits_per_draw_actual - score.hits_per_draw_expected
    verdict = "may hơn ngẫu nhiên 🍀" if delta > 0 else "tệ hơn cả ngẫu nhiên 💀"
    lines = [
        f"{score.draws_scored} kỳ đã chấm · trúng {score.hits_per_draw_actual:.2f}/kỳ "
        f"(ngẫu nhiên: {score.hits_per_draw_expected:.2f}) — {verdict}",
        f"đã đốt (giấy): {_money(score.paper_burned_vnd)}",
        f"thắng (giấy): {_money(score.paper_won_vnd)}",
        f"ROI <b>{score.roi * 100:.1f}%</b> · bỏ jackpot "
        f"<b>{score.roi_excluding_jackpot * 100:.1f}%</b>",
    ]
    if score.best_draw:
        lines.append(
            f"kỳ đỉnh nhất: #{score.best_draw.draw_id} — {score.best_draw.hits}/12 số"
        )
    return Card(
        key="scoreboard",
        title=f"📉 Bảng Phong Thần — {_safe(spec.display)}",
        lines=tuple(lines),
    )


def card_schedule(
    spec: GameSpec,
    draws: Sequence[Draw],
    prizes: Mapping[str, object] | None,
    *,
    now: datetime,
) -> Card | None:
    """Next draw, what a wheel costs, and what the jackpot is worth.

    Priced only for the Vietlott games: bao 12 is their product, and the US files carry
    no prize table to price against.
    """
    if not spec.wheel_playable or not draws:
        return None
    try:
        draw_id, draw_date = next_target(spec, draws, now=now)
    except RuntimeError:
        return None

    lines = [
        f"Kỳ tới: <b>#{draw_id}</b> ngày <b>{draw_date.strftime('%d/%m/%Y')}</b> lúc 18h00",
        f"Bao 12 = <b>{wheel.total_combinations(spec):,}</b> tổ hợp = "
        f"<b>{_money(wheel.wheel_cost_vnd(spec))}</b> cho một kỳ",
    ]
    if prizes and prizes.get("top_jackpot_vnd"):
        state = "cộng dồn sang kỳ sau" if prizes.get("rolled_over") else "đã có người trúng"
        quoted = str(prizes.get("draw_id"))
        lines.append(
            f"Jackpot kỳ #{quoted}: "
            f"<b>{_billions(float(prizes['top_jackpot_vnd']))}</b> — {state}"
        )
        # vietlott.vn answers a GitHub runner with 403, so this figure can freeze while
        # the results keep arriving from the mirror. A stale number that does not say it
        # is stale would be exactly the failure this project exists to refuse.
        latest = max(draws, key=lambda d: d.draw_id).draw_id
        if quoted != latest:
            lines.append(
                f"<i>⚠️ Số jackpot trên là của kỳ cũ (#{quoted}), "
                f"kết quả đã tới kỳ #{latest} — nguồn giải thưởng chưa cập nhật được.</i>"
            )
    lines += [
        "",
        f"<i>ROI kỳ vọng của cái bao đó: {wheel.expected_roi(spec) * 100:.1f}%. "
        "Âm. Luôn luôn âm.</i>",
    ]
    return Card(
        key="schedule",
        title=f"📅 Lịch và tiền — {_safe(spec.display)}",
        lines=tuple(lines),
    )


def card_xsmb(draws: Sequence[xsmb_source.XsmbDraw]) -> Card | None:
    if not draws:
        return None
    latest = max(draws, key=lambda d: d.date)
    ranked = sorted(xsmb_source.frequency(draws).items(), key=lambda kv: (-kv[1], kv[0]))
    report = xsmb_source.summarise(draws)
    return Card(
        key="xsmb",
        title="🎰 XSMB — hai chữ số cuối",
        lines=(
            f"Giải đặc biệt gần nhất ({latest.date.strftime('%d/%m/%Y')}): "
            f"<b>{latest.special:02d}</b>",
            f"{report['count']:,} kỳ · {report['observations']:,} lượt số trong không gian 00–99",
            f"ra nhiều nhất: {_numbers(ranked[:TOP_N])}",
            f"ra ít nhất: {_numbers(ranked[-TOP_N:])}",
        ),
    )


def card_gold(
    board: markets.GoldBoard | None,
    *,
    world_usd_per_oz: float | None = None,
    usd_vnd: float | None = None,
) -> Card | None:
    """The dealer's board, quoted per lượng - the unit people actually buy in.

    `markets` stores dong per chỉ because that is what PNJ publishes; every figure here
    is the per-lượng property, so the ×10 conversion happens in exactly one place and is
    pinned by `tests/test_markets.py` against two independent sources.

    The premium line appears only when an exchange rate is known. A premium computed off
    a guessed rate would be a plausible wrong number, which is the one thing this repo is
    not allowed to print.
    """
    if board is None or not board.quotes:
        return None

    lines = []
    for quote in board.quotes[:3]:
        lines.append(
            f"<b>{_safe(quote.label)}</b>\n"
            f"  mua {_money(quote.buy_vnd_per_luong)} · bán "
            f"<b>{_money(quote.sell_vnd_per_luong)}</b> /lượng"
        )
    top = board.quotes[0]
    lines += [
        "",
        f"Chênh mua–bán: <b>{_money(top.spread_vnd_per_luong)}</b>/lượng "
        f"(<b>{top.spread_pct:.2f}%</b>) — mất ngay lúc mua.",
    ]

    if world_usd_per_oz and usd_vnd:
        world = markets.world_gold_vnd_per_luong(world_usd_per_oz, usd_vnd=usd_vnd)
        premium = top.sell_vnd_per_luong - world
        lines.append(
            f"Vàng thế giới quy đổi: {_money(world)}/lượng — "
            f"trong nước đắt hơn <b>{_money(premium)}</b> "
            f"(<b>{premium / world * 100:+.1f}%</b>)."
        )

    if board.updated_at:
        lines.append(f"<i>Bảng giá lúc {_safe(board.updated_at)}"
                     + (f" · {_safe(board.branch)}" if board.branch else "")
                     + "</i>")
    return Card(
        key="gold",
        title="🪙 Giá vàng",
        lines=tuple(lines),
        disclaimer=MARKET_DISCLAIMER,
    )


def card_crypto(coins: Sequence[markets.CoinQuote]) -> Card | None:
    """Spot prices in both currencies. No opinion offered, because there isn't one."""
    if not coins:
        return None
    lines = []
    for coin in coins:
        move = (
            f" · 24h <b>{coin.change_24h_pct:+.2f}%</b>"
            if coin.change_24h_pct is not None
            else " · 24h chưa rõ"
        )
        lines.append(
            f"<b>{_safe(coin.symbol)}</b> ${coin.usd:,.2f} "
            f"({_money(coin.vnd)}){move}"
        )
    lines += [
        "",
        "<i>Giá spot, đọc lúc gửi tin. Cũng như mọi con số khác trong bot này: "
        "không nói gì về giá phút sau.</i>",
    ]
    return Card(
        key="crypto",
        title="₿ Giá crypto",
        lines=tuple(lines),
        disclaimer=MARKET_DISCLAIMER,
    )


def card_kienthiet(region: str, boards: Sequence[kienthiet.Board]) -> Card | None:
    """One region of xổ số kiến thiết, in the 00-99 tail space XSMB already lives in."""
    if not boards:
        return None
    spec = kienthiet.REGIONS[region]
    latest = max(boards, key=lambda b: b.date)
    ranked = sorted(kienthiet.frequency(boards).items(), key=lambda kv: (-kv[1], kv[0]))
    report = kienthiet.summarise(boards)
    # Miền Bắc is one đài, so naming it would just repeat the card title back.
    where = (
        f"Đài gần nhất: <b>{kienthiet.PROVINCES[latest.province].display}</b> "
        if len(kienthiet.provinces_in(region)) > 1
        else "Kỳ gần nhất: "
    )
    return Card(
        key=f"kienthiet_{region}",
        title=f"🎟️ Kiến thiết {spec.display} — hai chữ số cuối",
        lines=(
            f"{where}({latest.date.strftime('%d/%m/%Y')}) ĐB <b>{latest.special}</b>",
            f"{report['count']:,} bảng · {report['provinces']} đài · "
            f"{report['observations']:,} lượt số trong không gian 00–99",
            f"ra nhiều nhất: {_numbers(ranked[:TOP_N])}",
            f"ra ít nhất: {_numbers(ranked[-TOP_N:])}",
        ),
    )


def card_ve(score: VeScore) -> Card | None:
    """The vé Hall of Shame. Its headline number is arithmetic, not a sample."""
    if not score.tickets:
        return None
    return Card(
        key="ve",
        title="🎫 Thầy phán vé số — mỗi đài một vé",
        lines=(
            f"{score.tickets:,} vé đã chấm · trúng gì đó: <b>{score.winning_tickets:,}</b>",
            f"tiền vé: {score.paper_burned_vnd:,}đ · trúng: {score.paper_won_vnd:,}đ",
            f"ROI: <b>{score.roi * 100:+.2f}%</b> "
            f"(bỏ ĐB &amp; phụ ĐB: {score.roi_excluding_headline * 100:+.2f}%)",
            f"ROI lý thuyết: <b>{score.theoretical_roi * 100:+.2f}%</b> — "
            "cơ cấu giải trả về đúng 5 tỷ trên 10 tỷ doanh thu mỗi đài mỗi kỳ.",
            "",
            "<i>Thầy phán hay con tự bốc thì con số vẫn thế.</i>",
        ),
    )


def card_vibes(signals: CosmicSignals, *, day: date) -> Card | None:
    """The one card that always exists: the moon needs no network."""
    lines = [f"Hôm nay {day.strftime('%d/%m/%Y')}:"]
    if signals.lunar_day and signals.lunar_month:
        lines.append(
            f"âm lịch <b>{signals.lunar_day}/{signals.lunar_month}</b>"
            + (f" · ngày <b>{_safe(signals.day_can_chi)}</b>" if signals.day_can_chi else "")
            + (f" · năm <b>{_safe(signals.zodiac)}</b>" if signals.zodiac else "")
        )
    if signals.btc_usd is not None:
        lines.append(f"Bitcoin <b>${signals.btc_usd:,}</b>")
    if signals.hanoi_temp_c is not None:
        lines.append(f"Hà Nội <b>{signals.hanoi_temp_c}°C</b>")
    if signals.xsmb_special is not None:
        lines.append(f"XSMB đặc biệt gần nhất <b>{signals.xsmb_special:02d}</b>")
    if signals.silent_count:
        lines.append(f"<i>{signals.silent_count} tín hiệu im lặng hôm nay.</i>")
    if len(lines) == 1:
        return None
    lines += [
        "",
        "<i>Giá trị tiên đoán của mọi con số trên: đúng bằng không. "
        "Chúng chỉ dùng để gieo hạt cho oracle.</i>",
    ]
    return Card(key="vibes", title="🌙 Vũ trụ hôm nay", lines=tuple(lines))


def card_sermon(spec: GameSpec, prophecy: Prophecy | None, rng: random.Random) -> Card | None:
    """One line of the pending prophecy's sermon, picked at random.

    A record written before sermons existed has none - the same gap that used to crash
    `format_prophecy` - so an empty sermon means no card, not a KeyError.
    """
    if prophecy is None:
        return None
    spoken = [(n, prophecy.sermon[str(n)]) for n in prophecy.numbers if prophecy.sermon.get(str(n))]
    if not spoken:
        return None
    number, sermon = rng.choice(spoken)
    return Card(
        key="sermon",
        title=f"🔮 Lời sấm — {_safe(spec.display)} kỳ #{prophecy.draw_id}",
        lines=(
            f"<b>{number:02d}</b> — <i>{_safe(sermon)}</i>",
            "",
            f"Một trong 12 số đã cam kết cho kỳ ngày "
            f"{prophecy.draw_date.strftime('%d/%m/%Y')}. "
            "Ghi trước, không sửa được, để sau này còn có cái mà cười.",
        ),
    )


def card_fortune(fortune: Fortune | None, *, day: date) -> Card | None:
    """The personal layer. Derived values only - the birth date itself never appears."""
    if fortune is None:
        return None
    lines = [
        f"Bản mệnh: <b>{_safe(fortune.can_chi)}</b> · {_safe(fortune.nap_am)} "
        f"(mệnh <b>{_safe(fortune.element)}</b>) · {_safe(fortune.western_sign)}",
        f"Số chủ đạo: <b>{fortune.life_path}</b>"
        + (f" · số tên: <b>{fortune.name_number}</b>" if fortune.name_number else ""),
    ]
    if fortune.guardian_star:
        lines.append(f"Sao chiếu mệnh năm nay: <b>{_safe(fortune.guardian_star)}</b>")
    if fortune.tam_hop:
        lines.append(f"Tam hợp: {', '.join(fortune.tam_hop)}")
    if fortune.tu_hanh_xung:
        lines.append(f"Tứ hành xung: {', '.join(fortune.tu_hanh_xung)}")
    lines += [
        "",
        "<i>Suy ra từ ngày sinh, và ngày sinh không nằm ở đâu trong repo này. "
        "Độ chính xác tiên đoán: vẫn bằng không.</i>",
    ]
    return Card(key="fortune", title="🪷 Lá số của anh", lines=tuple(lines))


# ------------------------------------------------------------------- the personal layer


def read_birth_date(*, today: date) -> date | None:
    """`TIENTRIVUTRU_BIRTH_DATE` as a date, or None when the variable is not set.

    Raises `BirthDateError` when a value is present but unusable - this is a system
    boundary and a silent None here would look identical to "not configured". The
    message never quotes the value: this runs in GitHub Actions, whose logs are public.
    """
    raw = os.environ.get(ENV_BIRTH_DATE, "").strip()
    if not raw:
        return None
    try:
        birth = date.fromisoformat(raw)
    except ValueError:
        raise BirthDateError(f"{ENV_BIRTH_DATE} không đúng dạng YYYY-MM-DD") from None
    if birth.year < MIN_BIRTH_YEAR:
        raise BirthDateError(f"{ENV_BIRTH_DATE} sớm hơn năm {MIN_BIRTH_YEAR} — chắc là gõ sai")
    if birth > today:
        raise BirthDateError(f"{ENV_BIRTH_DATE} nằm ở tương lai")
    return birth


def read_fortune_from_env(today: date) -> Fortune | None:
    """The fortune for the configured birth date, or None when none is configured.

    Propagates `BirthDateError` so the caller can say which variable is wrong; the CLI
    turns that into a warning and carries on with one card fewer.
    """
    birth = read_birth_date(today=today)
    if birth is None:
        return None
    return read_fortune(
        birth,
        name=os.environ.get(ENV_NAME) or None,
        gender=os.environ.get(ENV_GENDER) or None,
        today=today,
    )


# ------------------------------------------------------------------------ assembling


def build_cards(
    specs: Sequence[GameSpec],
    *,
    now: datetime,
    fortune: Fortune | None = None,
    allow_network: bool = True,
) -> tuple[Card, ...]:
    """Every card that can be built right now. Absent data means an absent card.

    Reads the store directly, the way the `cmd_*` handlers do, so the CLI stays a thin
    shell over this.
    """
    day = now.astimezone(VN_TZ).date()
    rng = day_rng(day, salt="cards")
    xsmb_draws = store.read_xsmb()
    prophecies = store.read_prophecies()

    cards: list[Card | None] = []
    for spec in specs:
        draws = store.read_draws(spec.key)
        cards += [
            card_hot_cold(spec, draws),
            card_chi_square(spec, draws),
            card_gap(spec, draws),
            card_schedule(spec, draws, store.read_prizes(spec.key), now=now),
        ]
        if spec.wheel_playable:
            mine = [p for p in prophecies if p.game == spec.key]
            settled = {d.draw_id for d in draws}
            pending = [p for p in mine if p.draw_id not in settled]
            cards += [
                card_scoreboard(spec, build_score(spec, mine, draws)),
                card_sermon(spec, pending[0] if pending else None, rng),
            ]

    signals = gather(
        day,
        allow_network=allow_network,
        xsmb_special=xsmb_source.latest_special(xsmb_draws),
    )
    board = markets.fetch_gold_board() if allow_network else None
    coins = markets.fetch_coins() if allow_network else ()
    world = markets.fetch_world_gold_usd_per_oz() if allow_network else None

    tickets = store.read_ve()
    kien_thiet_boards = []
    for region in kienthiet.REGIONS:
        boards = store.read_boards(region)
        kien_thiet_boards += boards
        cards.append(card_kienthiet(region, boards))

    cards += [
        card_xsmb(xsmb_draws),
        card_ve(kienthiet_scoreboard.build(tickets, kien_thiet_boards)),
        card_vibes(signals, day=day),
        card_gold(board, world_usd_per_oz=world, usd_vnd=markets.implied_usd_vnd(coins)),
        card_crypto(coins),
        card_fortune(fortune, day=day),
    ]
    return tuple(card for card in cards if card is not None)


def day_order(cards: Sequence[Card], day: date) -> tuple[Card, ...]:
    """The day's running order: shuffled, then one card per kind pulled to the front.

    Shuffling alone is not enough. Four games produce four `hot_cold` cards, so a
    plain shuffle lands two of them in the same day about as often as not, and reads
    as the bot repeating itself. Fronting the first card of each distinct kind means
    the first `len(set(keys))` pulses of a day are all different kinds; the remainder
    keeps the shuffled order so nothing is ever unreachable.
    """
    order = list(cards)
    day_rng(day, salt="order").shuffle(order)
    seen: set[str] = set()
    first_of_kind, rest = [], []
    for card in order:
        target = rest if card.key in seen else first_of_kind
        target.append(card)
        seen.add(card.key)
    return tuple(first_of_kind + rest)


def card_for_slot(cards: Sequence[Card], day: date, index: int) -> Card | None:
    """The card for pulse number `index` of `day`. Wraps if asked past the end."""
    if not cards:
        return None
    order = day_order(cards, day)
    return order[index % len(order)]


def format_card(card: Card, *, now: datetime) -> str:
    """The Telegram message. HTML, disclaimed, and inside the API's length limit."""
    moment = now.astimezone(VN_TZ)
    body = "\n".join(
        (
            f"<b>{card.title}</b>",
            f"<i>{moment.strftime('%H:%M')} giờ VN</i>",
            "",
            *card.lines,
            "",
            f"<i>{card.disclaimer or DISCLAIMER}</i>",
        )
    )
    return body[:MAX_MESSAGE_CHARS]


def send_card(card: Card, *, now: datetime) -> bool:
    """Deliver one card. False on any failure, exactly like `notify.send_message`."""
    return send_message(format_card(card, now=now))
