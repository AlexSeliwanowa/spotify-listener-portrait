from pathlib import Path

import pandas as pd
import pytest

from config import load_config
from data.loaders import DASHBOARD_PATH
from data.schemas import get_required_columns, validate


EXPECTED_PARQUETS = [
    'sound/sound_clustering_meta.parquet',
    'sound/sound_core_global.parquet',
    'sound/sound_core_recent_6q.parquet',
    'sound/sound_core_last_90d.parquet',

    'time/epochs_sound.parquet',
    'time/feature_contributions.parquet',
    'time/time_changepoints.parquet',
    'time/time_series_global.parquet',
    'time/time_series_recent_6q.parquet',
    'time/time_series_last_90d.parquet',
    'time/time_series_meta.parquet',
    'time/time_storms.parquet',
    'time/variability.parquet',
    'time/variability_meta.parquet',

    'behavior/behavior_cohorts.parquet',
    'behavior/behavior_funnel_events.parquet',
    'behavior/behavior_funnel_tracks.parquet',
    'behavior/behavior_skip_by_genre.parquet',
    'behavior/behavior_skip_by_source.parquet',
    'behavior/obsessions_base_global.parquet',
    'behavior/obsessions_base_recent_6q.parquet',
    'behavior/obsessions_base_last_90d.parquet',
    'behavior/obsessions_strong.parquet',
    'behavior/portrait.parquet',

    'collection/collection_activity_scatter.parquet',
    'collection/collection_fill_summary.parquet',
    'collection/playlist_collaborators.parquet',
    'collection/playlist_portraits.parquet',

    'kpi_summary.parquet',
]


def test_all_parquets_exist():
    """Все 29 паркетов дашборда на месте."""
    missing = []
    for rel_path in EXPECTED_PARQUETS:
        if not (DASHBOARD_PATH / rel_path).exists():
            missing.append(rel_path)
    assert not missing, f"Missing parquets: {missing}"


def test_all_schemas_pass():
    """Все паркеты со схемой проходят валидацию."""
    failures = []
    for rel_path in EXPECTED_PARQUETS:
        schema = get_required_columns(rel_path)
        if schema is None:
            continue
        df = pd.read_parquet(DASHBOARD_PATH / rel_path)
        missing = validate(df, rel_path)
        if missing:
            failures.append(f"{rel_path}: missing {missing}")
    assert not failures, "Schema mismatches:\n" + "\n".join(failures)


def test_ui_modules_import():
    """Все модули ui/* импортируются."""
    from ui import sound, time, behavior, collection, overview
    for mod in (sound, time, behavior, collection, overview):
        assert hasattr(mod, 'render'), f"{mod.__name__} has no render()"


def test_app_parses():
    """app.py парсится без синтаксических ошибок."""
    import ast
    app_path = Path(__file__).resolve().parents[1] / 'app.py'
    source = app_path.read_text(encoding='utf-8')
    ast.parse(source)