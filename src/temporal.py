"""Temporal: работа со временем.

Примитивы:
    - compute_windows      — определение трёх окон (global / recent_6q / last_90d)
    - trim_cold_start      — отрезает холодный старт и неполный последний месяц

Окна и trim_cold_start — единый источник для всего проекта.
Ячейки и модули импортируют отсюда.
"""
import pandas as pd


# ============================================================================
# ПАРАМЕТРЫ (могут меняться от проекта к проекту)
# ============================================================================

RECENT_MONTHS = 18    # окно recent_6q
LAST_DAYS = 90        # окно last_90d
GAP_MONTHS = 1        # порог gap для trim_cold_start
FIRST_YEAR_MONTHS = 12  # длина «первого года» для проверки cold start


# ============================================================================
# ОКНА
# ============================================================================

def compute_windows(df: pd.DataFrame, playlist_links: pd.DataFrame) -> dict:
    """
    Определяет границы трёх окон и возвращает метаданные.

    Окна:
        global      — от первого события до последней даты
        recent_6q   — последние RECENT_MONTHS месяцев
        last_90d    — последние LAST_DAYS дней

    Конец окна — max из:
        - последнего валидного прослушивания
        - последнего добавления трека в плейлист

    Возвращает dict:
        max_data_date  — Timestamp
        recent_start   — Timestamp
        last90_start   — Timestamp
        windows        — dict {label: (start, end)}
    """
    max_valid_ts = df.loc[df['valid_play'], 'ts_naive'].max()
    max_added_ts = (
        pd.to_datetime(playlist_links['Added At'], errors='coerce')
          .dt.tz_localize(None)
          .max()
    )
    max_data_date = max(max_valid_ts, max_added_ts)

    recent_start = max_data_date - pd.DateOffset(months=RECENT_MONTHS)
    last90_start = max_data_date - pd.Timedelta(days=LAST_DAYS)

    windows = {
        'global':    (df['ts_naive'].min(), max_data_date),
        'recent_6q': (recent_start,         max_data_date),
        'last_90d':  (last90_start,         max_data_date),
    }

    return {
        'max_data_date': max_data_date,
        'recent_start':  recent_start,
        'last90_start':  last90_start,
        'windows':       windows,
    }


# ============================================================================
# TRIM COLD START
# ============================================================================

def trim_cold_start(df: pd.DataFrame,
                    gap_months: int = GAP_MONTHS) -> pd.DataFrame:
    """
    Отрезает неполный последний месяц и холодный старт.

    Правило cold start:
        если в первый год есть gap > gap_months без событий —
        история начинается после последнего такого gap.

    Требует: df['ts_naive'], df['period'] (создаётся в enrich.add_timestamps).

    Возвращает df без холодного старта и без неполного последнего месяца.
    """
    df = df.copy()

    # Fallback: period может не быть создан, если trim вызывается на голом df
    if 'period' not in df.columns:
        df['period'] = df['ts_naive'].dt.to_period('M')

    # --- Неполный последний месяц ---
    max_date = df['ts_naive'].max()
    last_month = max_date.to_period('M')
    if max_date.day < last_month.days_in_month:
        df = df[df['period'] < last_month]

    # --- Gap в первый год ---
    months_present = sorted(df['period'].unique())
    if not months_present:
        return df

    first_month = months_present[0]
    first_year_end = first_month + FIRST_YEAR_MONTHS
    cutoff = None

    for i in range(1, len(months_present)):
        gap = (months_present[i] - months_present[i - 1]).n
        if gap > gap_months and months_present[i] < first_year_end:
            cutoff = months_present[i]

    if cutoff is not None:
        df = df[df['period'] >= cutoff]

    return df