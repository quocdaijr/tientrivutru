"""The static-site bundle. It must be self-contained, small, and honest."""

from __future__ import annotations

import json
from datetime import date

from conftest import make_draw, make_prophecy, random_draw
from tientrivutru import site, store
from tientrivutru.games import MEGA645, POWER655
from tientrivutru.sources import kienthiet, xsmb


def _seed_history(count: int = 30) -> None:
    import random

    rng = random.Random(7)
    for spec in (POWER655, MEGA645):
        store.write_draws(spec.key, [random_draw(spec, i, rng) for i in range(1, count + 1)])


def test_bundle_covers_only_prophecy_games():
    """US games are stats-only and have no wheel, so the page never shows them."""
    _seed_history()
    bundle = site.build_bundle()
    assert [g["key"] for g in bundle["games"]] == ["power655", "mega645"]


def test_bundle_carries_the_disclaimer():
    _seed_history()
    bundle = site.build_bundle()
    assert "biến cố độc lập" in bundle["disclaimer"]
    assert "paper-trading" in bundle["disclaimer"]


def test_bundle_includes_both_roi_figures():
    """The jackpot-free ROI must reach the page, or one lucky draw rewrites the story."""
    _seed_history()
    game = site.build_bundle()["games"][0]

    assert "expected_roi" in game["wheel"]
    assert "expected_roi_excluding_jackpot" in game["wheel"]
    assert game["wheel"]["expected_roi_excluding_jackpot"] < game["wheel"]["expected_roi"] < 0
    assert "roi_excluding_jackpot" in game["score"]


def test_bundle_trims_history_to_recent_draws():
    """The browser has no use for a thousand draws."""
    _seed_history(count=200)
    game = site.build_bundle()["games"][0]

    assert game["draw_count"] == 200
    assert len(game["recent"]) == site.RECENT_DRAWS


def test_bundle_includes_chi_square_and_verdict():
    _seed_history(count=120)
    game = site.build_bundle()["games"][0]

    assert game["chi_square"]["degrees_of_freedom"] == POWER655.pool - 1
    assert 0.0 <= game["chi_square"]["p_value"] <= 1.0
    assert game["chi_square"]["verdict"]


def test_frequency_covers_the_whole_pool():
    _seed_history()
    game = site.build_bundle()["games"][1]
    assert len(game["frequency"]) == MEGA645.pool


def test_pending_prophecy_appears_but_settled_ones_do_not():
    store.write_draws("mega645", [make_draw(MEGA645, 1)])
    store.append_prophecy(make_prophecy(MEGA645, 2))

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    assert game["pending_prophecy"]["draw_id"] == "00002"


def test_no_pending_prophecy_is_null_not_an_error():
    store.write_draws("mega645", [make_draw(MEGA645, 1)])
    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    assert game["pending_prophecy"] is None


def _southern_board(day: date, province: str = "an-giang") -> kienthiet.Board:
    return kienthiet.Board(
        date=day,
        region="mn",
        province=province,
        tiers=(
            ("db", ("510332",)),
            ("g1", ("89516",)),
            ("g2", ("44895",)),
            ("g3", ("52640", "02439")),
            ("g4", ("90111", "32541", "20491", "71417", "32217", "57371", "15096")),
            ("g5", ("1635",)),
            ("g6", ("9670", "9023", "3404")),
            ("g7", ("516",)),
            ("g8", ("54",)),
        ),
    )


def test_kienthiet_is_an_empty_list_when_absent():
    """A list, not a nullable key: three regions had to fit where XSMB alone used to."""
    _seed_history()
    assert site.build_bundle()["kienthiet"] == []


def test_kienthiet_section_is_included_when_present():
    store.write_boards("mn", [_southern_board(date(2026, 8, 20))])
    _seed_history()

    (payload,) = site.build_bundle()["kienthiet"]
    assert payload["region"] == "mn"
    assert payload["draw_count"] == 1
    assert payload["provinces"] == 1
    assert len(payload["frequency"]) == 100
    assert payload["chi_square"]["degrees_of_freedom"] == 99
    assert payload["latest"]["special"] == "510332"


def test_only_prophesiable_regions_carry_a_ve_score():
    store.write_boards("mn", [_southern_board(date(2026, 8, 20))])
    store.write_xsmb(
        [xsmb.XsmbDraw(date=date(2026, 8, 17), special=7, prizes=(7,) + tuple(range(26)))]
    )
    _seed_history()

    by_region = {p["region"]: p for p in site.build_bundle()["kienthiet"]}
    assert "ve" in by_region["mn"]
    assert by_region["mn"]["ve"]["theoretical_roi"] == -0.5
    assert "mb" not in by_region  # no Miền Bắc boards stored in this test


def test_mien_bac_appears_without_a_ve_score():
    store.write_boards(
        "mb",
        [
            kienthiet.Board(
                date=date(2026, 8, 20),
                region="mb",
                province="mien-bac",
                tiers=(
                    ("db", ("07523",)),
                    ("g1", ("29580",)),
                    ("g2", ("34885", "65037")),
                    ("g3", ("44442", "95464", "14795", "94080", "18983", "22006")),
                    ("g4", ("4979", "4293", "2502", "4395")),
                    ("g5", ("4240", "3439", "3988", "5912", "3636", "5423")),
                    ("g6", ("729", "272", "278")),
                    ("g7", ("12", "25", "78", "70")),
                ),
            )
        ],
    )
    _seed_history()

    (payload,) = site.build_bundle()["kienthiet"]
    assert payload["prophesiable"] is False
    assert "ve" not in payload


def test_bundle_is_json_serialisable(tmp_path):
    _seed_history()
    bundle = site.build_bundle()
    target = site.write_bundle(bundle, site_dir=tmp_path)

    assert target.name == site.BUNDLE_NAME
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded["games"][0]["display"] == "Power 6/55"


def test_write_bundle_leaves_no_temp_file(tmp_path):
    site.write_bundle({"games": [], "xsmb": None}, site_dir=tmp_path)
    assert list(p.name for p in tmp_path.iterdir()) == [site.BUNDLE_NAME]


def test_bundle_handles_empty_history():
    """A fresh clone with no data must still produce a renderable bundle."""
    bundle = site.build_bundle()
    for game in bundle["games"]:
        assert game["draw_count"] == 0
        assert game["latest"] is None
        assert game["chi_square"] is None
        assert game["score"]["draws_scored"] == 0


# --------------------------------------------------------- jackpot in the bundle


def _jackpot_label(game: str) -> str:
    """Power calls it "Jackpot 1"; Mega just "Jackpot". Getting this wrong is what caught
    the production guard that refuses figures from another game's page."""
    return "Jackpot 1" if game == "power655" else "Jackpot"


def _store_prizes(game: str, draw_id: str, top: int = 34_897_731_150, winners: int = 0):
    from tientrivutru.sources.vietlott_prizes import DrawPrizes, PrizeTier

    store.write_prizes(
        DrawPrizes(
            game=game,
            draw_id=draw_id,
            jackpots={_jackpot_label(game): top},
            tiers=(PrizeTier(_jackpot_label(game), winners, top),),
            fetched_at="2026-08-20T07:00:00+00:00",
        )
    )


def test_bundle_carries_the_jackpot_for_the_newest_draw():
    store.write_draws("power655", [make_draw(POWER655, 1386)])
    _store_prizes("power655", "01386")

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "power655")

    assert game["prizes"]["top_jackpot_vnd"] == 34_897_731_150
    assert game["prizes"]["rolled_over"] is True
    assert game["prizes"]["matches_latest_draw"] is True


def test_a_jackpot_from_an_older_draw_is_flagged_not_hidden():
    """If the prize fetch failed, the stored figure belongs to a draw that is no longer
    the newest. Hiding it loses information; presenting it as current would be a lie.
    The flag lets the page say which draw the money belongs to."""
    store.write_draws("power655", [make_draw(POWER655, 1386), make_draw(POWER655, 1387)])
    _store_prizes("power655", "01386")

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "power655")

    assert game["prizes"]["matches_latest_draw"] is False
    assert game["prizes"]["draw_id"] == "01386"
    assert game["prizes"]["latest_draw_id"] == "01387"


def test_prizes_are_null_when_never_fetched():
    store.write_draws("power655", [make_draw(POWER655, 1386)])

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "power655")

    assert game["prizes"] is None


# ------------------------------------------------ what today's draw would actually pay


def test_payout_table_covers_every_hit_count():
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551", top=24_507_110_500)

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "mega645")
    rows = game["payout_if_hit"]

    assert [r["hits"] for r in rows] == [0, 1, 2, 3, 4, 5, 6]


def test_hitting_nothing_pays_nothing_and_loses_the_whole_stake():
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551")

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    zero = game["payout_if_hit"][0]

    assert zero["payout_vnd"] == 0
    assert zero["net_vnd"] == -game["wheel"]["cost_vnd"]


def test_six_hits_uses_the_live_jackpot_not_the_floor():
    """The floor is 12 billion; the scraped pot is 24.5. Showing the floor when we have
    the real figure would understate it, which is just as wrong as overstating it."""
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551", top=24_507_110_500)

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    six = game["payout_if_hit"][6]

    assert six["uses_live_jackpot"] is True
    assert six["payout_vnd"] > 24_507_110_500


def test_without_a_scraped_jackpot_the_table_falls_back_to_the_floor_and_says_so():
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    six = game["payout_if_hit"][6]

    assert six["uses_live_jackpot"] is False
    assert six["payout_vnd"] >= MEGA645.jackpot_floor["jackpot"]


def test_the_loss_lives_in_the_probability_not_the_payout():
    """Worth pinning because the obvious guess is wrong. A wheel is not a small win when
    it lands - four hits on Mega already clears the stake, five pays 112 million against
    9.24 million staked. The reason the ROI is -71% is that four-or-better happens about
    once in 28 draws, not that the prizes are stingy. The table must show both halves, or
    it argues the opposite of what the numbers say."""
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551")

    rows = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")["payout_if_hit"]

    assert rows[3]["net_vnd"] < 0, "three hits still loses"
    assert rows[4]["net_vnd"] > 0, "four hits already clears the stake"
    assert rows[5]["net_vnd"] > 100_000_000
    # and yet: the chance of doing four or better is tiny, which is where the ROI goes
    assert sum(r["probability"] for r in rows[4:]) < 0.04


def test_probability_column_matches_the_wheel_module():
    from tientrivutru import wheel

    store.write_draws("mega645", [make_draw(MEGA645, 1551)])

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    for row in game["payout_if_hit"]:
        assert row["probability"] == round(wheel.hit_probability(MEGA645, row["hits"]), 9)


def test_probabilities_sum_to_one():
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    total = sum(r["probability"] for r in game["payout_if_hit"])

    assert abs(total - 1.0) < 1e-6


# ------------------------------------------- the compact summary that replaced the table


def test_summary_reports_how_often_the_wheel_pays_nothing():
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551")

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")
    s = game["payout_summary"]

    rows = game["payout_if_hit"]
    expected = sum(r["probability"] for r in rows if r["payout_vnd"] == 0)
    assert abs(s["nothing_probability"] - expected) < 1e-9
    assert 0.5 < s["nothing_probability"] < 1.0


def test_summary_reports_how_rarely_the_wheel_turns_a_profit():
    """The counterweight to a jackpot figure. Without it the block is an advert."""
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])
    _store_prizes("mega645", "01551")

    s = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")["payout_summary"]

    assert s["profit_one_in"] > 1
    assert s["jackpot_one_in"] > s["profit_one_in"], "the jackpot is the rarest outcome"


def test_summary_probabilities_come_from_the_rows_not_a_second_calculation():
    """One source of truth. A summary that drifts from the table it summarises is worse
    than no summary, and this is exactly where that drift would hide."""
    store.write_draws("power655", [make_draw(POWER655, 1386)])
    _store_prizes("power655", "01386")

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "power655")
    rows, s = game["payout_if_hit"], game["payout_summary"]

    assert abs(s["profit_probability"] - sum(
        r["probability"] for r in rows if r["net_vnd"] > 0)) < 1e-9


def test_the_full_table_stays_in_the_bundle_even_though_the_page_stopped_drawing_it():
    """The page was trimmed on request; the data was not deleted. Anyone reading
    data.json still gets every row."""
    store.write_draws("mega645", [make_draw(MEGA645, 1551)])

    game = next(g for g in site.build_bundle()["games"] if g["key"] == "mega645")

    assert len(game["payout_if_hit"]) == MEGA645.pick + 1


def test_jackpot_odds_are_not_recomputed_from_a_rounded_probability():
    """A real off-by-one, caught on the rendered page. P(6 hits) on Power is 3.187e-5;
    rounding it to nine decimals and then inverting gives 1-in-31,375 instead of 31,374.
    The summary must read the row's own figure, which was computed before rounding."""
    from math import comb

    from tientrivutru import wheel

    store.write_draws("power655", [make_draw(POWER655, 1386)])
    game = next(g for g in site.build_bundle()["games"] if g["key"] == "power655")

    exact = round(1 / wheel.hit_probability(POWER655, POWER655.pick))
    assert game["payout_summary"]["jackpot_one_in"] == exact
    # and the exact value is just the ratio of combination counts
    assert exact == round(comb(POWER655.pool, POWER655.pick) / comb(12, POWER655.pick))


def test_bundle_states_how_many_draws_behind_the_jackpot_is():
    """`matches_latest_draw` says the figure is old; it does not say how old. One draw
    behind is a transient, eight is a dead source, and the page cannot word the
    difference from a boolean."""
    store.write_draws("power655", [make_draw(POWER655, n) for n in range(1388, 1397)])
    _store_prizes("power655", "01388")

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "power655")

    assert game["prizes"]["draws_behind"] == 8
    assert game["prizes"]["is_stale"] is True
    assert game["prizes"]["matches_latest_draw"] is False


def test_one_draw_behind_is_not_flagged_stale_on_the_site():
    store.write_draws("power655", [make_draw(POWER655, 1386), make_draw(POWER655, 1387)])
    _store_prizes("power655", "01386")

    payload = site.build_bundle()
    game = next(g for g in payload["games"] if g["key"] == "power655")

    assert game["prizes"]["draws_behind"] == 1
    assert game["prizes"]["is_stale"] is False
