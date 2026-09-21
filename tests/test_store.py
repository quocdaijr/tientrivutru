"""The append-only guard. This is what makes the scoreboard trustworthy."""

from __future__ import annotations

import pytest

from conftest import make_draw, make_prophecy
from tientrivutru import store
from tientrivutru.games import MEGA645, POWER655


def test_reading_missing_files_returns_empty():
    assert store.read_draws("mega645") == ()
    assert store.read_prophecies() == ()
    assert store.read_scoreboard() is None


def test_draws_round_trip():
    draws = [make_draw(MEGA645, i) for i in (3, 1, 2)]
    written = store.write_draws("mega645", draws)

    loaded = store.read_draws("mega645")
    assert written == 3
    assert [d.draw_id for d in loaded] == ["00001", "00002", "00003"]
    assert loaded[0].main == draws[0].main


def test_power655_bonus_survives_round_trip():
    original = make_draw(POWER655, 1386, main=(3, 15, 18, 38, 41, 48), bonus=30)
    store.write_draws("power655", [original])

    assert store.read_draws("power655")[0].bonus == 30


def test_write_draws_rejects_foreign_game():
    with pytest.raises(ValueError, match="refusing to write"):
        store.write_draws("mega645", [make_draw(POWER655, 1)])


def test_write_draws_rejects_duplicate_ids():
    duplicate = [make_draw(MEGA645, 1), make_draw(MEGA645, 1)]
    with pytest.raises(ValueError, match="duplicate draw_ids"):
        store.write_draws("mega645", duplicate)


def test_merge_draws_adds_only_new_rows():
    store.write_draws("mega645", [make_draw(MEGA645, 1)])
    added, total = store.merge_draws("mega645", [make_draw(MEGA645, 1), make_draw(MEGA645, 2)])

    assert (added, total) == (1, 2)


def test_merge_draws_never_rewrites_history():
    """A changed past result would silently rewrite the scoreboard - so it cannot happen."""
    original = make_draw(MEGA645, 1, main=(1, 2, 3, 4, 5, 6))
    store.write_draws("mega645", [original])

    tampered = make_draw(MEGA645, 1, main=(7, 8, 9, 10, 11, 12))
    added, _ = store.merge_draws("mega645", [tampered])

    assert added == 0
    assert store.read_draws("mega645")[0].main == (1, 2, 3, 4, 5, 6)


def test_prophecy_round_trip():
    prophecy = make_prophecy(MEGA645, 1550)
    store.append_prophecy(prophecy)

    loaded = store.read_prophecies("mega645")
    assert len(loaded) == 1
    assert loaded[0].numbers == prophecy.numbers
    assert loaded[0].seed == prophecy.seed


def test_prophecy_append_only():
    """Writing twice for the same draw must fail - no retroactive edits."""
    store.append_prophecy(make_prophecy(MEGA645, 1550))

    with pytest.raises(store.ProphecyConflict, match="already exists"):
        store.append_prophecy(make_prophecy(MEGA645, 1550, numbers=tuple(range(2, 14))))

    assert len(store.read_prophecies("mega645")) == 1


def test_prophecy_rejected_if_draw_already_settled():
    """Prophesying a draw that already has a result is cheating."""
    store.write_draws("mega645", [make_draw(MEGA645, 1549)])

    with pytest.raises(store.ProphecyConflict, match="already been drawn"):
        store.append_prophecy(make_prophecy(MEGA645, 1549))


def test_prophecies_for_different_games_do_not_collide():
    store.append_prophecy(make_prophecy(MEGA645, 1550))
    store.append_prophecy(make_prophecy(POWER655, 1550))

    assert len(store.read_prophecies()) == 2
    assert len(store.read_prophecies("mega645")) == 1


def test_corrupt_jsonl_reports_location():
    """A malformed line must name its line number, not fail somewhere downstream."""
    import json

    valid = json.dumps(make_draw(MEGA645, 1).to_dict())
    path = store.draws_path("mega645")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{valid}\nnot json at all\n", encoding="utf-8")

    with pytest.raises(ValueError, match=":2 is not valid JSON"):
        store.read_draws("mega645")


def test_scoreboard_round_trip():
    store.write_scoreboard({"per_game": {}, "note": "xin chào"})
    assert store.read_scoreboard()["note"] == "xin chào"


def test_data_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_DATA_DIR, str(tmp_path / "elsewhere"))
    assert store.data_dir() == tmp_path / "elsewhere"


def test_write_json_if_changed_skips_timestamp_only_diff():
    """Regression: every scheduled run regenerated these files, and `generated_at`
    alone made them differ - turning the commit history into two junk commits a day.
    """
    path = store.data_dir() / "probe.json"
    first = {"generated_at": "2026-08-19T00:00:00Z", "per_game": {"mega645": {"roi": -0.86}}}
    later = {"generated_at": "2026-08-19T11:00:00Z", "per_game": {"mega645": {"roi": -0.86}}}

    assert store.write_json_if_changed(path, first) is True
    written = path.read_text(encoding="utf-8")

    assert store.write_json_if_changed(path, later) is False
    assert path.read_text(encoding="utf-8") == written, "file must not be rewritten"


def test_write_json_if_changed_writes_on_real_diff():
    path = store.data_dir() / "probe.json"
    store.write_json_if_changed(path, {"generated_at": "t1", "roi": -0.86})

    assert store.write_json_if_changed(path, {"generated_at": "t2", "roi": -0.71}) is True
    assert '"roi": -0.71' in path.read_text(encoding="utf-8")


def test_write_json_if_changed_recovers_from_corrupt_file():
    """A half-written file must not make the next run silently skip its write."""
    path = store.data_dir() / "probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")

    assert store.write_json_if_changed(path, {"generated_at": "t", "roi": -0.86}) is True


def test_scoreboard_write_is_skipped_when_only_time_moved():
    payload = {"generated_at": "2026-08-19T00:00:00Z", "per_game": {}}
    assert store.write_scoreboard(payload) is True
    assert store.write_scoreboard({**payload, "generated_at": "2026-08-19T18:45:00Z"}) is False


# --------------------------------------------------------------------------- prizes


def _prizes(top: int = 34_897_731_150, winners: int = 0, when: str = "2026-08-20T07:00:00+00:00"):
    from tientrivutru.sources.vietlott_prizes import DrawPrizes, PrizeTier

    return DrawPrizes(
        game="power655",
        draw_id="01386",
        jackpots={"Jackpot 1": top, "Jackpot 2": 3_544_192_350},
        tiers=(PrizeTier("Jackpot 1", winners, top), PrizeTier("Giải Ba", 16_116, 50_000)),
        fetched_at=when,
    )


def test_write_prizes_then_read_them_back():
    assert store.write_prizes(_prizes()) is True

    stored = store.read_prizes("power655")
    assert stored["jackpots"]["Jackpot 1"] == 34_897_731_150
    assert stored["rolled_over"] is True
    assert stored["draw_id"] == "01386"


def test_read_prizes_returns_none_when_never_fetched():
    assert store.read_prizes("mega645") is None


def test_a_second_write_of_the_same_figures_does_not_touch_the_file():
    """The jackpot only moves when a draw happens. Rewriting on every cron run would
    turn the audit trail into two junk commits a day - the same trap generated_at set."""
    store.write_prizes(_prizes())

    assert store.write_prizes(_prizes(when="2026-08-20T19:30:00+00:00")) is False


def test_a_changed_jackpot_does_get_written():
    store.write_prizes(_prizes())

    assert store.write_prizes(_prizes(top=41_000_000_000)) is True
    assert store.read_prizes("power655")["jackpots"]["Jackpot 1"] == 41_000_000_000


def test_somebody_winning_gets_written_even_at_the_same_amount():
    """Same pot, but rolled_over flips - that is the whole story of the draw."""
    store.write_prizes(_prizes(winners=0))

    assert store.write_prizes(_prizes(winners=1)) is True
    assert store.read_prizes("power655")["rolled_over"] is False
