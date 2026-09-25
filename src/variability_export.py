"""Экспорт результатов Variability в parquet для дашборда.

Принимает результат run_variability_pipeline (не считает заново).
Пишет 4 файла в out_dir:
    variability.parquet          — month, score
    variability_meta.parquet     — lifetime/current, null-границы, short_history
    feature_contributions.parquet — period_to, feature, contribution
    epochs_sound.parquet         — start, end, duration_months, ...

При short_history=True пишет пустые файлы с правильной схемой —
дашборд проверяет флаг в meta и не рисует панель.
"""
from pathlib import Path
import pandas as pd


def export_variability(R: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    short = R.get('short_history', False)

    # --- 1. variability.parquet ---
    if short or R.get('rolling_series') is None:
        var_df = pd.DataFrame(columns=['period', 'score'])
    else:
        rolling = R['rolling_series']
        var_df = pd.DataFrame({
            'period': rolling.index.astype(str),
            'score': rolling.values,
        })
    p_var = out_dir / 'variability.parquet'
    var_df.to_parquet(p_var, index=False)

    # --- 2. variability_meta.parquet ---
    meta = pd.DataFrame([{
        'short_history':          short,
        'n_transitions':          R.get('n_transitions'),
        'n_valid_rolling_points': R.get('n_valid_rolling_points'),
        'window':                 R['window'],
        'seed':                   R['seed'],
        'n_boot_transitions':     R.get('n_boot_transitions'),
        'n_boot_score':           R.get('n_boot_score'),
        'lifetime_score':         R.get('lifetime_score'),
        'current_score':          R.get('current_score'),
        'null_low':               R.get('null_low'),
        'null_high':              R.get('null_high'),
    }])
    
    p_meta = out_dir / 'variability_meta.parquet'
    meta.to_parquet(p_meta, index=False)

    # --- 3. feature_contributions.parquet ---
    if R.get('feature_contributions'):
        contrib = pd.DataFrame(R['feature_contributions'])
    else:
        contrib = pd.DataFrame(
            columns=['period_to', 'feature', 'contribution'])
    p_contrib = out_dir / 'feature_contributions.parquet'
    contrib.to_parquet(p_contrib, index=False)

    # --- 4. epochs_sound.parquet ---
    if R.get('epochs'):
        epochs = pd.DataFrame(R['epochs'])
    else:
        epochs = pd.DataFrame(columns=[
            'start', 'end', 'duration_months', 'max_score', 'mean_score'])
    p_epochs = out_dir / 'epochs_sound.parquet'
    epochs.to_parquet(p_epochs, index=False)

    return {
        'variability':           p_var,
        'meta':                  p_meta,
        'feature_contributions': p_contrib,
        'epochs_sound':          p_epochs,
    }