import streamlit as st

from data.loaders import load_parquet, load_portrait
from logic.profile import nearest_profile
from pdf_report import build_overview_personal_pdf


@st.cache_data(show_spinner=False)
def get_overview_pdf(selected_stage, basic_info, cfg):
    if selected_stage == 'last_90d':
        return None
    try:
        axes_ov = ['Discovery', 'Retention', 'Burnout', 'Variability']

        portrait = load_portrait()
        portrait_stage = portrait[portrait['stage'] == selected_stage].copy()
        if portrait_stage.empty:
            return None

        portrait_idx_ov = portrait_stage.set_index('axis')
        user_levels_ov = [portrait_idx_ov.loc[a, 'level'] for a in axes_ov]

        profile, _ = nearest_profile(user_levels_ov, cfg['profiles']['profiles'])
        if profile is None:
            return None

        dash_config = cfg['dashboard']
        theme_personal = dash_config['themes']['personal']
        color_key = dash_config['profile_colors'].get(profile['id'], 'accent_blue')
        profile_color = theme_personal.get(color_key, theme_personal['accent_blue'])

        kpi = load_parquet('kpi_summary.parquet')
        obs = load_parquet('behavior/obsessions_strong.parquet')

        signals = ['Music Day Share', 'Hipster Index',
                   'Repeat Listening Share', 'Playlist Stickiness Rate']
        stage_label_map = {
            'global': 'Lifetime',
            'recent_6q': 'Last 18 months',
            'last_90d': 'Last 90 days',
        }

        return build_overview_personal_pdf(
            stage_label=stage_label_map[selected_stage],
            period_min=str(basic_info['min_date']),
            period_max=str(basic_info['max_date']),
            profile=profile,
            profile_color=profile_color,
            portrait_idx=portrait_idx_ov,
            axes=axes_ov,
            user_levels=user_levels_ov,
            level_colors=dash_config['colors'],
            level_radius=dash_config['level_radius'],
            kpi_df=kpi,
            indices_display=cfg['indices_display'],
            selected_stage=selected_stage,
            obsessions_df=obs,
            signals=signals,
            app_title=dash_config['app_title'],
        )
    except Exception:
        return None