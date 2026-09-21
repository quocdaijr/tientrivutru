"""How far behind the stored jackpot is, and whether that deserves an alarm.

Separate from `sources.vietlott_prizes` on purpose. That module answers "what does the
page say"; this one answers "is what we last managed to read still worth printing". They
fail for unrelated reasons and the parser must not grow a second job.

Why this exists at all: on 2026-08-25 vietlott.vn began answering GitHub Actions runners
with a Cloudflare managed challenge. `_refresh_prizes` caught the 403 exactly as it was
built to, kept the last figure, printed one yellow line - and the run went green. The
number then sat still for eighteen days. The site never claimed it was current, but
nothing ever said it had stopped moving either, which is its own kind of dishonesty.

The judgement encoded here is a threshold, not a boolean. One missed draw is a transient:
a single failed run between two draws, and shouting about it would teach the reader to
ignore the alert that matters. Two or more is a source that has gone away.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Mega 6/45 and Power 6/55 each draw three times a week, so two draws behind is roughly
# four days of consecutive failures - past any plausible transient.
STALE_AFTER_DRAWS = 1


@dataclass(frozen=True, slots=True)
class PrizeFreshness:
    """The distance between the stored jackpot and the newest draw on file.

    `draws_behind` is None when the distance cannot be known - nothing stored, or an id
    that will not parse. That is deliberately not zero: an unknown gap is the worst
    state, not the best one, and `is_stale` says so.
    """

    stored_draw_id: str | None
    latest_draw_id: str | None
    draws_behind: int | None

    @property
    def matches_latest_draw(self) -> bool:
        """True only when the stored figure describes the newest draw on file."""
        return self.draws_behind == 0

    @property
    def is_stale(self) -> bool:
        if self.latest_draw_id is None:
            # Nothing has been ingested yet, so there is nothing to be behind.
            return False
        if self.draws_behind is None:
            return True
        return self.draws_behind > STALE_AFTER_DRAWS


def _as_number(raw: Any) -> int | None:
    """Draw ids are zero-padded digit strings; anything else is unusable, not zero."""
    text = str(raw).strip() if raw is not None else ""
    return int(text) if text.isdigit() else None


def freshness(
    stored: Mapping[str, Any] | None, latest_draw_id: str | None
) -> PrizeFreshness:
    """Compare the stored prize figures against the newest draw on file."""
    stored_id = stored.get("draw_id") if stored else None
    stored_n = _as_number(stored_id)
    latest_n = _as_number(latest_draw_id)

    # `max` rather than a plain subtraction because being ahead is not being behind:
    # vietlott.vn has been observed publishing a draw before the mirror did, and
    # negative staleness is not a thing.
    behind = (
        None if stored_n is None or latest_n is None else max(0, latest_n - stored_n)
    )

    return PrizeFreshness(
        stored_draw_id=str(stored_id) if stored_id is not None else None,
        latest_draw_id=latest_draw_id,
        draws_behind=behind,
    )


def describe(fresh: PrizeFreshness) -> str:
    """One Vietnamese line stating the gap, for a terminal, a message or a log."""
    if fresh.draws_behind is None:
        return f"jackpot: chưa đọc được lần nào (kỳ mới nhất #{fresh.latest_draw_id})"
    if fresh.draws_behind == 0:
        return f"jackpot: đúng kỳ #{fresh.stored_draw_id}"
    return (
        f"jackpot: đang chậm {fresh.draws_behind} kỳ — "
        f"số đang lưu là kỳ #{fresh.stored_draw_id}, kỳ mới nhất #{fresh.latest_draw_id}"
    )
