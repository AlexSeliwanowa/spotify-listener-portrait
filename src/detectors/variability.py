"""Variability pipeline: обёртка над variability_toolkit.

Только Sound. Behavior не считаем — не идёт в дашборд.
Вход: event-level df (Period колонка 'month').
Выход: dict со score, epochs, feature contributions.

Level считается в дашборде по порогам из indices_display.json.

Требует ≥ 24 полных transitions (MIN_TRANSITIONS_FOR_VARIABILITY).
Иначе — short_history=True, метрики не считаются.

Что изменилось
1. Константа MIN_TRANSITIONS_FOR_VARIABILITY = 24.

2. Проверка после fit.
Если n_transitions < 24 → возвращает short_history=True, все метрики None, epochs пустой.

3. variability_score с min_periods=window.
Полное окно. Эпохи сравнимы. Убирает артефакты коротких окон.

4. n_transitions в возврате.
Дашборд может показать «у тебя X месяцев, нужно 24».

5. short_history в возврате.
Флаг для дашборда.
"""
from __future__ import annotations

import pandas as pd

from detectors.variability_toolkit import VariabilityAnalyzer


SOUND_FEATURES = ['valence', 'energy', 'danceability',
                  'instrumentalness', 'acousticness', 'tempo']

DEFAULT_WINDOW   = 12
DEFAULT_N_BOOT   = 200
DEFAULT_SEED     = 42
DEFAULT_PCT      = 75
EPOCH_THRESHOLD  = 0.5
EPOCH_MIN_MONTHS = 2

# Порог входа: минимум полных transitions для устойчивой rolling-медианы.
# При window=12: 24-12+1 = 13 валидных точек (было 7 при пороге 18).
# Обоснование в methodology_behavior_compass.md.
MIN_TRANSITIONS_FOR_VARIABILITY = 24

__all__ = ['run_variability_pipeline', 'MIN_TRANSITIONS_FOR_VARIABILITY']


def _find_epochs(rolling: pd.Series,
                 threshold: float = EPOCH_THRESHOLD,
                 min_months: int = EPOCH_MIN_MONTHS) -> list:
    """Непрерывные участки rolling > threshold длиной >= min_months."""
    if rolling.empty:
        return []

    periods = pd.PeriodIndex(rolling.index, freq='M')
    mask = (rolling > threshold).fillna(False).values

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
                             *,
                             window: int = DEFAULT_WINDOW,
                             n_boot_transitions: int = DEFAULT_N_BOOT,
                             n_boot_score: int = 500,
                             seed: int = DEFAULT_SEED,
                             percentile: int = DEFAULT_PCT) -> dict:
    """
    df: event-level, одна строка на событие, колонка 'month' (Period).
    monthly_sound: если None — строится из df.
    
        Возвращает dict. Ключевые поля:
      - lifetime_score   — медиана rolling-12
      - current_score    — последняя точка rolling-12
      - null_low/high    — границы permutation-null
      - epochs, transitions, feature_contributions

    # current_score — последнее значение rolling-12 (последние 12 мес).
    # Показывается в панели Variability на вкладке Time; в компасе
    # (portrait.parquet) не используется: там Variability = lifetime.
    """
    df = df.copy()
    if 'period' not in df.columns:
        df['period'] = df['ts_naive'].dt.to_period('M')

    if monthly_sound is None:
        monthly_sound = (df.groupby('period')[SOUND_FEATURES]                          .median().sort_index())

    # Практические пороги: p75 сырых сдвигов месячных медиан
    practical = (monthly_sound[SOUND_FEATURES].diff().abs()
                 .quantile(percentile / 100).to_dict())

    analyzer = VariabilityAnalyzer(
        period_col='period',
        value_cols=SOUND_FEATURES,
        agg='median',
        n_boot=n_boot_transitions,
        p_low=75,
        p_high=99,
        min_obs_per_period=5,
        practical_thresholds=practical,
        min_practical_features=2,
        random_state=seed,
    )
    analyzer.fit(df)

    n_transitions = len(analyzer.transitions_)

    # ---------- Короткая история — метрики не считаем ----------
    if n_transitions < MIN_TRANSITIONS_FOR_VARIABILITY:
        return {
            'short_history': True,
            'n_transitions': n_transitions,
            'n_valid_rolling_points': None,
            'lifetime_score': None,
            'current_score': None,
            'null_low': None,
            'null_high': None,
            'rolling_series': None,
            'transitions': analyzer.transitions_,
            'epochs': [],
            'feature_contributions': [],
            'window': window,
            'seed': seed,
            'n_boot_transitions': n_boot_transitions,
            'n_boot_score': n_boot_score,
        }

    # ---------- Полная история ----------
    sc = analyzer.variability_score(
        window=window,
        n_boot=n_boot_score,
        min_periods=window,   # полное окно — эпохи сравнимы
    )
    rolling = sc['rolling_series']

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
                    'period_to': p,
                    'feature': feat,
                    'contribution': float(val),
                })
        except (KeyError, RuntimeError):
            continue

    return {
        'short_history': False,
        'n_transitions': n_transitions,
        'n_valid_rolling_points': int(rolling.notna().sum()),
        'lifetime_score': float(sc['lifetime_score']),
        'current_score':  float(sc['current_score']),
        'null_low':       float(sc['null_low']),
        'null_high':      float(sc['null_high']),
        'rolling_series': rolling,
        'transitions':    analyzer.transitions_,
        'epochs':         epochs,
        'feature_contributions': contrib_rows,
        'window': window,
        'seed':   seed,
        'n_boot_transitions': n_boot_transitions,
        'n_boot_score': n_boot_score,
    }