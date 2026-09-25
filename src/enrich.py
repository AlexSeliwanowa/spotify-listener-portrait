"""Enrich: добавляет колонки в df. Не фильтрует строки.

Каждая функция берёт df и возвращает df с новой колонкой.
Строк не убирает, порядок не меняет (кроме add_sessions — там нужна сортировка).

Порядок применения в Cell 1 prep:
    df = add_timestamps(df)                # ts_naive, period
    df = add_valid_play(df)                # valid_play
    df = add_first_valid_seen(df)          # first_valid_seen
    df, my_music_uris = add_my_music(df, library_tracks, playlist_links, owner_ids)
    df = add_sessions(df)                  # session_id, gap_min, new_session
    df = add_track_source(df, library_tracks, playlist_links, owner_ids)

После этого df готов для любых селекторов.
"""
import numpy as np
import pandas as pd


# ============================================================================
# ВРЕМЕННЫЕ ШКАЛЫ
# ============================================================================

def add_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Добавляет ts_naive (без таймзоны) и period (месяц, Period).

    Без этих колонок не работает ничего: ни сессии, ни агрегаты.
    """
    df = df.copy()
    df['ts_naive'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    df['period'] = df['ts_naive'].dt.to_period('M')
    return df


# ============================================================================
# ВАЛИДНОЕ ПРОСЛУШИВАНИЕ
# ============================================================================

EXCLUDE_REASONS = ['trackerror', 'fwdbtn', 'backbtn',
                   'logout', 'remote', 'unexpected-exit']


def add_valid_play(df: pd.DataFrame) -> pd.DataFrame:
    """
    Определение валидного прослушивания (единое на весь проект).

    Событие валидно, если ОДНОВРЕМЕННО:
      - не скип
      - >= 30 секунд
      - played_frac >= 0.5
      - reason_end не из EXCLUDE_REASONS

    Возвращает df с колонкой valid_play (bool).
    """
    df = df.copy()
    df['valid_play'] = (
        (~df['is_skip']) &
        (df['ms_played'] >= 30_000) &
        (~df['reason_end'].isin(EXCLUDE_REASONS)) &
        (df['played_frac'] >= 0.5)
    )
    return df


# ============================================================================
# ПЕРВОЕ ВАЛИДНОЕ ПРОСЛУШИВАНИЕ ТРЕКА
# ============================================================================

def add_first_valid_seen(df: pd.DataFrame) -> pd.DataFrame:
    """
    Для каждого трека — timestamp его первого валидного прослушивания.

    Требует: df['valid_play'], df['ts_naive'].

    Возвращает df с колонкой first_valid_seen (timestamp).
    """
    df = df.copy()
    first_valid_seen = (
        df.loc[df['valid_play']]
          .groupby('spotify_track_uri')['ts_naive']
          .min()
    )
    df['first_valid_seen'] = df['spotify_track_uri'].map(first_valid_seen)
    return df


# ============================================================================
# MY MUSIC
# ============================================================================

def add_my_music(df: pd.DataFrame,
                 library_tracks: pd.DataFrame,
                 playlist_links: pd.DataFrame,
                 owner_ids: pd.DataFrame):
    """
    Помечает треки как «свои»: лайки ∪ свои плейлисты.

    Параметры
    ---------
    df : pd.DataFrame
        Основной df событий.
    library_tracks : pd.DataFrame
        Лайкнутые треки (колонка spotify_track_uri).
    playlist_links : pd.DataFrame
        Связи трек-плейлист (Track URI, Added By).
    owner_ids : pd.DataFrame
        Владельцы (owner_id).

    Возвращает
    ----------
    (df, my_music_uris) : tuple
        df с колонкой my_music (bool)
        my_music_uris — set URI, чтобы переиспользовать в других функциях.
    """
    df = df.copy()

    owner_set = set(owner_ids['owner_id'].dropna())
    liked_uris = set(library_tracks['spotify_track_uri'].dropna())
    own_playlist_uris = set(
        playlist_links[
            playlist_links['Added By'].isin(owner_set)
        ]['Track URI'].dropna().unique()
    )

    my_music_uris = liked_uris | own_playlist_uris
    df['my_music'] = df['spotify_track_uri'].isin(my_music_uris)

    return df, my_music_uris


# ============================================================================
# КЛАССИФИКАЦИЯ ИСТОЧНИКА ТРЕКА
# ============================================================================

def build_uri_sets(playlist_links: pd.DataFrame) -> dict:
    """
    Множества URI по типу плейлиста.

    Возвращает dict:
        personal / collaborative / contributed / foreign → set(URI)
    """
    return {
        'personal': set(playlist_links[
            playlist_links['playlist_type'] == 'personal'
        ]['Track URI'].dropna()),
        'collaborative': set(playlist_links[
            playlist_links['playlist_type'] == 'collaborative'
        ]['Track URI'].dropna()),
        'contributed': set(playlist_links[
            playlist_links['playlist_type'] == 'contributed'
        ]['Track URI'].dropna()),
        'foreign': set(playlist_links[
            playlist_links['playlist_type'] == 'foreign'
        ]['Track URI'].dropna()),
    }


def add_track_source(df: pd.DataFrame,
                     library_tracks: pd.DataFrame,
                     playlist_links: pd.DataFrame,
                     owner_ids: pd.DataFrame) -> pd.DataFrame:
    """
    Классификация источника трека.

    Категории:
        my_music — лайк или свой плейлист
        foreign  — из чужого или contributed плейлиста
        orphan   — ни там, ни там

    Возвращает df с колонкой source (строка).
    """
    df = df.copy()

    owner_set = set(owner_ids['owner_id'].dropna())
    liked_uris = set(library_tracks['spotify_track_uri'].dropna())
    own_playlist_uris = set(
        playlist_links[
            playlist_links['Added By'].isin(owner_set)
        ]['Track URI'].dropna().unique()
    )
    uri_sets = build_uri_sets(playlist_links)
    foreign_all = uri_sets['foreign'] | uri_sets['contributed']

    def _track_source(uri):
        if uri in liked_uris or uri in own_playlist_uris:
            return 'my_music'
        if uri in foreign_all:
            return 'foreign'
        return 'orphan'

    df['source'] = df['spotify_track_uri'].apply(_track_source)
    return df


# ============================================================================
# СЕССИИ
# ============================================================================

def add_sessions(df: pd.DataFrame, gap_min: int = 30) -> pd.DataFrame:
    """
    Разбивает события на сессии: разрыв > gap_min минут = новая сессия.

    ВНИМАНИЕ: сортирует df по (account, ts_naive) и делает reset_index.
    Если нужна привязка колонок к исходным строкам — сохраняйте row_id
    до вызова (см. is_obsession_event в aggregators/behavior.py).

    Возвращает df с колонками:
        prev_ts      — время предыдущего события (в рамках account)
        gap_min      — минут между событиями
        new_session  — bool, начало новой сессии
        session_id   — номер сессии (в рамках account)
    """
    df = df.sort_values(['account', 'ts_naive']).reset_index(drop=True).copy()
    df['prev_ts'] = df.groupby('account')['ts_naive'].shift(1)
    df['gap_min'] = (df['ts_naive'] - df['prev_ts']).dt.total_seconds() / 60
    df['new_session'] = (df['gap_min'].isna()) | (df['gap_min'] > gap_min)
    df['session_id'] = df.groupby('account')['new_session'].cumsum()
    return df


def session_stats(df_with_sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Агрегат по сессиям: длительность, число событий, тип сессии.

    Требует результат add_sessions (колонки session_id, gap_min).

    Возвращает DataFrame с индексом (account, session_id) и колонками:
        start_ts, end_ts, n_events, duration_min,
        max_gap, session_type, period
    """
    stats = df_with_sessions.groupby(['account', 'session_id']).agg(
        start_ts=('ts_naive', 'min'),
        end_ts=('ts_naive', 'max'),
        n_events=('ts_naive', 'count'),
        first_ms=('ms_played', 'first'),
    )

    stats['duration_min'] = (
        (stats['end_ts'] - stats['start_ts']).dt.total_seconds() / 60
        + stats['first_ms'] / 60000
    )

    # Максимальный разрыв внутри сессии (кроме первого события)
    max_gap = (
        df_with_sessions.groupby(['account', 'session_id'])['gap_min']
        .apply(lambda x: x.iloc[1:].max() if len(x) > 1 else 0)
    )
    stats['max_gap'] = stats.index.map(max_gap)

    # Тип: continuous, если макс. разрыв <= 10 мин, иначе interrupted
    stats['session_type'] = np.where(
        stats['max_gap'] > 10, 'interrupted', 'continuous'
    )

    # Месяц старта сессии
    stats['period'] = stats['start_ts'].dt.to_period('M')

    return stats.reset_index()