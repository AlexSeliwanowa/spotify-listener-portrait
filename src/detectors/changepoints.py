"""Сборка всех слоёв детекции в time_changepoints.parquet + time_storms.parquet.

Один раз вызывает все 4 детектора, объединяет результат.
"""
import pandas as pd

from temporal import trim_cold_start
from aggregators.music import build_monthly_sound
from aggregators.behavior import build_monthly_behavior
from detectors import pelt_sound, pelt_behavior, cosine_identity, storm

def build(df: pd.DataFrame, output_path) -> tuple:
    """
    Собирает все слои и сохраняет два файла:
        - time_changepoints.parquet: date | method | layer | confidence
        - time_storms.parquet: date | std_all | is_storm | episode_id

    Возвращает (changepoints_df, storms_df).
    """
    df_t = trim_cold_start(df)
    monthly_sound = build_monthly_sound(df_t)
    monthly_behavior = build_monthly_behavior(df_t)

    # --- Все детекторы ---
    res_sound = pelt_sound.detect(monthly_sound)
    res_behavior = pelt_behavior.detect(monthly_behavior)
    res_cosine = cosine_identity.detect(df_t, id_col='artist_name')
    res_storm = storm.detect(monthly_sound)

    # --- Сборка точек ---
    STABILITY_MIN = 0.10

    rows = []
    for p in res_sound['points']:
        conf = res_sound['stability'].get(p, 0)
        if conf < STABILITY_MIN:
            continue
        rows.append({
            'date': p, 'method': 'pelt_sound', 'layer': 'sound',
            'confidence': round(conf, 3),
        })
    for p in res_behavior['points']:
        conf = res_behavior['stability'].get(p, 0)
        if conf < STABILITY_MIN:
            continue
        rows.append({
            'date': p, 'method': 'pelt_behavior', 'layer': 'behavior',
            'confidence': round(conf, 3),
        })
    for p in res_cosine['points']:
        conf = res_cosine['stability'].get(p, 0)
        if conf < STABILITY_MIN:
            continue
        rows.append({
            'date': p, 'method': 'cosine_identity', 'layer': 'identity',
            'confidence': round(conf, 3),
        })

    changepoints = pd.DataFrame(rows).sort_values('date').reset_index(drop=True)
    changepoints.to_parquet(output_path / 'time_changepoints.parquet', index=False)

    storms = res_storm['df']
    storms.to_parquet(output_path / 'time_storms.parquet', index=False)

    return changepoints, storms