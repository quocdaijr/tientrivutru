"""How stale is the stored jackpot, and is that bad enough to shout about.

This module exists because of a real 18-day silence. On 2026-08-25 vietlott.vn began
answering GitHub Actions runners with a Cloudflare managed challenge, `_refresh_prizes`
caught the 403 exactly as designed, printed a yellow line nobody reads and kept the old
figure - and every run stayed green. The site never lied, but nothing ever said the
number had stopped moving either.

So the contract under test: one missed draw is a transient and must stay quiet; two or
more is a dead source and must be loud.
"""

from __future__ import annotations

from tientrivutru import prize_health


def _stored(draw_id: str) -> dict:
    return {"game": "mega645", "draw_id": draw_id, "top_jackpot_vnd": 28_975_123_500}


def test_prize_for_the_newest_draw_is_fresh() -> None:
    # Arrange
    stored = _stored("01560")

    # Act
    fresh = prize_health.freshness(stored, "01560")

    # Assert
    assert fresh.draws_behind == 0
    assert fresh.is_stale is False
    assert fresh.matches_latest_draw is True


def test_one_draw_behind_is_tolerated_as_a_transient() -> None:
    # A single failed fetch between two draws is ordinary. Shouting about it would
    # train the reader to ignore the alert that matters.
    fresh = prize_health.freshness(_stored("01559"), "01560")

    assert fresh.draws_behind == 1
    assert fresh.is_stale is False
    assert fresh.matches_latest_draw is False


def test_two_draws_behind_is_a_dead_source() -> None:
    fresh = prize_health.freshness(_stored("01558"), "01560")

    assert fresh.draws_behind == 2
    assert fresh.is_stale is True


def test_the_real_outage_is_reported_as_seven_draws_behind() -> None:
    # The figures that were actually live on 2026-09-10: stored #01553, mirror #01560.
    fresh = prize_health.freshness(_stored("01553"), "01560")

    assert fresh.draws_behind == 7
    assert fresh.is_stale is True


def test_never_fetched_with_draws_on_file_is_stale() -> None:
    # No stored figure at all is not a fresh state, it is the worst one. draws_behind
    # is None because the distance is unknowable, not because it is zero.
    fresh = prize_health.freshness(None, "01560")

    assert fresh.draws_behind is None
    assert fresh.is_stale is True
    assert fresh.matches_latest_draw is False


def test_no_draws_at_all_is_not_stale() -> None:
    # A fresh clone before the first ingest has nothing to be behind.
    fresh = prize_health.freshness(None, None)

    assert fresh.is_stale is False
    assert fresh.draws_behind is None


def test_prize_ahead_of_the_mirror_is_not_stale() -> None:
    # vietlott.vn has been observed showing a draw the mirror had not published yet.
    # Being ahead is not being behind, and must never read as negative staleness.
    fresh = prize_health.freshness(_stored("01561"), "01560")

    assert fresh.draws_behind == 0
    assert fresh.is_stale is False


def test_unpadded_stored_id_still_compares() -> None:
    # Older files and hand edits carry "1553" rather than "01553".
    fresh = prize_health.freshness(_stored("1553"), "01560")

    assert fresh.draws_behind == 7


def test_unreadable_draw_id_is_treated_as_never_fetched() -> None:
    # A corrupt id must not crash ingest, and must not pass as fresh either.
    fresh = prize_health.freshness({"draw_id": "??"}, "01560")

    assert fresh.draws_behind is None
    assert fresh.is_stale is True


def test_describe_names_the_gap_in_draws() -> None:
    assert "7 kỳ" in prize_health.describe(prize_health.freshness(_stored("01553"), "01560"))


def test_describe_says_so_when_nothing_was_ever_read() -> None:
    assert "chưa đọc được" in prize_health.describe(prize_health.freshness(None, "01560"))
