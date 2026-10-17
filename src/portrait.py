"""Портрет слушателя: оси Discovery, Retention, Burnout.

Variability НЕ считается здесь. Приходит в build() готовым числом.

Burnout и Variability в стадии recent_6q намеренно равны значению global:
обе оси отражают всю историю (в дашборде это сказано пользователю,
ui/behavior.py). Текущая Variability (последнее окно rolling-12) лежит
отдельно: variability_meta.parquet['current_score'], панель Time.
Behavior Variability в компас не входит: после детренда она связана
с Burnout (r ≈ -0.76), см. 02_methodology, фазы 9-10.

Публичные функции осей — чтобы kpi_summary мог забрать значения
в свой паркет. Компас и kpi_summary — два независимых потребителя.

База: valid.
"""
import numpy as np
import pandas as pd


# ============================================================================
# DISCOVERY
# ============================================================================

def discovery_global(df_valid: pd.DataFrame,
                     short_history_threshold_months: int = 24):
    """
    Медиана квартального Discovery Rate (только global).

    Холодный старт — первые 4 квартала, если история >= 24 месяцев.

    Returns
    -------
    (value, short_history) : (float, bool)
    """
    valid = df_valid.copy()
    valid['quarter'] = valid['ts_naive'].dt.to_period('Q')
    valid['first_quarter'] = valid['first_valid_seen'].dt.to_period('Q')
    valid['is_new'] = valid['quarter'] == valid['first_quarter']

    total = valid.groupby('quarter')['is_new'].count()
    new = valid.groupby('quarter')['is_new'].sum()
    dr = (new / total * 100).sort_index()

    months = (valid['ts_naive'].max() - valid['ts_naive'].min()).days / 30.44
    if months < short_history_threshold_months:
        short = True
        dr_f = dr
    else:
        short = False
        start_q = valid['ts_naive'].min().to_period('Q') + 4
        dr_f = dr[dr.index >= start_q]

    discovery = dr_f.median() / 100 if len(dr_f) >= 1 else np.nan
    return discovery, short


def discovery_window(df_valid: pd.DataFrame, start, end) -> float:
    """Discovery Rate для конкретного окна."""
    valid = df_valid[
        (df_valid['ts_naive'] >= start) & (df_valid['ts_naive'] <= end)
    ].copy()
    valid['quarter'] = valid['ts_naive'].dt.to_period('Q')
    valid['first_quarter'] = valid['first_valid_seen'].dt.to_period('Q')
    valid['is_new'] = valid['quarter'] == valid['first_quarter']
    total = valid.groupby('quarter')['is_new'].count()
    new = valid.groupby('quarter')['is_new'].sum()
    dr = (new / total * 100).sort_index()
    return dr.median() / 100 if len(dr) >= 2 else np.nan


# ============================================================================
# RETENTION
# ============================================================================

def retention_90(df_valid: pd.DataFrame) -> float:
    """Доля новых треков, вернувшихся в течение 90 дней."""
    if df_valid.empty:
        return np.nan
    last_date = df_valid['ts_naive'].max()
    cutoff = last_date - pd.Timedelta(days=90)

    first_events = df_valid[
        df_valid['ts_naive'] == df_valid['first_valid_seen']
    ].copy()
    first_events = first_events[first_events['first_valid_seen'] <= cutoff]
    if first_events.empty:
        return np.nan

    repeats = df_valid[df_valid['ts_naive'] > df_valid['first_valid_seen']].copy()
    repeats_90 = repeats[
        repeats['ts_naive'] <= repeats['first_valid_seen'] + pd.Timedelta(days=90)
    ]
    returned = set(repeats_90['spotify_track_uri'].unique())

    novel = first_events.drop_duplicates('spotify_track_uri')
    novel['returned_90'] = novel['spotify_track_uri'].isin(returned)
    return novel['returned_90'].mean()


# ============================================================================
# BURNOUT
# ============================================================================

def burnout(df_valid: pd.DataFrame) -> float:
    """Доля core-треков (>=5 плейев), не слушавшихся 12+ месяцев."""
    track_counts = df_valid.groupby('spotify_track_uri').size()
    core = track_counts[track_counts >= 5].index
    if len(core) == 0:
        return np.nan
    last_date = df_valid['ts_naive'].max()
    last_seen = df_valid[
        df_valid['spotify_track_uri'].isin(core)
    ].groupby('spotify_track_uri')['ts_naive'].max()
    months_since = (last_date - last_seen).dt.days / 30.44
    return (months_since > 12).mean()


# ============================================================================
# ОРКЕСТРАТОРЫ
# ============================================================================

def build_axes(df: pd.DataFrame,
               windows: dict) -> dict:
    """
    Считает три оси портрета (без Variability).

    Returns
    -------
    {
        'global':    {'Discovery': ..., 'Retention': ..., 'Burnout': ...,
                      'short_history': bool},
        'recent_6q': {'Discovery': ..., 'Retention': ..., 'Burnout': ...,
                      'short_history': False},
    }
    """
    df_valid = df[df['valid_play']].copy()

    discovery_global_val, short_history = discovery_global(df_valid)
    retention_global_val = retention_90(df_valid)
    burnout_val = burnout(df_valid)

    start_6q, end_6q = windows['recent_6q']
    discovery_6q_val = discovery_window(df_valid, start_6q, end_6q)

    df_valid_6q = df_valid[
        (df_valid['ts_naive'] >= start_6q) &
        (df_valid['ts_naive'] <= end_6q)
    ]
    retention_6q_val = retention_90(df_valid_6q)

    return {
        'global': {
            'Discovery':     discovery_global_val,
            'Retention':     retention_global_val,
            'Burnout':       burnout_val,
            'short_history': short_history,
        },
        'recent_6q': {
            'Discovery':     discovery_6q_val,
            'Retention':     retention_6q_val,
            'Burnout':       burnout_val,
            'short_history': False,
        },
    }


def build(df: pd.DataFrame,
          windows: dict,
          output_path,
          variability_score: float) -> pd.DataFrame:
    """
    Строит portrait.parquet (без level и thresholds).

    Variability передаётся снаружи как готовое число.
    """
    axes = build_axes(df, windows)

    rows = []
    for stage in ['global', 'recent_6q']:
        for axis in ['Discovery', 'Retention', 'Burnout']:
            rows.append({
                'axis':          axis,
                'value':         axes[stage][axis],
                'short_history': axes[stage]['short_history'],
                'stage':         stage,
            })
        rows.append({
            'axis':          'Variability',
            'value':         variability_score,
            'short_history': axes[stage]['short_history'],
            'stage':         stage,
        })

    portrait = pd.DataFrame(rows)
    portrait.to_parquet(output_path / 'portrait.parquet', index=False)
    return portrait