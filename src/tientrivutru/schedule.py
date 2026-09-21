"""When things happen, in Vietnam time.

Split out of `cli` so both the terminal and the Telegram pulse can ask "which draw is
next?" without importing each other. It sits above `games` and `models` and below
everything that talks to a human.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from .games import GameSpec, draw_days_between, next_draw_date
from .models import Draw, normalise_draw_id

VN_TZ = timezone(timedelta(hours=7))
DRAW_HOUR_VN = 18


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def today_vn() -> date:
    return now_vn().date()


def draw_has_happened(day: date, now: datetime | None = None) -> bool:
    now = now or now_vn()
    return day < now.date() or (day == now.date() and now.hour >= DRAW_HOUR_VN)


def next_target(
    spec: GameSpec, draws: Sequence[Draw], *, now: datetime | None = None
) -> tuple[str, date]:
    """Work out which draw to prophesy for, and its id.

    The id is derived by counting the draw days between the last stored draw and the
    target, so an upstream mirror that skipped a draw does not cause the oracle to
    prophesy a draw that already happened.
    """
    if not draws:
        raise RuntimeError(f"no {spec.key} history stored - run `tientrivutru ingest` first")

    now = now or now_vn()
    target = next_draw_date(spec, now.date(), inclusive=True)
    if draw_has_happened(target, now):
        target = next_draw_date(spec, target + timedelta(days=1), inclusive=True)

    last = max(draws, key=lambda d: d.draw_id)
    intervening = draw_days_between(spec, last.date + timedelta(days=1), target)
    # Must be normalised: stored draw_ids are zero-padded, so an unpadded id here
    # silently fails every `==` lookup against saved prophecies and draws.
    return normalise_draw_id(int(last.draw_id) + len(intervening)), target
