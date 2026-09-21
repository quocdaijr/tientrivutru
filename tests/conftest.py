"""Shared fixtures. Tests never touch the repo's real data directory."""

from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

from tientrivutru.games import MEGA645, POWER655, GameSpec
from tientrivutru.models import Draw, Prophecy, utc_now
from tientrivutru.oracle import ORACLE_VERSION
from tientrivutru.sources.vibes import CosmicSignals
from tientrivutru.store import ENV_DATA_DIR

FIRST_DRAW_DATE = date(2020, 1, 1)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch) -> Iterator[None]:
    """Point the store at a throwaway directory for every test."""
    monkeypatch.setenv(ENV_DATA_DIR, str(tmp_path / "data"))
    yield


@pytest.fixture
def quiet_signals() -> CosmicSignals:
    """Signals with the network half missing - the degraded path."""
    return CosmicSignals(
        btc_usd=None,
        hanoi_temp_c=None,
        lunar_day=8,
        lunar_month=7,
        zodiac="Ngọ",
        day_can_chi="Ất Sửu",
    )


@pytest.fixture
def loud_signals() -> CosmicSignals:
    """Signals with everything present."""
    return CosmicSignals(
        btc_usd=64_213,
        hanoi_temp_c=38,
        lunar_day=26,
        lunar_month=6,
        zodiac="Ngọ",
        day_can_chi="Giáp Tý",
    )


def make_draw(
    spec: GameSpec,
    draw_id: int,
    *,
    main: tuple[int, ...] | None = None,
    bonus: int | None = None,
    day: date | None = None,
) -> Draw:
    """Build a valid Draw with sensible defaults."""
    if main is None:
        main = tuple(range(1, spec.pick + 1))
    if spec.has_bonus and bonus is None:
        bonus = max(main) + 1
    return Draw(
        game=spec.key,
        draw_id=str(draw_id),
        date=day or FIRST_DRAW_DATE + timedelta(days=draw_id),
        main=main,
        bonus=bonus if spec.has_bonus else None,
        source="test",
    )


def make_prophecy(
    spec: GameSpec, draw_id: int, numbers: tuple[int, ...] | None = None
) -> Prophecy:
    if numbers is None:
        numbers = tuple(range(1, 13))
    return Prophecy(
        game=spec.key,
        draw_id=str(draw_id),
        draw_date=FIRST_DRAW_DATE + timedelta(days=draw_id),
        numbers=numbers,
        seed="deadbeef" * 8,
        signals={},
        sermon={},
        oracle_version=ORACLE_VERSION,
        created_at=utc_now(),
    )


def random_draw(spec: GameSpec, draw_id: int, rng: random.Random) -> Draw:
    """A uniformly random draw - the null hypothesis made flesh."""
    picked = sorted(rng.sample(range(1, spec.pool + 1), spec.pick + (1 if spec.has_bonus else 0)))
    if spec.has_bonus:
        bonus = picked.pop(rng.randrange(len(picked)))
        return make_draw(spec, draw_id, main=tuple(sorted(picked)), bonus=bonus)
    return make_draw(spec, draw_id, main=tuple(picked))


def random_prophecy(spec: GameSpec, draw_id: int, rng: random.Random) -> Prophecy:
    numbers = tuple(sorted(rng.sample(range(1, spec.pool + 1), 12)))
    return make_prophecy(spec, draw_id, numbers)


ALL_GAMES = (POWER655, MEGA645)
