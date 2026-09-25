"""Aggregators: temporal — временные ряды для дашборда.

Свёртка событий в периоды (M / W / D) для трёх окон.
Особенности:
    - NaN-строки для пропущенных периодов (реальный обрыв на графике)
    - is_post_gap: флаг «после холодного старта»
    - Цензура справа: неполный последний период исключается
    - База: df без trim — дашборд показывает полную историю
"""
import numpy as np
import pandas as pd
from helpers import is_desktop

# Частота периодов для каждого окна
AGG_WINDOWS = {
    'global':    'M',
    'recent_6q': 'W',
    'last_90d':  'D',
}


def build_time_series(df_input: pd.DataFrame,
                      window_label: str,
                      start, end,
                      freq: str,
                      first_post_gap_month=None) -> pd.DataFrame:
    """
    Временной ряд для одного окна.

    df_input: event-level df (без trim — дырки видны).
    first_post_gap_month: Period — граница плотной истории.
        Периоды до неё помечаются is_post_gap=False.
    Пропущенные периоды вставляются как NaN-строки (реальный обрыв).

    Возвращает DataFrame с колонками:
        period, date, hours, tracks, energy_mean, valence_mean,
        instrumentalness_mean, discovery_rate, completion_rate,
        skip_rate, desktop_share, is_post_gap
    """
    mask_window = ((df_input['ts_naive'] >= start) &
                   (df_input['ts_naive'] <= end))
    df_window = df_input.loc[mask_window].copy()
    df_window['period'] = df_window['ts_naive'].dt.to_period(freq)

    df_window['is_desktop'] = df_window['platform'].apply(is_desktop)

    
    df_window['is_complete'] = df_window['played_frac'] >= 0.90

    # Цензура справа: неполный последний период
    max_date_in_window = df_window['ts_naive'].max()
    last_period = max_date_in_window.to_period(freq)

    is_complete = True
    if freq == 'M':
        is_complete = max_date_in_window.day == last_period.days_in_month
    elif freq == 'W':
        days_in_last_week = df_window[
            df_window['period'] == last_period
        ]['ts_naive'].dt.date.nunique()
        is_complete = days_in_last_week >= 7

    if not is_complete:
        print(f"⚠️ Исключаем неполный период {last_period} из {window_label}")
        df_window = df_window[df_window['period'] < last_period]

    rows = []
    for period, group in df_window.groupby('period'):
        valid_group = group[group['valid_play']]
        if valid_group.empty:
            continue

        first_seen = (valid_group['first_valid_seen'].dropna()
                        .dt.to_period(freq))
        discovery_rate = ((first_seen == period).mean()
                          if not first_seen.empty else np.nan)

        rows.append({
            'date':                   period.start_time,
            'hours':                  valid_group['ms_played'].sum() / 3600000,
            'tracks':                 valid_group['spotify_track_uri'].nunique(),
            'energy_mean':            valid_group['energy'].mean(),
            'valence_mean':           valid_group['valence'].mean(),
            'instrumentalness_mean':  valid_group['instrumentalness'].mean(),
            'discovery_rate':         discovery_rate,
            'completion_rate':        valid_group['is_complete'].mean(),
            'skip_rate':              group['is_skip'].mean(),
            'desktop_share':          valid_group['is_desktop'].mean(),
        })

    if not rows:
        print(f"⚠️ {window_label}: нет данных")
        return pd.DataFrame()

    time_df = pd.DataFrame(rows).sort_values('date').reset_index(drop=True)

    # NaN-строки для пропущенных периодов
    full_range = pd.period_range(
        time_df['date'].min().to_period(freq),
        time_df['date'].max().to_period(freq),
        freq=freq,
    )
    time_df = (time_df
        .set_index(pd.PeriodIndex(time_df['date'], freq=freq))
        .reindex(full_range)
        .rename_axis('period')
        .reset_index())
    time_df['date'] = time_df['period'].dt.to_timestamp()

    # Флаг «после cold start» — asfreq с how='start' (начало периода)
    if first_post_gap_month is not None:
        if freq == 'M':
            gap_threshold = first_post_gap_month
        elif freq == 'W':
            gap_threshold = first_post_gap_month.asfreq('W', how='start')
        elif freq == 'D':
            gap_threshold = first_post_gap_month.asfreq('D', how='start')
        else:
            gap_threshold = first_post_gap_month
        time_df['is_post_gap'] = time_df['period'] >= gap_threshold
    else:
        time_df['is_post_gap'] = True

    return time_df


def build_time_series_meta(df: pd.DataFrame,
                            first_post_gap_month) -> pd.DataFrame:
    """
    Метаданные для time_series_*.

    Возвращает DataFrame из одной строки:
        first_event_month, first_post_gap_month, last_month,
        pause_months, n_pause_months, has_mid_history_gaps, mid_gaps
    """
    all_months = pd.period_range(df['period'].min(),
                                  df['period'].max(), freq='M')
    present = set(df['period'].unique())
    pause_months = sorted(all_months.difference(present))
    mid_gaps = [p for p in pause_months if p > first_post_gap_month]

    return pd.DataFrame([{
        'first_event_month':    str(df['period'].min()),
        'first_post_gap_month': str(first_post_gap_month),
        'last_month':           str(df['period'].max()),
        'pause_months':         '|'.join(str(p) for p in pause_months),
        'n_pause_months':       len(pause_months),
        'has_mid_history_gaps': len(mid_gaps) > 0,
        'mid_gaps':             '|'.join(str(p) for p in mid_gaps),
    }])
    