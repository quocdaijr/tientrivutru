"""Fallback source: the official vietlott.vn result page.

Exists because the mirror lags. Observed on 2026-08-19: the mirror's newest Mega 6/45
draw was #01549 (Fri 14 Aug) while vietlott.vn already showed #01550 (Sun 16 Aug) with
06 07 15 19 36 41. That draw would otherwise be lost from history.

Two findings that shaped this module:

1. **cloudscraper is not needed.** The site returns HTTP 200 to a plain request with a
   browser User-Agent - Cloudflare does not challenge these pages. Avoiding that
   dependency keeps the install thin. The `.html` suffix IS required; the short paths
   return a Cloudflare "Địa chỉ truy cập sai" error page.

2. **Only the latest draw is fetchable.** Older draws load through an AjaxPro endpoint
   (`ServerSideDrawResult`) whose first argument is a `CreateRenderInfo()` object built
   client-side. Reproducing that is fragile reverse-engineering for little gain, since
   the mirror already carries the deep history. So this module deliberately fetches
   ONLY the most recent draw - which is exactly where the mirror fails.

Verified page structure (2026-08-19):
    div.chitietketqua_title h5   ->  "Kỳ quay thưởng <b>#01386</b> ngày <b>18/08/2026</b>"
    div.day_so_ket_qua_v2        ->  span.bong_tron per number; for Power 6/55 the
                                     seventh span is the bonus, set off by <i>|</i>
"""

from __future__ import annotations

import re
from datetime import datetime

import requests

from ..games import GameSpec
from ..models import Draw

BASE_URL = "https://vietlott.vn/vi/trung-thuong/ket-qua-trung-thuong"
SOURCE_LABEL = "live:vietlott.vn"
DEFAULT_TIMEOUT = 30

# A browser User-Agent is required; the default requests agent gets a Cloudflare page.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi,en;q=0.8",
}

# The page slug is the product code without the slash: 6/55 -> 655, 6/45 -> 645.
PAGE_SLUGS = {"power655": "655", "mega645": "645"}

TITLE_PATTERN = re.compile(
    r"Kỳ\s+quay\s+thưởng\s*<b>\s*#(?P<draw_id>\d+)\s*</b>\s*ngày\s*<b>\s*"
    r"(?P<date>\d{2}/\d{2}/\d{4})\s*</b>",
    re.IGNORECASE,
)
BALL_PATTERN = re.compile(r'<span class="bong_tron[^"]*">\s*(\d{1,2})\s*</span>')
RESULT_BLOCK_PATTERN = re.compile(
    r'<div class="day_so_ket_qua_v2">(?P<block>.*?)</div>', re.DOTALL
)


class LiveFetchError(RuntimeError):
    """Raised when the official page cannot be read or understood."""


def page_url(spec: GameSpec) -> str:
    try:
        slug = PAGE_SLUGS[spec.key]
    except KeyError:
        raise LiveFetchError(
            f"{spec.key} has no vietlott.vn result page - live fetch is Vietlott only"
        ) from None
    # The .html suffix is mandatory: without it Cloudflare serves an error page.
    return f"{BASE_URL}/{slug}.html"


def fetch_html(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(page_url(spec), headers=BROWSER_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_page(spec: GameSpec, page: str) -> Draw:
    """Extract the single draw the page displays.

    Regex rather than a DOM parser is a deliberate trade: it avoids a dependency for
    two highly structured fields, and every extracted value is then validated by Draw,
    so a layout change fails loudly instead of producing a plausible wrong result.
    """
    title = TITLE_PATTERN.search(page)
    if not title:
        raise LiveFetchError(
            f"{spec.key}: could not find the draw title on {page_url(spec)} - "
            "the page layout probably changed"
        )

    block = RESULT_BLOCK_PATTERN.search(page)
    if not block:
        raise LiveFetchError(f"{spec.key}: could not find the result block (day_so_ket_qua_v2)")

    numbers = [int(value) for value in BALL_PATTERN.findall(block.group("block"))]
    if len(numbers) != spec.result_length:
        raise LiveFetchError(
            f"{spec.key} draw {title.group('draw_id')}: expected {spec.result_length} "
            f"numbers on the page, found {len(numbers)}: {numbers}"
        )

    return Draw(
        game=spec.key,
        draw_id=title.group("draw_id"),
        date=datetime.strptime(title.group("date"), "%d/%m/%Y").date(),
        main=tuple(sorted(numbers[: spec.pick])),
        bonus=numbers[spec.pick] if spec.has_bonus else None,
        source=SOURCE_LABEL,
    )


def fetch_latest(spec: GameSpec, *, timeout: int = DEFAULT_TIMEOUT) -> Draw:
    """The most recent draw straight from vietlott.vn."""
    return parse_page(spec, fetch_html(spec, timeout=timeout))
