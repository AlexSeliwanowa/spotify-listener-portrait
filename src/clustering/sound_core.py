"""Sound: подготовка ядра вкуса и применение кластеров.

Специфика Sound: отбор треков (валидные ∩ my_music) и применение
обученных на global моделей к ядрам разных окон.

Использование:
    from clustering.sound_core import prepare_core, apply_to_window

    core = prepare_core(df, start, end, my_music_uris)
    core = apply_to_window(core, scaler, kmeans, pca)
"""
import numpy as np
import pandas as pd


# ВНИМАНИЕ: это 5 признаков для кластеризации звука (без tempo).
# Не путать с SOUND_FEATURES из aggregators/music.py — там 6 признаков
# (включая tempo) для PELT-A / Variability.
CLUSTER_FEATURES = ['valence', 'energy', 'danceability',
                    'acousticness', 'instrumentalness']


def prepare_core(df, start, end, my_music_uris, features=CLUSTER_FEATURES):
    """
    Ядро окна: валидно прослушанные треки ∩ my_music.

    Логика:
      valid_window = события с valid_play=True за [start, end]
      core_uris    = уникальные треки из valid_window ∩ my_music_uris
      core         = уникальные строки df по этим трекам + play_count

    Returns
    -------
    pd.DataFrame — уникальные треки ядра с play_count.
        NaN в features отброшены.
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


def apply_to_window(core, scaler, kmeans, pca, features=CLUSTER_FEATURES):
    """
    Применяет обученные на global модели к ядру окна.

    Кластеры одинаковы во всех окнах (обучены на global) — иначе
    нельзя сравнивать «трек в global кластер 0, в recent_6q — тоже 0».

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