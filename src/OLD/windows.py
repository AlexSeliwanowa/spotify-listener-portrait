"""Временные окна проекта.

Единый источник правды для окна recent_6q и last_90d.

Все места (преп-нот, kpi_index, дашборд, эксперименты) должны читать
границы окон отсюда — иначе получится расхождение (было: 89 vs 90 дней).

Использование:
    from windows import compute_windows

    meta = compute_windows(df, playlist_links)
    max_data_date = meta['max_data_date']
    windows = meta['windows']
"""
import pandas as pd


RECENT_MONTHS = 18
LAST_DAYS = 90


def compute_windows(df: pd.DataFrame, playlist_links: pd.DataFrame):
    """
    Считает границы трёх окон: global, recent_6q, last_90d.

    Конец окна = max(последнее валидное прослушивание, последнее добавление
    в плейлист). Плейлисты могут обновляться после последнего прослушивания.

    Parameters
    ----------
    df : pd.DataFrame
        Требует колонок ts_naive (или ts) и valid_play.
    playlist_links : pd.DataFrame
        Требует колонки 'Added At'.

    Returns
    -------
    dict:
        max_data_date : pd.Timestamp
        recent_start  : pd.Timestamp
        last90_start  : pd.Timestamp
        windows       : dict {'global': (start, end), 'recent_6q': ..., 'last_90d': ...}
    """
    # ts_naive — если ещё не создан
    if 'ts_naive' not in df.columns:
        df = df.copy()
        df['ts_naive'] = pd.to_datetime(df['ts']).dt.tz_localize(None)

    # Max(последнее валидное, последнее добавление)
    valid_max = df.loc[df['valid_play'], 'ts_naive'].max()

    added_series = pd.to_datetime(playlist_links['Added At'], errors='coerce')
    if added_series.dt.tz is not None:
        added_series = added_series.dt.tz_localize(None)
    added_max = added_series.max()

    max_data_date = max(valid_max, added_max)
    recent_start = max_data_date - pd.DateOffset(months=RECENT_MONTHS)
    last90_start = max_data_date - pd.Timedelta(days=LAST_DAYS)

    windows = {
        'global':    (df['ts_naive'].min(), max_data_date),
        'recent_6q': (recent_start, max_data_date),
        'last_90d':  (last90_start, max_data_date),
    }

    return {
        'max_data_date': max_data_date,
        'recent_start': recent_start,
        'last90_start': last90_start,
        'windows': windows,
    }