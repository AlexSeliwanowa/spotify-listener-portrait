"""Indices: индексы метрик для kpi_summary.

Все индексы — публичные функции, возвращают float (или NaN).
Хелперы — приватные, используются только индексами.

Категории:
    basic     — звук, жанры, артисты, настроение, аудио-балансы (этап 5)
    temporal  — временные паттерны (этап 6)
    behavioral — поведение слушателя (этап 7)
    playlist  — плейлисты и коллекция (этап 8)

Метаданные индекса (unit, category, audience) — в INDEX_SPECS.
Оркестратор build_kpi_summary собирает всё в один DataFrame.


Принципы расчёта аудио-индексов:

    Каждый индекс сам решает, какие колонки ему нужны, и делает
    dropna ТОЛЬКО по ним. Не по общему набору 9 аудио-колонок.

    Почему: dropna по всем 9 колонкам сразу теряет 21% валидных событий
    (78.7% от 45 841), потому что часть событий имеет NaN в loudness
    или played_frac. Эти признаки не нужны большинству индексов
    (Acoustic-Energy Balance использует только energy и acousticness).

    Следствие: значения индексов отличаются от старого kpi_summary
    (например, Acoustic-Energy Balance 0.5611 вместо 0.5774). Это
    осознанный выбор: индекс считается на максимально доступной базе
    для СВОИХ признаков, а не на пересечении всех признаков.
"""

import numpy as np
import pandas as pd

from helpers import normalized_entropy


# ============================================================================
# HELPERS (приватные)
# ============================================================================

def _mood_entropy(df_subset, val_med=0.5, en_med=0.5) -> float:
    """Энтропия по квадрантам Рассела (границы valence/energy)."""
    mood = df_subset[['valence', 'energy']].dropna()
    if mood.empty:
        return np.nan
    conditions = [
        (mood['valence'] >= val_med) & (mood['energy'] >= en_med),
        (mood['valence'] <  val_med) & (mood['energy'] >= en_med),
        (mood['valence'] <  val_med) & (mood['energy'] <  en_med),
        (mood['valence'] >= val_med) & (mood['energy'] <  en_med),
    ]
    mood = mood.copy()
    mood['mood_group'] = np.select(
        conditions,
        ['HH', 'LH', 'LL', 'HL'],
        default='Unknown',
    )
    counts = mood['mood_group'].value_counts()
    return normalized_entropy(counts)


def _average_tracks_per_day(df_valid) -> float:
    if df_valid.empty:
        return np.nan
    daily = df_valid.groupby(df_valid['ts_naive'].dt.date)['spotify_track_uri'].count()
    return daily.mean()


def _average_events_per_day(df_all) -> float:
    if df_all.empty:
        return np.nan
    daily = df_all.groupby(df_all['ts_naive'].dt.date)['spotify_track_uri'].count()
    return daily.mean()


def _hipster_window(df_window, tracks_exportify) -> float:
    """
    Hipster для окна: my_music (≥1 play) ∪ foreign/orphan (≥3 plays).
    Требует df['source'] (enrich.add_track_source).
    Hipster Index (global) использует drop_duplicates('spotify_track_uri') и фильтр df['my_music']. 
    Не делает dropna вообще — pop.dropna() уже внутри. Оставляем как есть.
    """
    if df_window.empty:
        return np.nan
    track_counts = (df_window
        .groupby(['spotify_track_uri', 'source'])
        .size().reset_index(name='plays'))
    eligible = track_counts[
        ((track_counts['source'] == 'my_music') & (track_counts['plays'] >= 1)) |
        ((track_counts['source'].isin(['foreign', 'orphan'])) & (track_counts['plays'] >= 3))
    ]['spotify_track_uri'].unique()
    if len(eligible) == 0:
        return np.nan
    pop = tracks_exportify[
        tracks_exportify['spotify_track_uri'].isin(eligible)
    ]['popularity'].dropna()
    if pop.empty:
        return np.nan
    return 1 - pop.mean() / 100


# ============================================================================
# BASIC (этап 5)
# ============================================================================

def hipster_index(df, tracks_exportify) -> float:
    """Hipster Index global: 1 − средний popularity my_music треков / 100."""
    my_tracks = df[df['my_music']].drop_duplicates('spotify_track_uri')
    pop = my_tracks['popularity'].dropna()
    if pop.empty:
        return np.nan
    return 1 - pop.mean() / 100


def hipster_index_window(df_window, tracks_exportify) -> float:
    """Hipster Index для окна: my_music (≥1 play) ∪ foreign/orphan (≥3 plays)."""
    return _hipster_window(df_window, tracks_exportify)


def genre_diversity_index(df_valid) -> float:
    """Энтропия по жанрам (нормированная)."""
    genre_series = (df_valid[df_valid['genres_normalized'] != 'unknown']
                    ['genres_normalized']
                    .str.split(',').explode().str.strip())
    counts = genre_series.value_counts()
    return normalized_entropy(counts)


def artist_diversity_index(df_valid) -> float:
    """Энтропия по артистам (нормированная)."""
    counts = df_valid['artist_name'].value_counts()
    return normalized_entropy(counts)


def mood_diversity_index(df_valid) -> float:
    """Mood Diversity — квадранты Рассела, абсолютные границы 0.5."""
    return _mood_entropy(df_valid)


def mood_diversity_index_personal(df_all) -> float:
    """Mood Diversity относительно личных медиан valence/energy."""
    val_med = df_all['valence'].median()
    en_med  = df_all['energy'].median()
    return _mood_entropy(df_all, val_med=val_med, en_med=en_med)


def acoustic_energy_balance(df_valid) -> float:
    """(energy_mean − acousticness_mean + 1) / 2. 0 = акустика, 1 = электроника."""
    audio = df_valid[['energy', 'acousticness']].dropna()
    if audio.empty:
        return np.nan
    return (audio['energy'].mean() - audio['acousticness'].mean() + 1) / 2


def groove_index(df_valid) -> float:
    """(danceability_mean + (tempo_mean − 100)/100) / 2."""
    audio = df_valid[['danceability', 'tempo']].dropna()
    if audio.empty:
        return np.nan
    return (audio['danceability'].mean() + (audio['tempo'].mean() - 100) / 100) / 2


def vocalness_index(df_valid) -> float:
    """1 − instrumentalness_mean."""
    audio = df_valid['instrumentalness'].dropna()
    if audio.empty:
        return np.nan
    return 1 - audio.mean()


def ambient_factor(df_valid) -> float:
    """(acousticness_mean + instrumentalness_mean) / 2."""
    audio = df_valid[['acousticness', 'instrumentalness']].dropna()
    if audio.empty:
        return np.nan
    return (audio['acousticness'].mean() + audio['instrumentalness'].mean()) / 2


def commercial_pressure(df_valid) -> float:
    """((loudness_mean + 60)/60 + popularity_mean/100) / 2."""
    audio = df_valid[['loudness', 'popularity']].dropna()
    if audio.empty:
        return np.nan
    loudness_norm = (audio['loudness'].mean() + 60) / 60
    popularity_norm = audio['popularity'].mean() / 100
    return (loudness_norm + popularity_norm) / 2


def mood_bias(df_valid) -> float:
    """(valence_mean + energy_mean) / 2."""
    audio = df_valid[['valence', 'energy']].dropna()
    if audio.empty:
        return np.nan
    return (audio['valence'].mean() + audio['energy'].mean()) / 2


def total_listening_hours(df_valid) -> float:
    """Сумма ms_played / 3 600 000."""
    if df_valid.empty:
        return np.nan
    return df_valid['ms_played'].sum() / 3_600_000


def average_tracks_per_day(df_valid) -> float:
    """Среднее число треков в день (по валидным событиям)."""
    return _average_tracks_per_day(df_valid)


def average_events_per_day(df_all) -> float:
    """Среднее число событий в день (по всем событиям)."""
    return _average_events_per_day(df_all)


# ============================================================================
# TEMPORAL (этап 6)
# ============================================================================

def _music_day_share(df_all) -> float:
    """Доля дней с хотя бы одним событием."""
    if df_all.empty:
        return np.nan
    d_min = df_all['ts_naive'].dt.date.min()
    d_max = df_all['ts_naive'].dt.date.max()
    all_days = pd.date_range(d_min, d_max, freq='D')
    daily = df_all.groupby(df_all['ts_naive'].dt.date)['spotify_track_uri'].count()
    daily = daily.reindex(all_days.date, fill_value=0)
    return (daily > 0).mean()


def _listening_variability(df_all) -> float:
    """CV дневного числа событий (std/mean)."""
    if df_all.empty:
        return np.nan
    d_min = df_all['ts_naive'].dt.date.min()
    d_max = df_all['ts_naive'].dt.date.max()
    all_days = pd.date_range(d_min, d_max, freq='D')
    daily = df_all.groupby(df_all['ts_naive'].dt.date)['spotify_track_uri'].count()
    daily = daily.reindex(all_days.date, fill_value=0)
    if daily.mean() == 0:
        return 0.0
    return daily.std() / daily.mean()


def _listening_consistency(df_all) -> float:
    """music_day_share * 1 / (1 + log(1+cv))."""
    if df_all.empty:
        return np.nan
    share = _music_day_share(df_all)
    cv = _listening_variability(df_all)
    return share * (1 / (1 + np.log1p(cv)))


def music_day_share(df_all) -> float:
    """Доля дней с музыкой от всего периода."""
    return _music_day_share(df_all)


def listening_variability(df_all) -> float:
    """Вариативность дневного потребления (CV)."""
    return _listening_variability(df_all)


def listening_consistency_index(df_all) -> float:
    """Регулярность: комбинация music_day_share и CV."""
    return _listening_consistency(df_all)


def music_recency_index(df_valid) -> float:
    """Доля треков, вышедших за последние 2 года от последнего года в данных."""
    if df_valid.empty:
        return np.nan
    max_year = df_valid['ts_naive'].dt.year.max()
    threshold_year = max_year - 2
    release_year = pd.to_datetime(df_valid['release_date'], errors='coerce').dt.year
    return (release_year >= threshold_year).mean()


def night_listening_share(df_valid) -> float:
    """Доля событий в 0–5 часов (через helpers.night_share)."""
    from helpers import night_share
    return night_share(df_valid)


def platform_desktop_share(df_valid) -> float:
    """Доля событий на десктопе (через helpers.desktop_share)."""
    from helpers import desktop_share
    return desktop_share(df_valid)


def _sessions_count(df_all) -> int:
    """Число уникальных сессий (по account + session_id)."""
    if df_all.empty:
        return 0
    return df_all.groupby(['account', 'session_id']).ngroups


def average_sessions_per_day(df_all) -> float:
    """Сессий в день = число сессий / число дней."""
    if df_all.empty:
        return np.nan
    days = df_all['ts_naive'].dt.date.nunique()
    if days == 0:
        return np.nan
    return _sessions_count(df_all) / days


# ============================================================================
# BEHAVIORAL (этап 7)
# ============================================================================

def skip_risk_index(df_all) -> float:
    """Доля событий-скипов от всех событий."""
    if df_all.empty:
        return np.nan
    return df_all['is_skip'].mean()


def session_depth_index(sessions_df, start=None, end=None) -> float:
    """
    Глубина сессии: медианная длительность / 60 минут (обрезано в [0, 1].

    sessions_df — результат aggregators.behavior.session_stats(df).
    start/end — опциональные границы по start_ts.
    """
    if sessions_df is None or sessions_df.empty:
        return np.nan
    sub = sessions_df
    if start is not None:
        sub = sub[sub['start_ts'] >= start]
    if end is not None:
        sub = sub[sub['start_ts'] <= end]
    if sub.empty:
        return np.nan
    return min(1.0, sub['duration_min'].median() / 60)


def repeat_listening_share(df_valid) -> float:
    """Доля повторных прослушиваний: 1 − (уникальные треки / все события)."""
    if df_valid.empty:
        return np.nan
    tracks = df_valid.groupby('spotify_track_uri').size()
    repeats = (tracks[tracks > 1] - 1).sum()
    total = len(df_valid)
    return repeats / total if total > 0 else np.nan


def external_exposure_index(df_valid) -> float:
    """Доля событий из чужих источников (foreign + orphan)."""
    if df_valid.empty:
        return np.nan
    return df_valid['source'].isin(['foreign', 'orphan']).mean()


def artist_echo_chamber_index(df, current_start, current_end) -> float:
    """
    Доля артистов текущего окна, встречавшихся раньше.

    Требует df['valid_play'], df['artist_name'].
    history = valid события до current_start.
    current = valid события в [current_start, current_end].
    """
    current_uris = set(df.loc[
        (df['ts_naive'] >= current_start) &
        (df['ts_naive'] <= current_end) &
        (df['valid_play']),
        'spotify_track_uri',
    ].unique())
    history_uris = set(df.loc[
        (df['ts_naive'] < current_start) & (df['valid_play']),
        'spotify_track_uri',
    ].unique())

    if not current_uris:
        return np.nan

    track_artists = (df.drop_duplicates('spotify_track_uri')
                       .set_index('spotify_track_uri')['artist_name'])
    current_artists = set(track_artists.loc[track_artists.index.isin(current_uris)].dropna())
    history_artists = set(track_artists.loc[track_artists.index.isin(history_uris)].dropna())

    if not current_artists:
        return np.nan
    return len(current_artists & history_artists) / len(current_artists)


def mean_played_fraction(df_valid) -> float:
    """Средняя доля прослушанного трека (обрезано в 1.0)."""
    if df_valid.empty:
        return np.nan
    frac = df_valid['played_frac'].dropna().clip(upper=1.0)
    return frac.mean()


def completion_rate(df_valid) -> float:
    """Доля треков, дослушанных до ≥90% длительности."""
    if df_valid.empty:
        return np.nan
    return (df_valid['ms_played'] >= df_valid['duration_ms'] * 0.9).mean()


def contextual_skip_ratio(df_all) -> float:
    """
    Доля контекстных скипов среди всех мгновенных скипов.

    Контекстный скип = мгновенный скип (<10 сек) трека, который ранее
    (в истории до этого события) уже имел глубокое прослушивание (≥80%).
    """
    if df_all.empty:
        return np.nan
    tmp = df_all.copy()
    tmp['is_instant_skip'] = tmp['ms_played'] < 10_000
    tmp['is_deep'] = tmp['ms_played'] >= tmp['duration_ms'] * 0.8

    tmp = tmp.sort_values(['spotify_track_uri', 'ts_naive'])
    tmp['has_deep_so_far'] = (
        tmp.groupby('spotify_track_uri')['is_deep']
           .cummax()
           .shift(1, fill_value=False)
    )

    instant = tmp[tmp['is_instant_skip']]
    if len(instant) == 0:
        return np.nan
    return instant['has_deep_so_far'].mean()


def interrupted_session_share(sessions_df, start, end) -> float:
    """
    Доля прерывистых сессий в окне.

    sessions_df — результат aggregators.behavior.session_stats(df).
    start/end — границы по start_ts.
    """
    if sessions_df is None or sessions_df.empty:
        return np.nan
    sub = sessions_df[
        (sessions_df['start_ts'] >= start) & (sessions_df['start_ts'] <= end)
    ]
    if sub.empty:
        return np.nan
    return (sub['session_type'] == 'interrupted').mean()



# ============================================================================
# PLAYLIST (этап 8)
# ============================================================================

def _track_diversity(df_valid) -> float:
    """Энтропия по трекам."""
    if df_valid.empty:
        return np.nan
    counts = df_valid.groupby('spotify_track_uri').size()
    return normalized_entropy(counts)


def _top_artist_share(df_valid, top_n: int = 10) -> float:
    """Доля событий на топ-N артистов."""
    if df_valid.empty:
        return np.nan
    counts = df_valid['artist_name'].value_counts()
    return counts.head(top_n).sum() / len(df_valid)


def _social_music_share(df_valid, uri_sets) -> float:
    """Доля событий из collaborative ∪ contributed."""
    if df_valid.empty:
        return np.nan
    social = uri_sets['collaborative'] | uri_sets['contributed']
    return df_valid['spotify_track_uri'].isin(social).mean()


def _stickiness_rate(df_valid, uri_sets) -> float:
    """Доля событий из personal ∪ collaborative плейлистов."""
    if df_valid.empty:
        return np.nan
    own = uri_sets['personal'] | uri_sets['collaborative']
    return df_valid['spotify_track_uri'].isin(own).mean()


def _playlist_redundancy(playlist_links) -> float:
    """Доля треков, встречающихся в 2+ своих плейлистах."""
    own = playlist_links[
        playlist_links['playlist_type'].isin(['personal', 'collaborative'])
    ]
    counts = own.groupby('Track URI')['name_norm'].nunique()
    if counts.empty:
        return np.nan
    return (counts > 1).mean()


def _collaborator_diversity(playlist_links) -> float:
    """Энтропия по Added By среди collaborative / contributed."""
    collab = playlist_links[
        playlist_links['playlist_type'].isin(['collaborative', 'contributed'])
    ]
    added_by = collab['Added By'].replace('unknown', np.nan).dropna()
    if added_by.empty:
        return np.nan
    counts = added_by.value_counts()
    return normalized_entropy(counts)


def _playlist_creation_frequency(playlist_links) -> float:
    """Число созданных плейлистов в год."""
    creation_dates = (playlist_links
        .groupby('name_norm')['Added At'].min().dropna())
    if len(creation_dates) == 0:
        return np.nan
    dates = pd.to_datetime(creation_dates, errors='coerce').dt.tz_localize(None).dropna()
    if dates.empty:
        return np.nan
    years = (dates.max() - dates.min()).days / 365.25
    if years <= 0:
        return np.nan
    return len(dates) / years


def _active_playlist_days_per_year(playlist_links,
                                    start_date=None, end_date=None) -> float:
    """Число уникальных дней с добавлениями в свои плейлисты в год."""
    own = playlist_links[
        playlist_links['playlist_type'].isin(['personal', 'collaborative'])
    ].copy()
    own['Added At'] = pd.to_datetime(own['Added At'], errors='coerce').dt.tz_localize(None)

    if start_date is not None:
        own = own[own['Added At'] >= start_date]
    if end_date is not None:
        own = own[own['Added At'] <= end_date]

    if own.empty:
        return np.nan

    unique_days = own['Added At'].dt.date.nunique()

    if start_date is not None and end_date is not None:
        period_years = (end_date - start_date).days / 365.25
    else:
        min_d = own['Added At'].min()
        max_d = own['Added At'].max()
        period_years = (max_d - min_d).days / 365.25

    if period_years <= 0:
        return np.nan
    return unique_days / period_years


def _declining_engagement_rate(df_all) -> float:
    """Доля месяцев, в которых число событий меньше предыдущего."""
    valid = df_all[df_all['valid_play']].copy()
    if valid.empty:
        return np.nan
    monthly = valid.groupby('period').size()
    if len(monthly) < 12:
        return np.nan
    diff = monthly.diff().dropna()
    return (diff < 0).sum() / len(diff)


def _classify_playlist_fill(group) -> str:
    """
    Классификация fill_type одного плейлиста.

    Требует: колонки Added At, first_valid_seen, listened_before в группе.
    """
    total = len(group)
    if total == 0:
        return 'empty'

    group = group.sort_values('Added At').reset_index(drop=True)
    n_days = group['Added At'].dt.date.nunique()

    if n_days == 1:
        duration_min = (group['Added At'].max()
                        - group['Added At'].min()).total_seconds() / 60
        known = group['listened_before'].notna()
        share = (group.loc[known, 'listened_before'].mean()
                 if known.sum() > 0 else 0.0)
        if (total >= 100 and share < 0.30 and duration_min <= 15):
            return 'mass_import'

    lengths = []
    cur = 1
    for i in range(1, total):
        interval = (group.loc[i, 'Added At']
                    - group.loc[i - 1, 'Added At']).total_seconds() / 60
        if interval <= 2:
            cur += 1
        else:
            lengths.append(cur)
            cur = 1
    lengths.append(cur)

    return 'curated' if any(l == 1 for l in lengths) else 'batch'


def _playlist_update_frequency(playlist_links, valid_first_seen) -> float:
    """
    Медиана числа дней с добавлениями в год среди curated-плейлистов.
    """
    own = playlist_links[
        playlist_links['playlist_type'].isin(['personal', 'collaborative'])
    ].copy()
    own['Added At'] = pd.to_datetime(own['Added At'], errors='coerce').dt.tz_localize(None)
    own['first_valid_seen'] = own['Track URI'].map(valid_first_seen)
    own['listened_before'] = own['first_valid_seen'] < own['Added At']

    fill_types = {}
    for name, group in own.groupby('name_norm'):
        fill_types[name] = _classify_playlist_fill(group)

    rows = []
    for name, ft in fill_types.items():
        if ft != 'curated':
            continue
        group = own[own['name_norm'] == name]
        dates = group['Added At'].dropna()
        if dates.empty:
            continue
        n_days = dates.dt.date.nunique()
        lifespan = (dates.max() - dates.min()).days
        if lifespan < 30:
            continue
        rows.append(n_days / (lifespan / 365.25))

    if not rows:
        return np.nan
    return np.median(rows)


# Публичные обёртки
def social_music_share(df_valid, uri_sets) -> float:
    return _social_music_share(df_valid, uri_sets)


def playlist_stickiness_rate(df_valid, uri_sets) -> float:
    return _stickiness_rate(df_valid, uri_sets)


def track_diversity_index(df_valid) -> float:
    return _track_diversity(df_valid)


def top_artist_share(df_valid, top_n: int = 10) -> float:
    return _top_artist_share(df_valid, top_n)


def playlist_redundancy_index(playlist_links) -> float:
    return _playlist_redundancy(playlist_links)


def collaborator_diversity_index(playlist_links) -> float:
    return _collaborator_diversity(playlist_links)


def playlist_creation_frequency(playlist_links) -> float:
    return _playlist_creation_frequency(playlist_links)


def playlist_update_frequency(playlist_links, valid_first_seen) -> float:
    return _playlist_update_frequency(playlist_links, valid_first_seen)


def active_playlist_days_per_year(playlist_links,
                                  start_date=None, end_date=None) -> float:
    return _active_playlist_days_per_year(playlist_links, start_date, end_date)


def declining_engagement_rate(df_all) -> float:
    return _declining_engagement_rate(df_all)





# ============================================================================
# МЕТАДАННЫЕ ИНДЕКСОВ
# ============================================================================
INDEX_SPECS = {
    # ---------- basic ----------
    'Hipster Index':                          {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Genre Diversity Index':                  {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Artist Diversity Index':                 {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Mood Diversity Index':                   {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Mood Diversity Index (personal median)': {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Acoustic-Energy Balance':                {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Groove Index':                           {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Vocalness Index':                        {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Ambient Factor':                         {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Commercial Pressure':                    {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Mood Bias':                              {'unit': 'index', 'category': 'basic', 'audience': 'both'},
    'Total Listening Hours':                  {'unit': 'hours', 'category': 'basic', 'audience': 'both'},
    'Average Tracks per Day':                 {'unit': 'count', 'category': 'basic', 'audience': 'personal'},
    'Average Events per Day':                 {'unit': 'count', 'category': 'basic', 'audience': 'professional'},

    # ---------- temporal ----------
    'Music Day Share':                        {'unit': 'percent', 'category': 'temporal', 'audience': 'both'},
    'Listening Variability':                  {'unit': 'index',   'category': 'temporal', 'audience': 'both'},
    'Listening Consistency Index':            {'unit': 'index',   'category': 'temporal', 'audience': 'both'},
    'Music Recency Index':                    {'unit': 'percent', 'category': 'temporal', 'audience': 'both'},
    'Night Listening Share':                  {'unit': 'percent', 'category': 'temporal', 'audience': 'both'},
    'Platform Desktop Share':                 {'unit': 'percent', 'category': 'temporal', 'audience': 'both'},
    'Average Sessions per Day':               {'unit': 'count',   'category': 'temporal', 'audience': 'both'},

    # ---------- behavioral ----------
    'Skip Risk Index':                        {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Session Depth Index':                    {'unit': 'index',   'category': 'behavioral', 'audience': 'both'},
    'Repeat Listening Share':                 {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'External Exposure Index':                {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Artist Echo Chamber Index':              {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Mean Played Fraction':                   {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Completion Rate':                        {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Contextual Skip Ratio':                  {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},
    'Interrupted Session Share':              {'unit': 'percent', 'category': 'behavioral', 'audience': 'both'},

    # ---------- playlist ----------
    'Social Music Share':                     {'unit': 'percent', 'category': 'playlist', 'audience': 'both'},
    'Track Diversity Index':                  {'unit': 'index',   'category': 'playlist', 'audience': 'both'},
    'Playlist Stickiness Rate':               {'unit': 'percent', 'category': 'playlist', 'audience': 'both'},
    'Top Artist Share':                       {'unit': 'percent', 'category': 'playlist', 'audience': 'both'},
    'Playlist Redundancy Index':              {'unit': 'index',   'category': 'playlist', 'audience': 'both'},
    'Collaborator Diversity Index':           {'unit': 'index',   'category': 'playlist', 'audience': 'both'},
    'Playlist Creation Frequency':            {'unit': 'count',   'category': 'playlist', 'audience': 'both'},
    'Playlist Update Frequency':              {'unit': 'count',   'category': 'playlist', 'audience': 'both'},
    'Active Playlist Days per Year':          {'unit': 'days',    'category': 'playlist', 'audience': 'both'},
    'Declining Engagement Rate':              {'unit': 'percent', 'category': 'playlist', 'audience': 'both'},
}

# ============================================================================
# ОРКЕСТРАТОР
# ============================================================================

def _make_id(index_name: str, stage: str) -> str:
    stage_code = {'global': 'G', 'recent_6q': '6Q', 'last_90d': '90D'}[stage]
    slug = index_name.lower()
    slug = slug.replace(' / ', '_').replace(' ', '_').replace('/', '_')
    slug = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in slug)
    slug = '_'.join(p for p in slug.split('_') if p)
    return f'{slug}_{stage_code}'


def _append(records, index_name, value, stage):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return
    spec = INDEX_SPECS.get(index_name, {})
    records.append({
        'id':         _make_id(index_name, stage),
        'index_name': index_name,
        'value':      float(value),
        'unit':       spec.get('unit', 'index'),
        'stage':      stage,
        'category':   spec.get('category', 'other'),
        'audience':   spec.get('audience', 'both'),
    })


def build_kpi_summary(df, windows, tracks_exportify, playlist_links):
    """
    Собирает все индексы в один DataFrame.

    df — обогащённый (valid_play, my_music, source, session_id, period).
    windows — dict {global / recent_6q / last_90d: (start, end)}.
    tracks_exportify, playlist_links — метаданные.

    Возвращает DataFrame с колонками:
        id, index_name, value, unit, stage, category, audience
    """
    from enrich import build_uri_sets
    from aggregators.behavior import session_stats

    uri_sets = build_uri_sets(playlist_links)
    sessions = session_stats(df)

    valid_first_seen = (df[df['valid_play']]
                          .groupby('spotify_track_uri')['first_valid_seen']
                          .min())

    records = []

    # ---------- GLOBAL ----------
    start_g, end_g = windows['global']
    v_g = df[df['valid_play']]

    _append(records, 'Hipster Index',            hipster_index(df, tracks_exportify), 'global')
    _append(records, 'Genre Diversity Index',    genre_diversity_index(v_g), 'global')
    _append(records, 'Artist Diversity Index',   artist_diversity_index(v_g), 'global')
    _append(records, 'Mood Diversity Index',     mood_diversity_index(v_g), 'global')
    _append(records, 'Mood Diversity Index (personal median)',
            mood_diversity_index_personal(df), 'global')
    _append(records, 'Acoustic-Energy Balance',  acoustic_energy_balance(v_g), 'global')
    _append(records, 'Groove Index',             groove_index(v_g), 'global')
    _append(records, 'Vocalness Index',          vocalness_index(v_g), 'global')
    _append(records, 'Ambient Factor',           ambient_factor(v_g), 'global')
    _append(records, 'Commercial Pressure',      commercial_pressure(v_g), 'global')
    _append(records, 'Mood Bias',                mood_bias(v_g), 'global')
    _append(records, 'Total Listening Hours',    total_listening_hours(v_g), 'global')
    _append(records, 'Average Tracks per Day',   average_tracks_per_day(v_g), 'global')
    _append(records, 'Average Events per Day',   average_events_per_day(df), 'global')

    _append(records, 'Music Day Share',          music_day_share(df), 'global')
    _append(records, 'Listening Variability',    listening_variability(df), 'global')
    _append(records, 'Listening Consistency Index',
            listening_consistency_index(df), 'global')
    _append(records, 'Music Recency Index',      music_recency_index(v_g), 'global')
    _append(records, 'Night Listening Share',    night_listening_share(v_g), 'global')
    _append(records, 'Platform Desktop Share',   platform_desktop_share(v_g), 'global')
    _append(records, 'Average Sessions per Day', average_sessions_per_day(df), 'global')

    _append(records, 'Skip Risk Index',          skip_risk_index(df), 'global')
    _append(records, 'Session Depth Index',      session_depth_index(sessions), 'global')
    _append(records, 'Repeat Listening Share',   repeat_listening_share(v_g), 'global')
    _append(records, 'External Exposure Index',  external_exposure_index(v_g), 'global')
    _append(records, 'Mean Played Fraction',     mean_played_fraction(v_g), 'global')
    _append(records, 'Completion Rate',          completion_rate(v_g), 'global')
    _append(records, 'Contextual Skip Ratio',    contextual_skip_ratio(df), 'global')
    _append(records, 'Interrupted Session Share',
            interrupted_session_share(sessions, start_g, end_g), 'global')

    _append(records, 'Social Music Share',
            social_music_share(v_g, uri_sets), 'global')
    _append(records, 'Playlist Redundancy Index',
            playlist_redundancy_index(playlist_links), 'global')
    _append(records, 'Collaborator Diversity Index',
            collaborator_diversity_index(playlist_links), 'global')
    _append(records, 'Track Diversity Index',    track_diversity_index(v_g), 'global')
    _append(records, 'Playlist Creation Frequency',
            playlist_creation_frequency(playlist_links), 'global')
    _append(records, 'Playlist Update Frequency',
            playlist_update_frequency(playlist_links, valid_first_seen), 'global')
    _append(records, 'Playlist Stickiness Rate',
            playlist_stickiness_rate(v_g, uri_sets), 'global')
    _append(records, 'Top Artist Share',         top_artist_share(v_g), 'global')
    _append(records, 'Declining Engagement Rate',
            declining_engagement_rate(df), 'global')
    _append(records, 'Active Playlist Days per Year',
            active_playlist_days_per_year(playlist_links), 'global')

    # ---------- RECENT 6Q ----------
    start_6, end_6 = windows['recent_6q']
    v_6 = df[(df['ts_naive'] >= start_6) &
             (df['ts_naive'] <= end_6) & (df['valid_play'])]
    df_6_all = df[(df['ts_naive'] >= start_6) & (df['ts_naive'] <= end_6)]

    _append(records, 'Hipster Index',
            hipster_index_window(v_6, tracks_exportify), 'recent_6q')
    _append(records, 'Genre Diversity Index',    genre_diversity_index(v_6), 'recent_6q')
    _append(records, 'Artist Diversity Index',   artist_diversity_index(v_6), 'recent_6q')
    _append(records, 'Mood Diversity Index',     mood_diversity_index(v_6), 'recent_6q')
    _append(records, 'Acoustic-Energy Balance',  acoustic_energy_balance(v_6), 'recent_6q')
    _append(records, 'Groove Index',             groove_index(v_6), 'recent_6q')
    _append(records, 'Vocalness Index',          vocalness_index(v_6), 'recent_6q')
    _append(records, 'Ambient Factor',           ambient_factor(v_6), 'recent_6q')
    _append(records, 'Commercial Pressure',      commercial_pressure(v_6), 'recent_6q')
    _append(records, 'Mood Bias',                mood_bias(v_6), 'recent_6q')
    _append(records, 'Total Listening Hours',    total_listening_hours(v_6), 'recent_6q')
    _append(records, 'Average Tracks per Day',   average_tracks_per_day(v_6), 'recent_6q')
    _append(records, 'Average Events per Day',   average_events_per_day(df_6_all), 'recent_6q')

    _append(records, 'Music Day Share',          music_day_share(df_6_all), 'recent_6q')
    _append(records, 'Listening Variability',    listening_variability(df_6_all), 'recent_6q')
    _append(records, 'Listening Consistency Index',
            listening_consistency_index(df_6_all), 'recent_6q')
    _append(records, 'Music Recency Index',      music_recency_index(v_6), 'recent_6q')
    _append(records, 'Night Listening Share',    night_listening_share(v_6), 'recent_6q')
    _append(records, 'Platform Desktop Share',   platform_desktop_share(v_6), 'recent_6q')
    _append(records, 'Average Sessions per Day',
            average_sessions_per_day(df_6_all), 'recent_6q')

    _append(records, 'Skip Risk Index',          skip_risk_index(df_6_all), 'recent_6q')
    _append(records, 'Session Depth Index',
            session_depth_index(sessions, start_6, end_6), 'recent_6q')
    _append(records, 'Repeat Listening Share',   repeat_listening_share(v_6), 'recent_6q')
    _append(records, 'External Exposure Index',  external_exposure_index(v_6), 'recent_6q')
    _append(records, 'Artist Echo Chamber Index',
            artist_echo_chamber_index(df, start_6, end_6), 'recent_6q')
    _append(records, 'Mean Played Fraction',     mean_played_fraction(v_6), 'recent_6q')
    _append(records, 'Completion Rate',          completion_rate(v_6), 'recent_6q')
    _append(records, 'Contextual Skip Ratio',    contextual_skip_ratio(df_6_all), 'recent_6q')
    _append(records, 'Interrupted Session Share',
            interrupted_session_share(sessions, start_6, end_6), 'recent_6q')

    _append(records, 'Social Music Share',
            social_music_share(v_6, uri_sets), 'recent_6q')
    _append(records, 'Track Diversity Index',    track_diversity_index(v_6), 'recent_6q')
    _append(records, 'Playlist Stickiness Rate',
            playlist_stickiness_rate(v_6, uri_sets), 'recent_6q')
    _append(records, 'Top Artist Share',         top_artist_share(v_6), 'recent_6q')
    _append(records, 'Active Playlist Days per Year',
            active_playlist_days_per_year(playlist_links, start_6, end_6), 'recent_6q')

    # ---------- LAST 90D ----------
    start_90, end_90 = windows['last_90d']
    v_90 = df[(df['ts_naive'] >= start_90) &
              (df['ts_naive'] <= end_90) & (df['valid_play'])]
    df_90_all = df[(df['ts_naive'] >= start_90) & (df['ts_naive'] <= end_90)]

    _append(records, 'Hipster Index',
            hipster_index_window(v_90, tracks_exportify), 'last_90d')
    _append(records, 'Genre Diversity Index',    genre_diversity_index(v_90), 'last_90d')
    _append(records, 'Artist Diversity Index',   artist_diversity_index(v_90), 'last_90d')
    _append(records, 'Mood Diversity Index',     mood_diversity_index(v_90), 'last_90d')
    _append(records, 'Acoustic-Energy Balance',  acoustic_energy_balance(v_90), 'last_90d')
    _append(records, 'Groove Index',             groove_index(v_90), 'last_90d')
    _append(records, 'Vocalness Index',          vocalness_index(v_90), 'last_90d')
    _append(records, 'Ambient Factor',           ambient_factor(v_90), 'last_90d')
    _append(records, 'Commercial Pressure',      commercial_pressure(v_90), 'last_90d')
    _append(records, 'Mood Bias',                mood_bias(v_90), 'last_90d')
    _append(records, 'Total Listening Hours',    total_listening_hours(v_90), 'last_90d')
    _append(records, 'Average Tracks per Day',   average_tracks_per_day(v_90), 'last_90d')
    _append(records, 'Average Events per Day',   average_events_per_day(df_90_all), 'last_90d')

    _append(records, 'Music Day Share',          music_day_share(df_90_all), 'last_90d')
    _append(records, 'Listening Variability',    listening_variability(df_90_all), 'last_90d')
    _append(records, 'Listening Consistency Index',
            listening_consistency_index(df_90_all), 'last_90d')
    _append(records, 'Music Recency Index',      music_recency_index(v_90), 'last_90d')
    _append(records, 'Night Listening Share',    night_listening_share(v_90), 'last_90d')
    _append(records, 'Platform Desktop Share',   platform_desktop_share(v_90), 'last_90d')
    _append(records, 'Average Sessions per Day',
            average_sessions_per_day(df_90_all), 'last_90d')

    _append(records, 'Skip Risk Index',          skip_risk_index(df_90_all), 'last_90d')
    _append(records, 'Session Depth Index',
            session_depth_index(sessions, start_90, end_90), 'last_90d')
    _append(records, 'Repeat Listening Share',   repeat_listening_share(v_90), 'last_90d')
    _append(records, 'External Exposure Index',  external_exposure_index(v_90), 'last_90d')
    _append(records, 'Mean Played Fraction',     mean_played_fraction(v_90), 'last_90d')
    _append(records, 'Completion Rate',          completion_rate(v_90), 'last_90d')
    _append(records, 'Contextual Skip Ratio',    contextual_skip_ratio(df_90_all), 'last_90d')
    _append(records, 'Interrupted Session Share',
            interrupted_session_share(sessions, start_90, end_90), 'last_90d')

    _append(records, 'Social Music Share',
            social_music_share(v_90, uri_sets), 'last_90d')
    _append(records, 'Track Diversity Index',    track_diversity_index(v_90), 'last_90d')
    _append(records, 'Playlist Stickiness Rate',
            playlist_stickiness_rate(v_90, uri_sets), 'last_90d')
    _append(records, 'Top Artist Share',         top_artist_share(v_90), 'last_90d')
    _append(records, 'Active Playlist Days per Year',
            active_playlist_days_per_year(playlist_links, start_90, end_90), 'last_90d')

    return pd.DataFrame(records)

