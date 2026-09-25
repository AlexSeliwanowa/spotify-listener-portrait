"""Sound: подготовка ядра и применение кластеров.

Использует clustering.py для моделей.
Специфика Sound: отбор треков (валидные ∩ my_music) и применение
к ядрам разных окон.

Использование:
    from sound import prepare_core, apply_to_window

    core = prepare_core(df, start, end, my_music_uris)
    core = apply_to_window(core, scaler, kmeans, pca)
"""
import numpy as np
import pandas as pd


FEATURES = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']


# ============================================================================
# ОТБОР ЯДРА
# ============================================================================

def prepare_core(df, start, end, my_music_uris, features=FEATURES):
    """
    Ядро окна: валидно прослушанные треки ∩ my_music.

    Логика:
      valid_window = события с valid_play=True за [start, end]
      core_uris    = уникальные треки из valid_window ∩ my_music_uris
      core         = уникальные строки df по этим трекам + play_count

    Parameters
    ----------
    df : pd.DataFrame
        Должен иметь: valid_play, ts_naive, spotify_track_uri + features.
    start, end : pd.Timestamp
        Границы окна.
    my_music_uris : set
        URI «своей музыки» (лайки ∪ свои плейлисты).
    features : list
        Признаки для кластеризации.

    Returns
    -------
    pd.DataFrame — уникальные треки ядра с play_count. NaN в features отброшены.
    """
    valid_window = df[
        (df['valid_play']) &
        (df['ts_naive'] >= start) &
        (df['ts_naive'] <= end)
    ].copy()

    core_uris = set(valid_window['spotify_track_uri'].unique()) & my_music_uris

    core = df[
        df['spotify_track_uri'].isin(core_uris)
    ].drop_duplicates('spotify_track_uri').copy()

    play_count = (
        valid_window.groupby('spotify_track_uri').size()
        .reset_index(name='play_count')
    )
    core = core.merge(play_count, on='spotify_track_uri', how='left')
    core['play_count'] = core['play_count'].fillna(0).astype(int)

    return core.dropna(subset=features)


# ============================================================================
# ПРИМЕНЕНИЕ К ОКНУ
# ============================================================================

def apply_to_window(core, scaler, kmeans, pca, features=FEATURES):
    """
    Применяет обученные на global модели (scaler, kmeans, pca)
    к ядру конкретного окна.

    Логика:
      X       = scaler.transform(core[features])
      cluster = kmeans.predict(X)
      pc1, pc2 = pca.transform(X)
      distance_to_center = ||X - center(cluster)||

    Важно: кластеры одинаковы во всех окнах, потому что обучены
    на global. Иначе нельзя сравнивать «этот трек в global кластер 0,
    а в recent_6q — тоже кластер 0».

    Parameters
    ----------
    core : pd.DataFrame
        Результат prepare_core для нужного окна.
    scaler : StandardScaler
        Обучен на global.
    kmeans : KMeans
        Обучен на global.
    pca : PCA
        Обучен на global.
    features : list
        Тот же набор, что при обучении.

    Returns
    -------
    pd.DataFrame — core с добавленными cluster, pc1, pc2, distance_to_center.
    """
    X = scaler.transform(core[features].values)

    core = core.copy()
    core['cluster'] = kmeans.predict(X)

    X_pca = pca.transform(X)
    core['pc1'] = X_pca[:, 0]
    core['pc2'] = X_pca[:, 1]

    centers = kmeans.cluster_centers_
    core['distance_to_center'] = np.linalg.norm(
        X - centers[core['cluster']], axis=1
    )

    return core