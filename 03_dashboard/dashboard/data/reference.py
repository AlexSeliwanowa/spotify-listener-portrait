import pandas as pd
import streamlit as st

from data.loaders import DASHBOARD_PATH, load_portrait


@st.cache_data(show_spinner=False)
def build_reference_table():
    """Wide-format таблица: все индексы из kpi_summary + 4 оси из portrait."""
    kpi = pd.read_parquet(DASHBOARD_PATH / 'kpi_summary.parquet')

    wide = kpi.pivot_table(
        index=['index_name', 'unit', 'category'],
        columns='stage',
        values='value',
        aggfunc='first'
    ).reset_index()

    for s in ['global', 'recent_6q', 'last_90d']:
        if s not in wide.columns:
            wide[s] = pd.NA
    wide = wide[['index_name', 'unit', 'category',
                 'global', 'recent_6q', 'last_90d']]

    portrait = load_portrait()
    portrait_wide = portrait.pivot_table(
        index='axis',
        columns='stage',
        values='value',
        aggfunc='first'
    ).reset_index().rename(columns={'axis': 'index_name'})
    portrait_wide['unit'] = 'index'
    portrait_wide['category'] = 'profile'
    for s in ['global', 'recent_6q', 'last_90d']:
        if s not in portrait_wide.columns:
            portrait_wide[s] = pd.NA
    portrait_wide = portrait_wide[['index_name', 'unit', 'category',
                                   'global', 'recent_6q', 'last_90d']]

    for df in (wide, portrait_wide):
        for s in ['global', 'recent_6q', 'last_90d']:
            df[s] = pd.to_numeric(df[s], errors='coerce').astype('Float64')

    combined = pd.concat([wide, portrait_wide], ignore_index=True)

    cat_order = ['basic', 'temporal', 'behavioral', 'playlist', 'profile']
    combined['_rank'] = combined['category'].map(
        {c: i for i, c in enumerate(cat_order)}
    ).fillna(99)
    combined = combined.sort_values(['_rank', 'index_name']).drop(columns='_rank')
    combined = combined.reset_index(drop=True)

    return combined