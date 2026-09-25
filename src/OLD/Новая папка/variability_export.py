"""Экспорт результатов Variability в parquet для дашборда."""
from pathlib import Path
import pandas as pd
from variability import run_variability_pipeline

def export_variability(df, monthly_sound, out_dir: Path,
                       window: int = 12, seed: int = 42) -> dict:
    """
    Прогоняет пайплайн и сохраняет:
        variability.parquet        — по месяцам: sound/behavior/levels
        variability_events.parquet — бинарные события по месяцам
        variability_meta.parquet   — сводка: p-value, калибровка, окно

    Возвращает dict с путями.
    """
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)

    R = run_variability_pipeline(df, monthly_sound,
                                 window=window, seed=seed)

    # --- по месяцам ---
    idx = R['events_sound'].index
    var = pd.DataFrame({
        'month':               idx.astype(str),
        'sound_variability':   R['variability_sound'].values,
        'behavior_variability':R['variability_behavior'].values,
        'sound_level':         R['labels_sound'].values,
        'behavior_level':      R['labels_behavior'].values,
    })
    p_var = out_dir / 'variability.parquet'
    var.to_parquet(p_var, index=False)

    # --- события ---
    ev = pd.DataFrame({
        'month':            idx.astype(str),
        'sound_high':       R['events_sound'].values,
        'behavior_high':    R['events_behavior'].values,
    })
    p_ev = out_dir / 'variability_events.parquet'
    ev.to_parquet(p_ev, index=False)

    # --- мета ---
    meta = pd.DataFrame([{
        'window':            R['window'],
        'seed':              R['seed'],
        'sound_p_event':     float(R['events_sound'].mean()),
        'behavior_p_event':  float(R['events_behavior'].mean()),
        'sound_binom_p':     R['binom_sound']['p_value'],
        'behavior_binom_p':  R['binom_behavior']['p_value'],
        'sound_n_above':     R['binom_sound']['n_above'],
        'behavior_n_above':  R['binom_behavior']['n_above'],
        'sound_clustered':   bool(R['binom_sound']['p_value'] < 0.05),
        'behavior_clustered':bool(R['binom_behavior']['p_value'] < 0.05),
    }])
    p_meta = out_dir / 'variability_meta.parquet'
    meta.to_parquet(p_meta, index=False)

    return {'variability': p_var, 'events': p_ev, 'meta': p_meta}