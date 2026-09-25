"""Variability pipeline: обёртка над variability_toolkit.

Только Sound. Behavior не считаем — не идёт в дашборд.
Вход: event-level df (Period колонка 'month').
Выход: dict со score, level, epochs, feature contributions.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from detectors.variability_toolkit import VariabilityAnalyzer

SOUND_FEATURES = ['valence', 'energy', 'danceability',
                  'instrumentalness', 'acousticness', 'tempo']

DEFAULT_WINDOW  = 12
DEFAULT_N_BOOT  = 200
DEFAULT_SEED    = 42
DEFAULT_PCT     = 75
EPOCH_THRESHOLD = 0.5
EPOCH_MIN_MONTHS = 2

__all__ = ['run_variability_pipeline']


def _find_epochs(rolling: pd.Series,
                 threshold: float = EPOCH_THRESHOLD,
                 min_months: int = EPOCH_MIN_MONTHS) -> list:
    """Непрерывные участки rolling > threshold длиной ≥ min_months."""
    if rolling.empty:
        return []
    mask = (rolling > threshold).fillna(False).values
    periods = pd.PeriodIndex(rolling.index, freq='M')

    epochs = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            start = i
            while i < n and mask[i]:
                i += 1
            end = i - 1
            length = end - start + 1
            if length >= min_months:
                seg = rolling.iloc[start:end + 1]
                epochs.append({
                    'start': str(periods[start]),
                    'end': str(periods[end]),
                    'duration_months': int(length),
                    'max_score': float(seg.max()),
                    'mean_score': float(seg.mean()),
                })
        else:
            i += 1
    return epochs


def run_variability_pipeline(df: pd.DataFrame,
                             monthly_sound: pd.DataFrame | None = None,
                             *, window: int = DEFAULT_WINDOW,
                             n_boot: int = DEFAULT_N_BOOT,
                             seed: int = DEFAULT_SEED,
                             percentile: int = DEFAULT_PCT) -> dict:
    """
    df: event-level, одна строка на событие, колонка 'month' (Period).
    monthly_sound: если None — строится из df.
    """
    df = df.copy()
    if 'month' not in df.columns:
        df['month'] = df['ts_naive'].dt.to_period('M')

    if monthly_sound is None:
        monthly_sound = (df.groupby('month')[SOUND_FEATURES]
                          .median().sort_index())

    # Практические пороги: p75 сырых сдвигов месячных медиан
    practical = (monthly_sound[SOUND_FEATURES].diff().abs()
                 .quantile(percentile / 100).to_dict())

    analyzer = VariabilityAnalyzer(
        period_col='month',
        value_cols=SOUND_FEATURES,
        agg='median',
        n_boot=n_boot,
        p_low=75,
        p_high=99,
        min_obs_per_period=5,
        practical_thresholds=practical,
        min_practical_features=2,
        random_state=seed,
    )
    analyzer.fit(df)

    sc = analyzer.variability_score(window=window, n_boot=500)
    rolling = sc['rolling_series']          # index: str 'YYYY-MM'

    # Эпохи
    epochs = _find_epochs(rolling)

    # Feature contributions для всех High-переходов
    high = analyzer.transitions_[
        analyzer.transitions_['label'] == 'High'
    ].index.tolist()
    contrib_rows = []
    for p in high:
        try:
            c = analyzer.feature_contributions(p)
            for feat, val in c.items():
                contrib_rows.append({
                    'period_to': p, 'feature': feat,
                    'contribution': float(val),
                })
        except (KeyError, RuntimeError):
            continue

    return {
        'lifetime_score': float(sc['lifetime_score']),
        'lifetime_level': sc['lifetime_level'],
        'current_score':  float(sc['current_score']),
        'current_level':  sc['current_level'],
        'null_low':       float(sc['null_low']),
        'null_high':      float(sc['null_high']),
        'rolling_series': rolling,
        'transitions':    analyzer.transitions_,
        'epochs':         epochs,
        'feature_contributions': contrib_rows,
        'window': window,
        'seed':   seed,
        'n_boot': n_boot,
    }