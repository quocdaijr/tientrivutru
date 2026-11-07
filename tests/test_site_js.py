"""The shared page helpers in dom.js, and personal.js when the browser refuses storage.

Same harness as test_finance_js.py: Node, a stub window, no DOM. Skipped without Node.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
SITE = Path(__file__).resolve().parents[1] / "site"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WORKING_STORAGE = """{
  data: {},
  getItem(k) { return k in this.data ? this.data[k] : null; },
  setItem(k, v) { this.data[k] = String(v); },
  removeItem(k) { delete this.data[k]; },
}"""

# What Safari / Firefox do with site data blocked: reads come back empty, writes throw.
BLOCKED_STORAGE = """{
  getItem: () => null,
  setItem: () => { throw new Error('SecurityError: The operation is insecure.'); },
  removeItem: () => { throw new Error('SecurityError: The operation is insecure.'); },
}"""


def _run(body: str, storage: str = WORKING_STORAGE) -> object:
    script = f"""
    global.window = {{}};
    global.localStorage = {storage};
    require({str(SITE / "dom.js")!r});
    require({str(SITE / "personal.js")!r});
    const D = window.TienTriVuTruDom;
    const P = window.TienTriVuTruPersonal;
    {body}
    """
    result = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"node failed:\n{result.stderr}")
    return json.loads(result.stdout)


# --- one number format, the one Vietnamese reads ------------------------------------

def test_percentages_use_the_vietnamese_decimal_comma_and_a_real_minus():
    got = _run(
        "console.log(JSON.stringify([D.pct(-0.8663), D.pct(0.0178), D.pct(0),"
        " D.signed(0.0178, 2), D.signed(-0.0005, 3), D.pctAt(0.5, 0)]));"
    )
    assert got == ["−86,63%", "1,78%", "0,00%", "+1,78%", "−0,050%", "50%"]


def test_dollars_use_the_same_separators_as_dong():
    """"đã đốt 9.240.000đ" next to "$4,604.40" means the dot is thousands in one and
    nothing in the other."""
    got = _run("console.log(JSON.stringify([D.usd(4604.4), D.vnd(9240000)]));")
    assert got == ["$4.604,40", "9.240.000đ"]


def test_each_formatter_is_defined_once_across_the_site():
    """Four copies of a formatter is how pages started disagreeing in the first place."""
    pattern = re.compile(r"\b(?:const|function)\s+(pct|pctAt|signed|signedPct|todayHcm)\b")
    found = [
        (m.group(1), path.name)
        for path in sorted(SITE.glob("*.js"))
        for m in pattern.finditer(path.read_text(encoding="utf-8"))
    ]
    assert sorted(found) == [("pct", "dom.js"), ("pctAt", "dom.js"),
                             ("signed", "dom.js"), ("todayHcm", "dom.js")]


# --- today, in Vietnam --------------------------------------------------------------

def test_today_is_the_vietnamese_date_not_the_utc_one():
    """23:30 UTC on 5 Feb 2027 is 06:30 on Tết morning in Vietnam. The UTC date is still
    the last day of the old lunar year, which hands out last year's guardian star."""
    got = _run(
        "console.log(JSON.stringify(D.todayHcm(new Date('2027-02-05T23:30:00Z'))));"
    )
    assert got == "2027-02-06"


def test_the_fortune_page_asks_for_today_in_vietnam():
    render = (SITE / "render.js").read_text(encoding="utf-8")
    assert "toISOString" not in render
    assert "todayHcm()" in render


# --- storage blocked ----------------------------------------------------------------

PROFILE = {"birthDate": "1990-01-27", "name": "", "gender": None}


def test_saving_a_profile_with_storage_blocked_still_serves_this_visit():
    got = _run(
        f"const kept = P.saveProfile({json.dumps(PROFILE)});"
        "console.log(JSON.stringify({kept, now: P.loadProfile()}));",
        storage=BLOCKED_STORAGE,
    )
    assert got == {"kept": False, "now": PROFILE}


def test_clearing_with_storage_blocked_still_forgets_for_this_visit():
    got = _run(
        f"P.saveProfile({json.dumps(PROFILE)});"
        "const kept = P.clearAll();"
        "console.log(JSON.stringify({kept, now: P.loadProfile()}));",
        storage=BLOCKED_STORAGE,
    )
    assert got == {"kept": False, "now": None}


def test_committing_a_pick_with_storage_blocked_does_not_throw():
    got = _run(
        "const pick = {game: 'mega', drawId: '01386', numbers: [1, 2, 3, 4, 5, 6],"
        " drawDate: '2026-11-08'};"
        "console.log(JSON.stringify(P.savePick(pick)));",
        storage=BLOCKED_STORAGE,
    )
    assert got == {"numbers": [1, 2, 3, 4, 5, 6], "drawDate": "2026-11-08"}


def test_storage_that_works_reports_the_profile_as_kept():
    got = _run(
        f"const kept = P.saveProfile({json.dumps(PROFILE)});"
        "const cleared = P.clearAll();"
        "console.log(JSON.stringify({kept, cleared, now: P.loadProfile(),"
        " raw: localStorage.getItem('tientrivutru.personal.v1')}));"
    )
    assert got == {"kept": True, "cleared": True, "now": None, "raw": None}


def test_the_form_says_when_the_browser_will_not_remember():
    render = (SITE / "render.js").read_text(encoding="utf-8")
    assert "STORAGE_REFUSED" in render and "chặn lưu trữ" in render
