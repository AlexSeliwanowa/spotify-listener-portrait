"""Шторм-анализ: скорость изменений профиля.

Rolling std по 4 признакам → агрегат std_all → порог.
Эпизоды: 3+ штормовых месяца в окне ≤5.
"""
import numpy as np
import pandas as pd


STORM_FEATURES = ['valence', 'energy', 'danceability', 'instrumentalness']
WINDOW = 3
K_MAD = 1.5


def detect(monthly_sound: pd.DataFrame,
           features=STORM_FEATURES,
           window: int = WINDOW,
           k_mad: float = K_MAD) -> dict:
    """
    Возвращает:
        df: DataFrame с колонками [std_all, is_storm, episode_id]
        threshold: порог шторма
        episodes: список списков Period — эпизоды
    """
    ms = monthly_sound.copy()
    for f in features:
        ms[f] = ms[f].fillna(ms[f].median())

    for f in features:
        ms[f'{f}_std'] = ms[f].rolling(window, center=True, min_periods=2).std()

    std_cols = [f'{f}_std' for f in features]
    ms['std_all'] = ms[std_cols].mean(axis=1)

    valid = ms['std_all'].dropna()
    med = valid.median()
    mad = np.median(np.abs(valid - med))
    threshold = med + k_mad * mad

    ms['is_storm'] = ms['std_all'] > threshold

    # Группировка в эпизоды: 3+ штормовых в окне ≤5
    storm_months = ms[ms['is_storm']].index.tolist()
    episodes = []
    if storm_months:
        current = [storm_months[0]]
        for m in storm_months[1:]:
            if (m - current[-1]).n <= 5:
                current.append(m)
            else:
                if len(current) >= 3:
                    episodes.append(current)
                current = [m]
        if len(current) >= 3:
            episodes.append(current)

    ms['episode_id'] = None
    for i, ep in enumerate(episodes, 1):
        for m in ep:
            ms.loc[m, 'episode_id'] = i

    df_out = ms[['std_all', 'is_storm', 'episode_id']].reset_index()
    df_out['date'] = df_out['period'].dt.to_timestamp()
    df_out = df_out[['date', 'std_all', 'is_storm', 'episode_id']]

    return {
        'df': df_out,
        'threshold': threshold,
        'episodes': episodes,
    }