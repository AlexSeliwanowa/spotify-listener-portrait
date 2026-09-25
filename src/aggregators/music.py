"""Aggregator: музыкальные признаки по месяцам.

Свёртка событий в месячные медианы 6 звуковых признаков.
Вход — event-level df (уже с period). Выход — 70 строк, Period-индекс.

Используется PELT-A, Variability, Storm.
"""
import pandas as pd


SOUND_FEATURES = ['valence', 'energy', 'danceability',
                  'instrumentalness', 'acousticness', 'tempo']


def build_monthly_sound(df: pd.DataFrame) -> pd.DataFrame:
    """
    Медианы 6 звуковых признаков по месяцам.

    Требует: df['period'] (создан enrich.add_timestamps).

    Возвращает DataFrame с индексом period (Period 'M') и колонками:
        valence, energy, danceability, instrumentalness,
        acousticness, tempo, date
    """
    monthly = df.groupby('period').agg(
        **{f: (f, 'median') for f in SOUND_FEATURES}
    ).reset_index()
    monthly['date'] = monthly['period'].dt.to_timestamp()
    monthly = monthly.set_index('period').sort_index()
    return monthly