"""JSONL persistence with an append-only guard on prophecies.

The guard is the integrity of this whole project: a prophecy may only be written
for a draw that has not happened yet, and may never be overwritten. Without that,
the scoreboard is just a number the oracle gets to choose.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from .models import Draw, Prophecy

if TYPE_CHECKING:  # pragma: no cover
    from .kienthiet_oracle import VeProphecy
    from .sources.kienthiet import Board
    from .sources.vietlott_prizes import DrawPrizes
    from .sources.xsmb import XsmbDraw

ENV_DATA_DIR = "TIENTRIVUTRU_DATA_DIR"


class ProphecyConflict(RuntimeError):
    """Raised when a prophecy would overwrite history or predict a settled draw."""


def data_dir() -> Path:
    """Where data lives. Overridable via TIENTRIVUTRU_DATA_DIR so tests never touch the repo."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data"


def draws_path(game: str) -> Path:
    return data_dir() / "draws" / f"{game}.jsonl"


def boards_path(region: str) -> Path:
    return data_dir() / "boards" / f"{region}.jsonl"


def predictions_path() -> Path:
    return data_dir() / "predictions.jsonl"


def ve_path() -> Path:
    return data_dir() / "ve.jsonl"


def ve_scoreboard_path() -> Path:
    return data_dir() / "ve_scoreboard.json"


def scoreboard_path() -> Path:
    return data_dir() / "scoreboard.json"


def _read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} is not valid JSON: {exc}") from exc


def _write_atomic(path: Path, payload: str) -> None:
    """Write via temp file + rename so an interrupted run never truncates data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def read_draws(game: str) -> tuple[Draw, ...]:
    """All stored draws for a game, sorted by draw_id."""
    draws = tuple(Draw.from_dict(row) for row in _read_jsonl(draws_path(game)))
    return tuple(sorted(draws, key=lambda d: d.draw_id))


def write_draws(game: str, draws: Sequence[Draw]) -> int:
    """Replace the stored draws for a game. Returns how many rows were written."""
    wrong = {d.game for d in draws} - {game}
    if wrong:
        raise ValueError(f"refusing to write {sorted(wrong)} draws into {game}.jsonl")
    ordered = sorted(draws, key=lambda d: d.draw_id)
    ids = [d.draw_id for d in ordered]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate draw_ids for {game}: cannot write")
    body = "".join(json.dumps(d.to_dict(), ensure_ascii=False) + "\n" for d in ordered)
    _write_atomic(draws_path(game), body)
    return len(ordered)


def merge_draws(game: str, incoming: Iterable[Draw]) -> tuple[int, int]:
    """Merge new draws into storage without disturbing existing rows.

    Returns (added, total). Existing draws win on conflict: history is never rewritten
    silently, because a changed past result would silently rewrite the scoreboard too.
    """
    existing = {d.draw_id: d for d in read_draws(game)}
    added = 0
    for draw in incoming:
        if draw.game != game:
            raise ValueError(f"draw {draw.draw_id} is {draw.game}, expected {game}")
        if draw.draw_id not in existing:
            existing[draw.draw_id] = draw
            added += 1
    total = write_draws(game, tuple(existing.values()))
    return added, total


def read_prophecies(game: str | None = None) -> tuple[Prophecy, ...]:
    """All prophecies, optionally filtered to one game, sorted by (game, draw_id)."""
    rows = (Prophecy.from_dict(row) for row in _read_jsonl(predictions_path()))
    items = tuple(p for p in rows if game is None or p.game == game)
    return tuple(sorted(items, key=lambda p: (p.game, p.draw_id)))


def append_prophecy(prophecy: Prophecy) -> None:
    """Append a prophecy, refusing anything that would compromise the audit trail."""
    for existing in read_prophecies(prophecy.game):
        if existing.draw_id == prophecy.draw_id:
            raise ProphecyConflict(
                f"a prophecy for {prophecy.game} draw {prophecy.draw_id} already exists "
                f"(seed {existing.seed[:12]}...). Prophecies are append-only."
            )

    settled = {d.draw_id for d in read_draws(prophecy.game)}
    if prophecy.draw_id in settled:
        raise ProphecyConflict(
            f"{prophecy.game} draw {prophecy.draw_id} has already been drawn. "
            "Prophesying a settled draw is cheating."
        )

    path = predictions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(prophecy.to_dict(), ensure_ascii=False) + "\n")


TIMESTAMP_KEYS = ("generated_at",)


def write_json_if_changed(
    path: Path, payload: dict, *, ignore: Sequence[str] = TIMESTAMP_KEYS, indent: int = 2
) -> bool:
    """Write JSON only when something other than the timestamps actually changed.

    Every scheduled run regenerates these files, and `generated_at` alone would make
    them differ every time - which turns the commit history from an audit trail into
    two junk commits a day. Returns whether the file was written.
    """
    body = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if existing is not None:
            strip = lambda d: {k: v for k, v in d.items() if k not in ignore}  # noqa: E731
            if strip(existing) == strip(payload):
                return False
    _write_atomic(path, body)
    return True


def write_scoreboard(payload: dict) -> bool:
    return write_json_if_changed(scoreboard_path(), payload)


def write_ve_scoreboard(payload: dict) -> bool:
    return write_json_if_changed(ve_scoreboard_path(), payload)


def read_ve_scoreboard() -> dict | None:
    path = ve_scoreboard_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_scoreboard() -> dict | None:
    path = scoreboard_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def prizes_path(game: str) -> Path:
    return data_dir() / "prizes" / f"{game}.json"


def write_prizes(prizes: DrawPrizes) -> bool:
    """Persist one draw's money figures. Returns whether the file changed.

    `fetched_at` is excluded from the comparison on purpose. A completed draw's jackpot
    does not move, so every cron run would otherwise rewrite the file with nothing but a
    new timestamp - the same trap `generated_at` set, and the reason this helper exists.
    What that costs is knowing when the figure was last *checked*; what it buys is a
    history where a commit means the money actually changed.
    """
    path = prizes_path(prizes.game)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json_if_changed(path, prizes.as_dict(), ignore=("fetched_at",))


def read_prizes(game: str) -> dict | None:
    """The last stored figures for a game, or None if they were never fetched."""
    path = prizes_path(game)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_boards(region: str) -> tuple[Board, ...]:
    """Stored kiến thiết boards for one region, oldest first, then by đài."""
    from .sources.kienthiet import Board

    boards = tuple(Board.from_dict(row) for row in _read_jsonl(boards_path(region)))
    return tuple(sorted(boards, key=lambda b: b.key))


def write_boards(region: str, boards: Sequence[Board]) -> int:
    """Replace one region's boards. Identity is (date, đài), so duplicates are a bug."""
    wrong = {b.region for b in boards} - {region}
    if wrong:
        raise ValueError(f"refusing to write {sorted(wrong)} boards into {region}.jsonl")
    ordered = sorted(boards, key=lambda b: b.key)
    keys = [b.key for b in ordered]
    if len(set(keys)) != len(keys):
        duplicate = next(k for k in keys if keys.count(k) > 1)
        raise ValueError(f"duplicate board {duplicate[1]} {duplicate[0]}: cannot write")
    body = "".join(json.dumps(b.to_dict(), ensure_ascii=False) + "\n" for b in ordered)
    _write_atomic(boards_path(region), body)
    return len(ordered)


def merge_boards(region: str, incoming: Iterable[Board]) -> tuple[int, int]:
    """Merge boards into storage without disturbing existing rows.

    Returns (added, total). Existing boards win, for the same reason merge_draws works
    that way: a rewritten past result silently rewrites the scoreboard with it.
    """
    existing = {b.key: b for b in read_boards(region)}
    added = 0
    for board in incoming:
        if board.region != region:
            raise ValueError(f"board {board.province} is {board.region}, expected {region}")
        if board.key not in existing:
            existing[board.key] = board
            added += 1
    total = write_boards(region, tuple(existing.values()))
    return added, total


def read_ve(province: str | None = None) -> tuple[VeProphecy, ...]:
    """Committed kiến thiết tickets, oldest first, optionally for one đài."""
    from .kienthiet_oracle import VeProphecy

    rows = (VeProphecy.from_dict(row) for row in _read_jsonl(ve_path()))
    items = tuple(v for v in rows if province is None or v.province == province)
    return tuple(sorted(items, key=lambda v: v.key))


def append_ve(prophecy: VeProphecy) -> None:
    """Append a ticket, refusing anything that would compromise the audit trail.

    Same two rules as append_prophecy: never overwrite, never predict a draw that has
    already happened. Here 'already happened' means a board is on file for that đài and
    day - which is why ingest and oracle must not be reordered.
    """
    for existing in read_ve(prophecy.province):
        if existing.draw_date == prophecy.draw_date:
            raise ProphecyConflict(
                f"đã có vé cho {prophecy.province} ngày {prophecy.draw_date} "
                f"(seed {existing.seed[:12]}...). Vé là append-only."
            )

    settled = {b.key for b in read_boards(prophecy.region)}
    if prophecy.key in settled:
        raise ProphecyConflict(
            f"{prophecy.province} ngày {prophecy.draw_date} đã quay rồi. "
            "Phán một kỳ đã quay là ăn gian."
        )

    path = ve_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(prophecy.to_dict(), ensure_ascii=False) + "\n")


def xsmb_path() -> Path:
    return data_dir() / "xsmb.jsonl"


def read_xsmb() -> tuple[XsmbDraw, ...]:
    """Stored XSMB draws, oldest first.

    Derived from the Miền Bắc boards once those exist, because a board holds the full
    printed number and this record only ever wanted its last two digits. The legacy
    `xsmb.jsonl` remains the fallback so a checkout without boards still works - and
    tests/test_kienthiet_migration.py pins that the two agree, row for row.
    """
    from .sources.xsmb import XsmbDraw

    if boards_path("mb").exists():
        return tuple(
            XsmbDraw(date=board.date, special=board.tails[0], prizes=board.tails)
            for board in read_boards("mb")
        )
    draws = tuple(XsmbDraw.from_dict(row) for row in _read_jsonl(xsmb_path()))
    return tuple(sorted(draws, key=lambda d: d.date))


def write_xsmb(draws: Sequence[XsmbDraw]) -> int:
    """Replace stored XSMB history. Identity is the date, so duplicates are a bug."""
    ordered = sorted(draws, key=lambda d: d.date)
    dates = [d.date for d in ordered]
    if len(set(dates)) != len(dates):
        raise ValueError("duplicate XSMB dates: cannot write")
    body = "".join(json.dumps(d.to_dict(), ensure_ascii=False) + "\n" for d in ordered)
    _write_atomic(xsmb_path(), body)
    return len(ordered)


def latest_xsmb_special() -> int | None:
    """The most recent XSMB special prize, or None when no history is stored.

    Read lazily by the oracle so a missing XSMB file degrades to a silent signal
    rather than breaking the run.
    """
    from .sources.xsmb import latest_special

    return latest_special(read_xsmb())
