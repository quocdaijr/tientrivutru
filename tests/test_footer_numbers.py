"""The colophon quotes a line count and a test count, and both READMEs wear a test badge.

All of them were measured, so all of them rot the moment the code changes - and a stale
number on a site whose entire premise is that no number lies would be the worst bug in the
repo. These tests make them impossible to leave behind.

The badge is here because it proved the point: it sat at 459 while the suite passed 570,
silently, for 111 tests. The footer never drifted, because the footer had a test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "site" / "index.html"
READMES = (ROOT / "README.md", ROOT / "README.en.md")

# The same set the footer's figure was measured over: shipped code, not its tests.
COUNTED = (
    sorted((ROOT / "src" / "tientrivutru").glob("*.py"))
    + sorted((ROOT / "src" / "tientrivutru" / "sources").glob("*.py"))
    + sorted((ROOT / "site").glob("*.js"))
    + sorted((ROOT / "site").glob("*.html"))
    + sorted((ROOT / "site").glob("*.css"))
)


def measured_lines() -> int:
    return sum(len(p.read_text(encoding="utf-8").splitlines()) for p in COUNTED)


def footer_claim() -> tuple[int, int]:
    match = re.search(
        r"([\d.]+) dòng code, ([\d.]+) test", INDEX.read_text(encoding="utf-8")
    )
    assert match, "the colophon no longer states a line count and a test count"
    return (
        int(match.group(1).replace(".", "")),
        int(match.group(2).replace(".", "")),
    )


def test_counted_file_set_is_not_empty():
    """Guards the guard: a bad glob would make the line count trivially agree."""
    assert len(COUNTED) > 10


def test_footer_line_count_is_the_measured_one():
    claimed, _ = footer_claim()
    assert claimed == measured_lines(), (
        f"colophon says {claimed} lines, the tree measures {measured_lines()}"
    )


def test_footer_test_count_is_the_collected_one(request):
    """Only meaningful for a full run - a subset collects fewer by definition."""
    opt = request.config.option
    narrowed = (
        [a for a in request.config.args if "::" in a or a.endswith(".py")]
        or getattr(opt, "keyword", "")
        or getattr(opt, "markexpr", "")
    )
    if narrowed:
        pytest.skip("chỉ kiểm khi chạy toàn bộ suite")
    _, claimed = footer_claim()
    assert claimed == request.session.testscollected


def test_readme_badges_state_the_collected_test_count(request):
    """Both language editions carry the badge, so both can rot; the English one is the
    likelier to be forgotten, which is exactly why it is asserted rather than trusted."""
    opt = request.config.option
    narrowed = (
        [a for a in request.config.args if "::" in a or a.endswith(".py")]
        or getattr(opt, "keyword", "")
        or getattr(opt, "markexpr", "")
    )
    if narrowed:
        pytest.skip("chỉ kiểm khi chạy toàn bộ suite")

    for readme in READMES:
        match = re.search(r"tests-(\d+)%20passing", readme.read_text(encoding="utf-8"))
        assert match, f"{readme.name} no longer carries a test-count badge"
        assert int(match.group(1)) == request.session.testscollected, (
            f"{readme.name} badge says {match.group(1)} tests, "
            f"the suite collects {request.session.testscollected}"
        )
