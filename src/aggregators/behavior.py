"""Aggregators: поведение.

Свёртка событий в поведенческие агрегаты + obsession-логика.

Секции:
    1. Константы (BEHAVIOR_FEATURES_PELT, BEHAVIOR_CLUSTERS)
    2. Сессии (session_stats)
    3. Obsessions (is_obsession_event, build_strong_obsessions, build_obsession_base)
    4. Агрегаты (build_monthly_behavior)

Базы: PELT-B использует all (skip_rate/played_frac мертвы на valid).
Obsessions — тоже all.
"""
import numpy as np
import pandas as pd

from enrich import add_sessions


# ============================================================================
# 1. КОНСТАНТЫ
# ============================================================================

# Финальный набор для PELT-B: 4 сглаженных + 2 сырых.
# desktop_share исключён (структурный скачок, не разладка).
BEHAVIOR_FEATURES_PELT = ['hours', 'tracks_smooth', 'skip_rate_smooth',
                          'played_frac_smooth', 'obsession_share',
                          'discovery_rate_smooth']

# Кластеры признаков для голосования (используется в Variability behavior,
# отложено).
BEHAVIOR_CLUSTERS = {
    'volume':     ['hours', 'tracks'],
    'completion': ['skip_rate', 'played_frac'],
    'obsession':  ['obsession_share'],
}


# ============================================================================
# 2. СЕССИИ
# ============================================================================

def session_stats(df_with_sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Агрегат по сессиям: длительность, число событий, тип, период.

    Требует результат add_sessions (колонки session_id, gap_min).

    Возвращает DataFrame с колонками:
        account, session_id, start_ts, end_ts, n_events,
        duration_min, max_gap, session_type, period
    """
    stats = df_with_sessions.groupby(['account', 'session_id']).agg(
        start_ts=('ts_naive', 'min'),
        end_ts=('ts_naive', 'max'),
        n_events=('ts_naive', 'count'),
        first_ms=('ms_played', 'first'),
    ).reset_index()

    stats['duration_min'] = (
        (stats['end_ts'] - stats['start_ts']).dt.total_seconds() / 60
        + stats['first_ms'] / 60000
    )

    # Максимальный разрыв внутри сессии (кроме первого события)
    max_gap = (
        df_with_sessions.groupby(['account', 'session_id'])['gap_min']
        .apply(lambda x: x.iloc[1:].max() if len(x) > 1 else 0)
    )
    stats['max_gap'] = stats.set_index(['account', 'session_id']).index.map(max_gap)

    # continuous, если макс. разрыв <= 10 мин, иначе interrupted
    stats['session_type'] = np.where(
        stats['max_gap'] > 10, 'interrupted', 'continuous'
    )
    stats['period'] = stats['start_ts'].dt.to_period('M')

    return stats


# ============================================================================
# 3. OBSESSIONS
# ============================================================================

def is_obsession_event(df: pd.DataFrame) -> pd.Series:
    """
    Флаг obsession на КАЖДОЕ событие.

    Пара (session, track) — obsession, если одновременно:
        count >= 3 И share >= 0.10 (share = count / n_events в сессии).

    add_sessions сортирует df. Чтобы флаг попал на ПРАВИЛЬНУЮ строку,
    сохраняем _row_id до сортировки и восстанавливаем порядок в конце.

    Возвращает pd.Series bool с именем 'is_base_obsession_event'.
    Индекс — как у df.
    """
    s = df.copy()
    s['_row_id'] = np.arange(len(s))
    s = add_sessions(s)

    pair = (s.groupby(['account', 'session_id', 'spotify_track_uri'])
              .size().rename('count').reset_index())
    total = (s.groupby(['account', 'session_id'])
               .size().rename('n_events').reset_index())
    pair = pair.merge(total, on=['account', 'session_id'])
    pair['share'] = pair['count'] / pair['n_events']
    pair['is_obsession_episode'] = (
        (pair['count'] >= 3) & (pair['share'] >= 0.10)
    )

    merged = s.merge(
        pair[['account', 'session_id', 'spotify_track_uri',
              'is_obsession_episode']],
        on=['account', 'session_id', 'spotify_track_uri'],
        how='left',
    )
    merged = merged.sort_values('_row_id').reset_index(drop=True)
    merged.index = df.index

    return merged['is_obsession_episode'].fillna(False).rename(
        'is_base_obsession_event'
    )


def build_strong_obsessions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Серии >= 5 повторов ПОДРЯД одного трека в одной сессии.

    Streak — строго подряд, без других треков между.
    База — все события.

    Возвращает DataFrame:
        track_uri | track_name | artist_name | date | repeats | hours
    date — timestamp начала месяца пика.
    """
    s = add_sessions(df)
    s = s.sort_values(
        ['account', 'session_id', 'ts_naive']
    ).reset_index(drop=True)

    s['prev_uri'] = (s.groupby(['account', 'session_id'])
                       ['spotify_track_uri'].shift(1))
    s['same_as_prev'] = (s['spotify_track_uri'] == s['prev_uri'])

    s['new_series'] = (~s['same_as_prev']).astype(int)
    s['series_id'] = s['new_series'].cumsum()

    series = s.groupby('series_id').agg(
        track_uri=('spotify_track_uri', 'first'),
        repeats=('series_id', 'size'),
        start_ts=('ts_naive', 'min'),
        total_ms=('ms_played', 'sum'),
    )

    strong = series[series['repeats'] >= 5].copy()
    strong['date'] = strong['start_ts'].dt.to_period('M').dt.start_time

    track_info = (df.drop_duplicates('spotify_track_uri')
                    .set_index('spotify_track_uri')
                    [['track_name', 'artist_name']])
    strong = strong.merge(
        track_info, left_on='track_uri', right_index=True, how='left'
    )
    strong['hours'] = strong['total_ms'] / 3600000

    cols = ['track_uri', 'track_name', 'artist_name',
            'date', 'repeats', 'hours']
    return strong[cols].reset_index(drop=True)


def build_obsession_base(df: pd.DataFrame, freq: str = 'M') -> pd.DataFrame:
    """
    Доля obsession-событий по периодам.

    obsesssion_share = доля событий периода, попавших в obsession-пары
    (count>=3 & share>=0.10).

    Параметры
    ---------
    df : pd.DataFrame
        Обогащённый df (valid_play, period, ts_naive).
    freq : 'M' | 'W' | 'D'
        Частота периодов.

    Возвращает DataFrame с колонками: date, obsession_share.
    """
    df_local = df.copy()
    df_local['is_base_obsession_event'] = is_obsession_event(df_local)
    df_local['agg_period'] = df_local['ts_naive'].dt.to_period(freq)

    share = (df_local
             .groupby('agg_period')['is_base_obsession_event']
             .mean()
             .reset_index(name='obsession_share'))
    share['date'] = share['agg_period'].dt.to_timestamp()
    return share[['date', 'obsession_share']].sort_values('date')


# ============================================================================
# 4. АГРЕГАТЫ
# ============================================================================

def build_monthly_behavior(df: pd.DataFrame) -> pd.DataFrame:
    """
    Поведенческие признаки по месяцам.

    Признаки:
        hours, tracks, skip_rate, played_frac,
        obsession_share (event-level),
        discovery_rate (по first_valid_seen, всегда valid-база внутри)

    Плюс сглаженные версии (rolling 3 мес) для PELT-B:
        tracks_smooth, skip_rate_smooth, played_frac_smooth,
        discovery_rate_smooth

    Возвращает DataFrame с индексом period (Period 'M').
    """
    df = df.copy()

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

    # --- Obsession (event-level) ---
    df_obs = df.copy()
    df_obs['is_base_obsession_event'] = is_obsession_event(df)
    obsession_share = (
        df_obs.groupby('period')['is_base_obsession_event'].mean()
        .rename('obsession_share')
    )

    # --- Агрегаты по месяцу ---
    monthly = df.groupby('period').agg(
        hours=('ms_played', lambda x: x.sum() / 3_600_000),
        tracks=('spotify_track_uri', 'nunique'),
        skip_rate=('is_skip', 'mean'),
        played_frac=('played_frac', 'mean'),
    )
    monthly = monthly.join(obsession_share, how='left')
    monthly = monthly.join(discovery_rate, how='left')
    monthly = monthly.sort_index()
    monthly['date'] = monthly.index.to_timestamp()

    # --- Сглаженные версии для PELT-B ---
    for f in ['tracks', 'skip_rate', 'played_frac', 'discovery_rate']:
        monthly[f'{f}_smooth'] = (
            monthly[f].rolling(3, center=True, min_periods=2).mean()
        )

    return monthly