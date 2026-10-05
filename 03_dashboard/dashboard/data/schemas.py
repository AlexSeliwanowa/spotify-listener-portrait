import re


SCHEMAS = {
    # Sound
    r'sound/sound_core_(\w+)\.parquet': [
        'track_name', 'artist_name', 'valence', 'energy', 'danceability',
        'acousticness', 'instrumentalness', 'popularity', 'genres_normalized',
        'cluster', 'play_count', 'pc1', 'pc2', 'distance_to_center',
        'is_characteristic',
    ],
    r'sound/sound_clustering_meta\.parquet': [
        'k', 'silhouette', 'n_tracks', 'threshold', 'passed',
    ],

    # Time
    r'time/time_series_(global|recent_6q|last_90d)\.parquet': [
        'period', 'date', 'hours', 'tracks', 'energy_mean', 'valence_mean',
        'instrumentalness_mean', 'discovery_rate', 'completion_rate',
        'skip_rate', 'desktop_share', 'is_post_gap',
    ],
    r'time/time_series_meta\.parquet': [
        'first_event_month', 'first_post_gap_month', 'last_month',
        'pause_months', 'n_pause_months', 'has_mid_history_gaps', 'mid_gaps',
    ],
    r'time/time_changepoints\.parquet': [
        'date', 'method', 'layer', 'confidence',
    ],
    r'time/time_storms\.parquet': [
        'date', 'std_all', 'is_storm', 'episode_id',
    ],
    r'time/variability\.parquet': [
        'period', 'score',
    ],
    r'time/variability_meta\.parquet': [
        'short_history', 'n_transitions', 'n_valid_rolling_points', 'window',
        'seed', 'n_boot_transitions', 'n_boot_score', 'lifetime_score',
        'current_score', 'null_low', 'null_high',
    ],
    r'time/feature_contributions\.parquet': [
        'period_to', 'feature', 'contribution',
    ],
    r'time/epochs_sound\.parquet': [
        'start', 'end', 'duration_months', 'max_score', 'mean_score',
    ],

    # Behavior
    r'behavior/obsessions_base_(\w+)\.parquet': [
        'date', 'obsession_share',
    ],
    r'behavior/obsessions_strong\.parquet': [
        'track_uri', 'track_name', 'artist_name', 'date', 'repeats', 'hours',
    ],
    r'behavior/portrait\.parquet': [
        'axis', 'value', 'short_history', 'stage',
    ],
    r'behavior/behavior_funnel_events\.parquet': [
        'stage', 'count', 'share_from_first', 'share_from_previous',
    ],
    r'behavior/behavior_funnel_tracks\.parquet': [
        'stage', 'count', 'share_from_first', 'share_from_previous',
    ],
    r'behavior/behavior_skip_by_source\.parquet': [
        'source', 'total', 'skip_rate', 'full_play_rate', 'valid_rate', 'stage',
    ],
    r'behavior/behavior_skip_by_genre\.parquet': [
        'genre', 'total', 'skip_rate', 'full_play_rate', 'stage',
    ],
    r'behavior/behavior_cohorts\.parquet': [
        'cohort', 'retention_30d', 'retention_90d', 'retention_180d',
    ],

    # Collection
    r'collection/playlist_portraits\.parquet': [
        'playlist_name', 'playlist_type', 'total_tracks', 'mode_release_year',
        'decade_2020s', 'decade_2010s', 'decade_2000s', 'decade_pre_2000',
        'valence_med', 'energy_med', 'danceability_med', 'acousticness_med',
        'instrumentalness_med', 'tempo_med', 'popularity_med', 'top_genres',
        'unique_genres', 'genre_diversity', 'share_listened',
        'skip_rate_all_events', 'full_play_share_valid', 'total_valid_listens',
        'top_tracks',
    ],
    r'collection/playlist_collaborators\.parquet': [
        'playlist_name', 'added_by_id', 'display_name', 'additions', 'role',
    ],
    r'collection/collection_fill_summary\.parquet': [
        'fill_type', 'playlists', 'avg_size', 'total_listens', 'share',
    ],
    r'collection/collection_activity_scatter\.parquet': [
        'name_norm', 'playlist_type', 'total_listens', 'unique_tracks',
        'num_tracks', 'days_since_update', 'fill_type', 'activity_group',
    ],

    # Root
    r'kpi_summary\.parquet': [
        'id', 'index_name', 'value', 'unit', 'stage', 'category', 'audience',
    ],
}


def get_required_columns(rel_path):
    """Найти список обязательных колонок по пути паркета. None — если схемы нет."""
    for pattern, cols in SCHEMAS.items():
        if re.fullmatch(pattern, rel_path):
            return cols
    return None


def validate(df, rel_path):
    """Проверить, что все колонки из схемы есть в df.
    Возвращает список пропавших колонок (пустой — если всё ок)."""
    required = get_required_columns(rel_path)
    if required is None:
        return []
    return [c for c in required if c not in df.columns]