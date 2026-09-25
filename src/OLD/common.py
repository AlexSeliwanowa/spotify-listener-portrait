"""Общие хелперы для всех модулей.

- Определение valid_play
- Разбиение на сессии
- BIC-штраф для PELT
- PELT + bootstrap устойчивость
- SNR и permutation-тест
"""
import numpy as np
import pandas as pd
import ruptures as rpt


# ============================================================================
# ВАЛИДНОЕ ПРОСЛУШИВАНИЕ
# ============================================================================

EXCLUDE_REASONS = ['trackerror', 'fwdbtn', 'backbtn', 'logout', 'remote', 'unexpected-exit']


def add_valid_play(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет колонку valid_play."""
    df = df.copy()
    df['valid_play'] = (
        (~df['is_skip']) &
        (df['ms_played'] >= 30_000) &
        (~df['reason_end'].isin(EXCLUDE_REASONS)) &
        (df['played_frac'] >= 0.5)
    )
    return df


# ============================================================================
# СЕССИИ
# ============================================================================

def add_sessions(df: pd.DataFrame, gap_min: int = 30) -> pd.DataFrame:
    """Разбивает события на сессии: разрыв > gap_min минут = новая сессия."""
    df = df.sort_values(['account', 'ts_naive']).reset_index(drop=True).copy()
    df['prev_ts'] = df.groupby('account')['ts_naive'].shift(1)
    df['gap_min'] = (df['ts_naive'] - df['prev_ts']).dt.total_seconds() / 60
    df['new_session'] = (df['gap_min'].isna()) | (df['gap_min'] > gap_min)
    df['session_id'] = df.groupby('account')['new_session'].cumsum()
    return df


def session_stats(df_with_sessions: pd.DataFrame) -> pd.DataFrame:
    """Агрегат по сессиям: длительность, число событий, месяц старта."""
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
    stats['period'] = stats['start_ts'].dt.to_period('M')
    return stats


# ============================================================================
# BIC-ШТРАФ ДЛЯ PELT
# ============================================================================

def compute_bic_pen(X: np.ndarray):
    """
    BIC-подобный штраф (Lavielle): pen = σ² · dim · log(n).
    σ² оценивается робастно через MAD первых разностей.

    Возвращает (pen, sigma2, n_obs, n_dims, X_norm).
    """
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1
    X_norm = (X - mean) / std

    diffs = np.diff(X_norm, axis=0)
    mad = np.median(np.abs(diffs - np.median(diffs, axis=0)), axis=0)
    sigma2 = np.mean((mad / 0.6745) ** 2)

    n_obs, n_dims = X_norm.shape
    pen = sigma2 * n_dims * np.log(n_obs)
    return pen, sigma2, n_obs, n_dims, X_norm


# ============================================================================
# PELT + BOOTSTRAP
# ============================================================================

def pelt_points(
    X_norm: np.ndarray,
    sigma2: float,
    n_dims: int,
    index: pd.Index,
    n_boot: int = 200,
    drop_frac: float = 0.15,
    seed: int = 42,
):
    """
    PELT с BIC-штрафом + bootstrap устойчивость точек.

    - X_norm: нормализованная матрица (n_obs × n_dims)
    - sigma2, n_dims: из compute_bic_pen
    - index: pd.Index с месяцами (Period) — для датировки точек

    Возвращает:
        points: список 'YYYY-MM'
        stability: dict {'YYYY-MM': доля}
        pen_bic: использованный штраф
    """
    n_obs = X_norm.shape[0]
    pen_bic = sigma2 * n_dims * np.log(n_obs)

    bkps = rpt.Pelt(model="l2").fit(X_norm).predict(pen=pen_bic)
    points = [index[i].strftime('%Y-%m') for i in bkps[:-1]]

    rng = np.random.default_rng(seed)
    n_keep = int(round(n_obs * (1 - drop_frac)))
    counts = {}

    for _ in range(n_boot):
        keep_idx = np.sort(rng.choice(n_obs, size=n_keep, replace=False))
        X_sub = X_norm[keep_idx]
        pen_sub = sigma2 * n_dims * np.log(n_keep)
        bkps_sub = rpt.Pelt(model="l2").fit(X_sub).predict(pen=pen_sub)
        for i in bkps_sub[:-1]:
            d = index[keep_idx[i]].strftime('%Y-%m')
            counts[d] = counts.get(d, 0) + 1

    stability = {k: v / n_boot for k, v in counts.items()}
    return points, stability, pen_bic


# ============================================================================
# SNR И PERMUTATION-ТЕСТ
# ============================================================================

def compute_snr(series: pd.Series, window: int = 3) -> float:
    """Signal-to-Noise Ratio: std rolling medians / median rolling std."""
    rolling_med = series.rolling(window, center=True, min_periods=2).median()
    rolling_std = series.rolling(window, center=True, min_periods=2).std()
    signal = rolling_med.std()
    noise = rolling_std.median()
    if noise == 0 or pd.isna(noise):
        return np.nan
    return signal / noise


def snr_gain_permutation(series: pd.Series, n_perm: int = 200,
                          window: int = 3, seed: int = 42):
    """
    Проверяет, отличается ли прирост SNR при сглаживании от прироста
    на случайных данных. Возвращает (real_gain, noise_p95, all_gains).
    """
    snr_raw = compute_snr(series, window)
    snr_smooth = compute_snr(
        series.rolling(window, center=True, min_periods=2).mean(), window
    )
    real_gain = snr_smooth - snr_raw

    rng = np.random.default_rng(seed)
    values = series.dropna().values
    gains = []
    for _ in range(n_perm):
        shuffled = pd.Series(rng.permutation(values), index=series.dropna().index)
        snr_r = compute_snr(shuffled, window)
        snr_s = compute_snr(
            shuffled.rolling(window, center=True, min_periods=2).mean(), window
        )
        if not (np.isnan(snr_r) or np.isnan(snr_s)):
            gains.append(snr_s - snr_r)

    return real_gain, np.percentile(gains, 95), gains


# ============================================================================
# УРОВНИ ПО ПОРОГАМ (без хардкода)
# ============================================================================

def level_from_value(val, thresholds):
    """Low / Medium / High / N/A по порогам из JSON."""
    if pd.isna(val) or not thresholds or len(thresholds) != 2:
        return 'N/A'
    low, high = thresholds
    if val < low:
        return 'Low'
    elif val <= high:
        return 'Medium'
    else:
        return 'High'


# ============================================================================
# MY MUSIC
# ============================================================================

def build_my_music(df: pd.DataFrame,
                    library_tracks: pd.DataFrame,
                    playlist_links: pd.DataFrame,
                    owner_ids: pd.DataFrame):
    """
    Помечает треки как «свои»: лайки ∪ свои плейлисты.

    Parameters
    ----------
    df : pd.DataFrame
        Основной DataFrame событий.
    library_tracks : pd.DataFrame
        Лайкнутые треки (колонка spotify_track_uri).
    playlist_links : pd.DataFrame
        Связи трек-плейлист (колонка Track URI, Added By).
    owner_ids : pd.DataFrame
        Владельцы (колонка owner_id).

    Returns
    -------
    (df, my_music_uris) : tuple
        df с добавленной колонкой my_music
        my_music_uris — set URI для переиспользования в других функциях
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
# ОБСЕССИИ (session-level)
# ============================================================================

def build_obsession_session_flag(df_events: pd.DataFrame,
                                 count_threshold: int = 3,
                                 share_threshold: float = 0.10,
                                 session_gap_min: int = 30) -> pd.DataFrame:
    """
    Session-level флаг обсессии.
    Возвращает DataFrame с колонками [account, session_id, is_obsession, period].
    """
    s = df_events.sort_values(['account', 'ts_naive']).copy()
    s['prev_ts'] = s.groupby('account')['ts_naive'].shift(1)
    s['gap_min'] = (s['ts_naive'] - s['prev_ts']).dt.total_seconds() / 60
    s['new_session'] = s['gap_min'].isna() | (s['gap_min'] > session_gap_min)
    s['session_id'] = s.groupby('account')['new_session'].cumsum()

    pair = (s.groupby(['account', 'session_id', 'spotify_track_uri'])
              .size().rename('count').reset_index())
    total = (s.groupby(['account', 'session_id'])
               .size().rename('n_events').reset_index())
    pair = pair.merge(total, on=['account', 'session_id'])
    pair['share'] = pair['count'] / pair['n_events']
    pair['is_pair'] = (
        (pair['count'] >= count_threshold) &
        (pair['share'] >= share_threshold)
    )

    sess = (pair.groupby(['account', 'session_id'])['is_pair']
                 .any().rename('is_obsession').reset_index())
    sess['period'] = (s.groupby(['account', 'session_id'])['period']
                        .first().values)
    return sess

# ============================================================================
# OBSESSION (event-level)
# ============================================================================
def is_obsession_event(df: pd.DataFrame) -> pd.Series:
    """
    Флаг базовой obsession на КАЖДОЕ событие.

    Пара (session, track) — obsession, если одновременно:
        count >= 3 И share >= 0.10.

    add_sessions сортирует df (по account, ts_naive) и делает reset_index.
    Чтобы флаг попал на ПРАВИЛЬНУЮ строку исходного df, сохраняем
    row_id до сортировки и восстанавливаем исходный порядок в конце.
    """
    # Сохраняем row_id — привязка флага к конкретному событию
    s = df.copy()
    s['_row_id'] = np.arange(len(s))

    s = add_sessions(s)

    # Пары (session, track) с числом повторов
    pair = (s.groupby(['account', 'session_id', 'spotify_track_uri'])
              .size().rename('count').reset_index())
    total = (s.groupby(['account', 'session_id'])
               .size().rename('n_events').reset_index())
    pair = pair.merge(total, on=['account', 'session_id'])
    pair['share'] = pair['count'] / pair['n_events']
    pair['is_obsession_episode'] = (
        (pair['count'] >= 3) & (pair['share'] >= 0.10)
    )

    # Помечаем события
    merged = s.merge(
        pair[['account', 'session_id', 'spotify_track_uri',
              'is_obsession_episode']],
        on=['account', 'session_id', 'spotify_track_uri'],
        how='left',
    )

    # Восстанавливаем исходный порядок по _row_id и исходный индекс
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
    # Сессии
    s = add_sessions(df)
    s = s.sort_values(
        ['account', 'session_id', 'ts_naive']
    ).reset_index(drop=True)

    # Сравниваем текущий трек с предыдущим в сессии
    s['prev_uri'] = (s.groupby(['account', 'session_id'])
                       ['spotify_track_uri'].shift(1))
    s['same_as_prev'] = (s['spotify_track_uri'] == s['prev_uri'])

    # Каждая новая серия — там, где трек сменился
    s['new_series'] = (~s['same_as_prev']).astype(int)
    s['series_id'] = s['new_series'].cumsum()

    # Агрегат по серии
    series = s.groupby('series_id').agg(
        track_uri=('spotify_track_uri', 'first'),
        repeats=('series_id', 'size'),
        start_ts=('ts_naive', 'min'),
        total_ms=('ms_played', 'sum'),
    )

    strong = series[series['repeats'] >= 5].copy()

    # date = timestamp начала месяца пика
    strong['date'] = strong['start_ts'].dt.to_period('M').dt.start_time

    # Подтягиваем название трека и артиста
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