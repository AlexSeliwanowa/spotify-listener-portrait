import pandas as pd
import streamlit as st

from config import BASE_PATH, DASHBOARD_PATH, load_config
from logic.profile import PORTRAIT_AXIS_TO_INDEX

_CFG = load_config()
INDICES_DISPLAY = _CFG['indices_display']


@st.cache_data
def load_parquet(rel_path):
    path = DASHBOARD_PATH / rel_path
    if not path.exists():
        return None
    df = pd.read_parquet(path)

    from data.schemas import validate
    missing = validate(df, rel_path)
    if missing:
        st.error(
            f"Schema mismatch in `{rel_path}`. "
            f"Missing columns: {', '.join(missing)}. "
            f"Re-run the prep notebook."
        )
        return None

    return df





@st.cache_data
def load_portrait():
    df = pd.read_parquet(DASHBOARD_PATH / 'behavior' / 'portrait.parquet')

    def _level(row):
        idx = PORTRAIT_AXIS_TO_INDEX.get(row['axis'], row['axis'])
        t = INDICES_DISPLAY.get(idx, {}).get('thresholds')
        if not t or len(t) != 2:
            return None
        lo, hi = t
        if row['value'] < lo:
            return 'Low'
        if row['value'] <= hi:
            return 'Medium'
        return 'High'

    df['level'] = df.apply(_level, axis=1)
    return df


@st.cache_data
def load_kpi_summary():
    return pd.read_parquet(DASHBOARD_PATH / 'kpi_summary.parquet')


@st.cache_data
def load_basic_info():
    df = pd.read_parquet(DASHBOARD_PATH / 'eda_enriched.parquet')
    playlist_links = pd.read_parquet(BASE_PATH / 'playlist_links.parquet')
    max_valid_ts = df.loc[df['valid_play'], 'ts_naive'].max()
    max_added_ts = (
        pd.to_datetime(playlist_links['Added At'], errors='coerce')
          .dt.tz_localize(None)
          .max()
    )
    max_date = max(max_valid_ts, max_added_ts)

    recent_start = max_date - pd.DateOffset(months=18)
    last90_start = max_date - pd.Timedelta(days=90)

    windows = {
        'global': df,
        'recent_6q': df[df['ts_naive'] >= recent_start],
        'last_90d': df[df['ts_naive'] >= last90_start],
    }

    info = {}
    for stage, wdf in windows.items():
        wdf_valid = wdf[wdf['valid_play']]
        info[stage] = {
            'tracks': wdf_valid['spotify_track_uri'].nunique(),
            'events': len(wdf_valid),
        }

    info['min_date'] = df['ts_naive'].min().date()
    info['max_date'] = max_date.date()
    return info