"""Bases: срезы df. Не добавляют колонок, только фильтруют строки.

Базы читают колонки, которые создал enrich (valid_play, period, ts_naive).
Без enrich упадут с KeyError.

Минимальный набор: all_events / valid / trimmed / trimmed_valid.
Эти четыре используются в 4+ ноутбуках проекта.

Остальные срезы (repeat, saved, my_music, foreign, orphan) — inline
в ячейках, потому что у каждого 1–2 потребителя.
"""
import pandas as pd

from temporal import trim_cold_start


def all_events(df: pd.DataFrame) -> pd.DataFrame:
    """Все события без фильтров."""
    return df


def valid(df: pd.DataFrame) -> pd.DataFrame:
    """
    Только валидные события (valid_play=True).

    Требует: df['valid_play'] (создан enrich.add_valid_play).
    """
    return df[df['valid_play']].copy()


def trimmed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Без холодного старта и без неполного последнего месяца.

    База для PELT-A, PELT-B, Cosine, Storm, Variability.
    Требует: df['period'], df['ts_naive'] (создан enrich.add_timestamps).
    """
    return trim_cold_start(df)


def trimmed_valid(df: pd.DataFrame) -> pd.DataFrame:
    """
    trimmed ∩ valid.

    База для PELT-A и Variability: только валидные события после
    обрезки холодного старта.
    """
    return valid(trimmed(df))