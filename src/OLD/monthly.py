"""Построение monthly-рядов для детекторов разладок.

- build_monthly_sound: медианы звуковых признаков по месяцам
- build_monthly_behavior: поведенческие признаки + сессии + обсессии + discovery
- trim_cold_start: отрезает холодный старт по правилу gap > 1 мес
"""
import numpy as np
import pandas as pd
from common import add_sessions, session_stats, is_obsession_event
from common import add_sessions, session_stats, build_obsession_session_flag


SOUND_FEATURES = ['valence', 'energy', 'danceability', 'instrumentalness',
                  'acousticness', 'tempo']

BEHAVIOR_FEATURES_RAW = ['hours', 'tracks', 'skip_rate', 'played_frac',
                         'obsession_share', 'discovery_rate']

# Финальный набор для PELT-B (после SNR): 4 сглаженных + 2 сырых
BEHAVIOR_FEATURES_PELT = ['hours', 'tracks_smooth', 'skip_rate_smooth',
                          'played_frac_smooth', 'obsession_share',
                          'discovery_rate_smooth']


def trim_cold_start(df: pd.DataFrame, gap_months: int = 1) -> pd.DataFrame:
    """
    Отрезает неполный последний месяц и холодный старт.

    Правило: если в первый год есть gap > gap_months без событий —
    история начинается после последнего такого gap.
    """
    df = df.copy()

    # Канонический период. Обычно создан в Cell 1, но fallback — на случай
    # вызова на голом df (тесты, отдельные скрипты).
    if 'period' not in df.columns:
        df['period'] = df['ts_naive'].dt.to_period('M')

    # Неполный последний месяц
    max_date = df['ts_naive'].max()
    last_month = max_date.to_period('M')
    if max_date.day < last_month.days_in_month:
        df = df[df['period'] < last_month]

    # Gap в первый год
    months_present = sorted(df['period'].unique())
    if not months_present:
        return df

    first_month = months_present[0]
    first_year_end = first_month + 12
    cutoff = None
    for i in range(1, len(months_present)):
        gap = (months_present[i] - months_present[i-1]).n
        if gap > gap_months and months_present[i] < first_year_end:
            cutoff = months_present[i]

    if cutoff is not None:
        df = df[df['period'] >= cutoff]

    return df


def build_monthly_sound(df: pd.DataFrame) -> pd.DataFrame:
    """Медианы звуковых признаков по месяцам. Index = Period('M')."""
    monthly = df.groupby('period').agg(
        **{f: (f, 'median') for f in SOUND_FEATURES}
    ).reset_index()
    monthly['date'] = monthly['period'].dt.to_timestamp()
    monthly = monthly.set_index('period').sort_index()
    return monthly


def build_monthly_behavior(df: pd.DataFrame) -> pd.DataFrame:
    """
    Поведенческие признаки по месяцам + event-level obsession_share + discovery.

    Возвращает DataFrame с колонками:
        hours, tracks, skip_rate, played_frac, obsession_share, discovery_rate
        + *_smooth версии для PELT-B
    """
    df = add_sessions(df)
    sessions = session_stats(df)

    # --- Обсессии event-level (единая формула на весь проект) ---
    # Флаг на событие: попало ли в obsession-пару (count>=3 & share>=0.10).
    # Агрегат: доля событий месяца.
    df_obs = df.copy()
    df_obs['is_base_obsession_event'] = is_obsession_event(df)
    obsession_share = (
        df_obs.groupby('period')['is_base_obsession_event'].mean()
        .rename('obsession_share')
    )

    # --- Discovery (всегда на valid-базе, независимо от df) ---
    df_valid_local = df[df['valid_play']].copy()

    first_valid_month = (
        df_valid_local.groupby('spotify_track_uri')['first_valid_seen'].min()
        .dt.to_period('M').reset_index(name='first_valid_month')
    )
    df_valid_local = df_valid_local.merge(
        first_valid_month, on='spotify_track_uri', how='left'
    )
    df_valid_local['is_discovery'] = (
        df_valid_local['period'] == df_valid_local['first_valid_month']
    )
    discovery_rate = (
        df_valid_local.groupby('period')['is_discovery'].mean()
        .rename('discovery_rate')
    )

    # --- Агрегаты ---
    monthly = df.groupby('period').agg(
        hours=('ms_played', lambda x: x.sum() / 3600000),
        tracks=('spotify_track_uri', 'nunique'),
        skip_rate=('is_skip', 'mean'),
        played_frac=('played_frac', 'mean'),
    ).reset_index()

    monthly = monthly.merge(obsession_share.reset_index(), on='period', how='left')
    monthly = monthly.merge(discovery_rate.reset_index(), on='period', how='left')
    monthly['date'] = monthly['period'].dt.to_timestamp()
    monthly = monthly.set_index('period').sort_index()
    
    # --- Сглаженные версии для PELT-B ---
    for f in ['tracks', 'skip_rate', 'played_frac', 'discovery_rate']:
        monthly[f'{f}_smooth'] = (
            monthly[f].rolling(3, center=True, min_periods=2).mean()
        )

    return monthly