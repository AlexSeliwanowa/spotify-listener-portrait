import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from data.loaders import load_parquet, load_kpi_summary, load_portrait, load_basic_info, DASHBOARD_PATH


from logic.profile import nearest_profile
from logic.formatting import format_table_value
from ui.components import (
    render_personal_card_variant,
    render_single_variant_v4_capsules,
    render_compass,
)


def _build_reference_table(cfg):
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


def _shift_color(idx_name, cur, prev, theme, indices_display):
    polarity = indices_display.get(idx_name, {}).get('polarity', 'neutral')
    if polarity == 'neutral':
        return theme['text']
    went_up = cur > prev
    is_good = (went_up and polarity == 'higher_better') or (not went_up and polarity == 'lower_better')
    return theme['accent_green'] if is_good else theme['accent_pink']


def render(mode, selected_stage, cfg):
    theme = cfg['dashboard']['themes'][mode.lower()]
    kpi_summary = load_kpi_summary()

    st.markdown("<div class='ui-title'>Overview</div>", unsafe_allow_html=True)


    if mode == 'Personal':
        _render_personal(kpi_summary, selected_stage, theme, cfg)
    elif mode == 'Professional':
        _render_professional(kpi_summary, selected_stage, theme, cfg)


def _render_personal(kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    profiles = cfg['profiles']['profiles']

    st.markdown(
        "<div class='ui-subtitle'>"
        "Your music story at a glance — who you are, how you listen, and where you're heading."
        "</div>",
        unsafe_allow_html=True
    )

    portrait_ov = load_portrait()

    if portrait_ov is not None and not portrait_ov.empty:
        if selected_stage == 'last_90d':
            portrait_ov = None
        else:
            portrait_ov = portrait_ov[portrait_ov['stage'] == selected_stage].copy()

    if portrait_ov is None and selected_stage == 'last_90d':
        st.info("Listener profile requires at least 12 months of data. "
                "Switch to Lifetime or Last 18 months.")

    axes_ov = ['Discovery', 'Retention', 'Burnout', 'Variability']
    profile_ov = None
    portrait_idx_ov = None
    user_levels_ov = None
    profile_color_ov = theme['accent_blue']

    if portrait_ov is not None and not portrait_ov.empty:
        portrait_idx_ov = portrait_ov.set_index('axis')
        user_levels_ov = [portrait_idx_ov.loc[a, 'level'] for a in axes_ov]

        profile_ov, _ = nearest_profile(user_levels_ov, profiles)

        if profile_ov:
            color_key_ov = dash_config['profile_colors'].get(profile_ov['id'], 'accent_blue')
            profile_color_ov = theme.get(color_key_ov, theme['accent_blue'])

            st.markdown(
                f"<div style='font-size:2.4rem; font-weight:900; "
                f"color:{profile_color_ov}; margin-top:14px; margin-bottom:8px; "
                f"line-height:1.1'>{profile_ov['name_en']}</div>"
                f"<div style='font-size:1.25rem; color:{profile_color_ov}; "
                f"opacity:0.95; font-style:italic; line-height:1.4'>"
                f"{profile_ov['personal_phrase_en']}</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    if portrait_ov is not None and not portrait_ov.empty:
        render_compass(portrait_idx_ov, axes_ov, user_levels_ov, profile_color_ov,
                       theme, cfg, height=380, key='overview_personal_compass')

    st.markdown("---")

    st.markdown(
        "<div class='ui-section'>Your signals at a glance</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Four numbers that describe your listening right now."
        "</div>",
        unsafe_allow_html=True
    )

    overview_cards = [
        ('Music Day Share', 'Rhythm'),
        ('Hipster Index', 'Sound'),
        ('Repeat Listening Share', 'Habit'),
        ('Playlist Stickiness Rate', 'Collection'),
    ]

    cols = st.columns(4)
    for col, (idx_name, display) in zip(cols, overview_cards):
        with col:
            render_personal_card_variant(
                'B', idx_name, kpi_summary, selected_stage, theme, cfg, mode='Personal',
                key_extra=f'overview_{idx_name}',
                display_name=display
            )

    st.markdown("---")

    obs_strong_ov = load_parquet('behavior/obsessions_strong.parquet')
    if obs_strong_ov is not None and not obs_strong_ov.empty:
        top_obs = obs_strong_ov.nlargest(1, 'repeats').iloc[0]
        st.markdown(
            f"<div class='ui-section'>Your most intense obsession</div>"
            f"<div style='font-size:1.4rem; color:{theme['text']}; "
            f"margin-top:8px; line-height:1.3'>"
            f"<b>{top_obs['track_name']}</b> — {top_obs['artist_name']}</div>"
            f"<div style='font-size:1rem; color:{theme['text']}; opacity:0.75; "
            f"margin-top:4px'>"
            f"{int(top_obs['repeats'])} repeats in a row · {top_obs['hours']:.1f} hours</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )

#==============professional=================================


def _render_professional(kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    indices_display = cfg['indices_display']
    profiles = cfg['profiles']['profiles']
    takeaway = cfg['takeaway']
    professional_theme = dash_config['themes']['professional']

    st.markdown(
        "<div class='ui-subtitle'>"
        "Listener overview — key indices across sound, time, behavior, and collection."
        "</div>",
        unsafe_allow_html=True
    )

    st.caption("Base: valid plays.")
    st.markdown("---")
    period_accent_map = {
        'global': professional_theme.get('accent_blue', professional_theme['accent_blue']),
        'recent_6q': professional_theme.get('accent_cyan', professional_theme['accent_blue']),
        'last_90d': professional_theme.get('accent_purple', professional_theme['accent_blue']),
    }
    period_accent = period_accent_map.get(selected_stage, professional_theme['accent_blue'])

    kpi_ov = kpi_summary
    portrait_ov_all = load_portrait()

    profile_ov = None
    match_dist_ov = None
    portrait_idx_ov = None
    axes_ov = ['Discovery', 'Retention', 'Burnout', 'Variability']

    if portrait_ov_all is not None and not portrait_ov_all.empty:
        portrait_ov = portrait_ov_all[portrait_ov_all['stage'] == 'global'].copy()
        if not portrait_ov.empty:
            portrait_idx_ov = portrait_ov.set_index('axis')
            user_levels_ov = [portrait_idx_ov.loc[a, 'level'] for a in axes_ov]
            profile_ov, match_dist_ov = nearest_profile(user_levels_ov, profiles)

    profile_color_ov = theme['accent_blue']
    if profile_ov:
        color_key_ov = dash_config['profile_colors'].get(profile_ov['id'], 'accent_blue')
        profile_color_ov = theme.get(color_key_ov, theme['accent_blue'])


    st.markdown(
        "<div class='ui-section'>Listener profile</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Listener archetype based on four portrait axes — computed on the full history."        "</div>",
        unsafe_allow_html=True
    )

    if profile_ov and portrait_idx_ov is not None:
        levels_str = ' · '.join(
            f"{a} {portrait_idx_ov.loc[a, 'level']}"
            for a in axes_ov
        )
        st.markdown(
            f"<div style='font-size:2.2rem; font-weight:900; "
            f"color:{profile_color_ov}; line-height:1.15; margin-bottom:8px'>"
            f"{profile_ov['name_en']}</div>"
            f"<div style='font-size:1rem; color:{theme['text']}; opacity:0.8; "
            f"line-height:1.4; margin-bottom:6px'>{levels_str}</div>"
            f"<div style='font-size:0.85rem; opacity:0.55; "
            f"color:{theme['text']}'>"
            f"Match distance: {match_dist_ov:.2f} · computed on full history</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='font-size:1.05rem; color:{theme['text']}; "
            f"opacity:0.75; line-height:1.4'>No profile data available.</div>",
            unsafe_allow_html=True
        )





    st.markdown("---")


    takeaways_ov = []
    if portrait_idx_ov is not None:
        for axis in ['discovery', 'retention', 'burnout', 'variability']:
            level = portrait_idx_ov.loc[axis.capitalize(), 'level']
            level_key = level.lower() if level in ['Low', 'Medium', 'High'] else 'low'
            if axis in takeaway.get('behavior', {}):
                t = (takeaway['behavior'][axis].get(level.capitalize() + '_en')
                     or takeaway['behavior'][axis].get(level_key))
                if t:
                    takeaways_ov.append(t)

    if takeaways_ov:
        bg_color = 'rgba(0, 0, 0, 0.04)'
        bullets_html = (
            f"<div style='background:{bg_color}; "
            f"border-radius:10px; padding:20px 24px; "
            f"border-left:3px solid {profile_color_ov}'>"
            f"<div class='ui-section' style='margin-top:0'>Key takeaways</div>"
            f"<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            f"Recommendations derived from the listener archetype (full history)."
            f"</div>"
        )
        for t in takeaways_ov:
            bullets_html += (
                f"<div style='font-size:1rem; color:{profile_color_ov}; "
                f"line-height:1.5; margin-bottom:8px'>— {t}</div>"
            )
        bullets_html += "</div>"
        st.markdown(bullets_html, unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='ui-section'>Key takeaways</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "Recommendations derived from the listener archetype (full history)."
            "</div>",
            unsafe_allow_html=True
        )
        st.caption("No takeaways available.")

    st.markdown("---")

    st.markdown(
        "<div class='ui-section'>Snapshot across all areas</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Six key indices — one per major area."
        "</div>",
        unsafe_allow_html=True
    )

    snapshot_indices = [
        'Hipster Index',
        'Genre Diversity Index',
        'Listening Consistency Index',
        'Platform Desktop Share',
        'Repeat Listening Share',
        'Playlist Stickiness Rate',
    ]
    for start in [0, 3]:
        cols_ov = st.columns(3)
        for col, idx_name in zip(cols_ov, snapshot_indices[start:start+3]):
            with col:
                render_single_variant_v4_capsules(
                    idx_name, kpi_ov, selected_stage, theme, cfg, mode='Professional',
                    key_extra=f'overview_{start}'
                )

    st.markdown("---")

    st.markdown(
        "<div class='ui-section'>Biggest shift in selected period</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Relative shifts in proportional metrics (absolute volumes excluded)."
        "</div>",
        unsafe_allow_html=True
    )

    if selected_stage == 'global':
        st.info(
            "Biggest shift compares the selected window against the previous one. "
            "Switch to Last 18 months or Last 90 days to see it."
        )
    elif kpi_ov is not None and not kpi_ov.empty:
        prev_stage = 'recent_6q' if selected_stage == 'last_90d' else 'global'
        ABSOLUTE_UNITS = {'hours', 'days', 'count'}

        shifts = []
        for idx_name in kpi_ov['index_name'].unique():
            cur = kpi_ov[(kpi_ov['index_name'] == idx_name) & (kpi_ov['stage'] == selected_stage)]
            prev = kpi_ov[(kpi_ov['index_name'] == idx_name) & (kpi_ov['stage'] == prev_stage)]
            if cur.empty or prev.empty:
                continue
            unit = cur.iloc[0]['unit']
            if unit in ABSOLUTE_UNITS:
                continue
            v_cur = cur.iloc[0]['value']
            v_prev = prev.iloc[0]['value']
            if v_prev == 0:
                continue
            pct = abs((v_cur - v_prev) / v_prev)
            if pct < 0.05:
                continue
            shifts.append({
                'index': idx_name, 'prev': v_prev,
                'cur': v_cur, 'pct': pct, 'unit': unit,
            })

        if not shifts:
            st.caption("No significant shifts above 5% in this period.")
        else:
            shifts_sorted = sorted(shifts, key=lambda x: x['pct'], reverse=True)
            top_shift = shifts_sorted[0]

            def fmt_shift(v, unit):
                if unit == 'percent':
                    return f"{v * 100:.0f}%"
                elif unit == 'hours':
                    return f"{v:.0f}h"
                elif unit == 'days':
                    return f"{v:.0f}d"
                elif unit == 'count':
                    return f"{v:.1f}"
                return f"{v:.2f}"

            direction = "↑" if top_shift['cur'] > top_shift['prev'] else "↓"
            dir_color = _shift_color(top_shift['index'], top_shift['cur'], top_shift['prev'], theme, indices_display)

            html_parts = [
                f"<div style='border:1px solid {period_accent}; border-radius:10px; "
                f"padding:20px; background:transparent'>",
                f"<div style='font-size:1.3rem; color:{theme['text']}; "
                f"line-height:1.4; margin-bottom:12px'>"
                f"<b>{top_shift['index']}</b> changed by "
                f"<span style='color:{dir_color}; font-weight:700'>"
                f"{direction} {top_shift['pct'] * 100:.0f}%</span></div>",
                f"<div style='font-size:0.95rem; opacity:0.7; "
                f"color:{theme['text']}; margin-bottom:16px'>"
                f"{STAGE_LABELS[prev_stage]}: {fmt_shift(top_shift['prev'], top_shift['unit'])} → "
                f"{STAGE_LABELS[selected_stage]}: {fmt_shift(top_shift['cur'], top_shift['unit'])}"
                f"</div>",
            ]

            if len(shifts_sorted) > 1:
                html_parts.append(
                    f"<div style='font-size:0.8rem; opacity:0.55; "
                    f"color:{theme['text']}; text-transform:uppercase; "
                    f"letter-spacing:1px; margin-bottom:8px'>Next movers</div>"
                )
                for s in shifts_sorted[1:3]:
                    dir_s = "↑" if s['cur'] > s['prev'] else "↓"
                    dir_s_color = _shift_color(s['index'], s['cur'], s['prev'], theme, indices_display)
                    html_parts.append(
                        f"<div style='font-size:0.95rem; color:{theme['text']}; "
                        f"margin-bottom:6px; line-height:1.4'>"
                        f"{s['index']}: "
                        f"<span style='color:{dir_s_color}; font-weight:600'>"
                        f"{dir_s} {s['pct'] * 100:.0f}%</span> "
                        f"<span style='opacity:0.6; font-size:0.85rem'>"
                        f"({fmt_shift(s['prev'], s['unit'])} → {fmt_shift(s['cur'], s['unit'])})"
                        f"</span></div>"
                    )

            html_parts.append("</div>")
            st.markdown(''.join(html_parts), unsafe_allow_html=True)

    st.markdown("---")
    with st.expander('All indices — full reference'):
        ref = _build_reference_table(cfg)

        cat_labels = {
            'basic': 'Basic',
            'temporal': 'Temporal',
            'behavioral': 'Behavioral',
            'playlist': 'Playlist',
            'profile': 'Listener profile axes',
        }

        html = (
            '<table style="width:100%; border-collapse:collapse; font-size:0.9rem">'
            '<thead><tr>'
            '<th style="text-align:left; padding:8px 12px; '
            'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600">Index</th>'
            '<th style="text-align:left; padding:8px 12px; '
            'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600; '
            'font-size:0.8rem; opacity:0.6">Unit</th>'
            '<th style="text-align:right; padding:8px 12px; '
            'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600">Lifetime</th>'
            '<th style="text-align:right; padding:8px 12px; '
            'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600">Last 18mo</th>'
            '<th style="text-align:right; padding:8px 12px; '
            'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600">Last 90d</th>'
            '</tr></thead><tbody>'
        )

        current_cat = None
        for _, row in ref.iterrows():
            cat = row['category']
            if cat != current_cat:
                current_cat = cat
                label = cat_labels.get(cat, cat)
                html += (
                    f'<tr><td colspan="5" style="padding:14px 12px 6px 12px; '
                    f'font-weight:700; font-size:0.8rem; text-transform:uppercase; '
                    f'letter-spacing:1px; opacity:0.55; '
                    f'border-bottom:1px solid rgba(128,128,128,0.2)">'
                    f'{label}</td></tr>'
                )

            unit = row['unit']
            html += '<tr>'
            html += (
                f'<td style="padding:6px 12px; '
                f'border-bottom:1px solid rgba(128,128,128,0.1)">'
                f'{row["index_name"]}</td>'
            )
            html += (
                f'<td style="padding:6px 12px; '
                f'border-bottom:1px solid rgba(128,128,128,0.1); '
                f'font-size:0.8rem; opacity:0.6">'
                f'{unit}</td>'
            )
            for stage in ['global', 'recent_6q', 'last_90d']:
                html += (
                    f'<td style="padding:6px 12px; text-align:right; '
                    f'border-bottom:1px solid rgba(128,128,128,0.1)">'
                    f'{format_table_value(row[stage], unit)}</td>'
                )
            html += '</tr>'

        html += '</tbody></table>'
        st.markdown(html, unsafe_allow_html=True)

        st.caption(
            "Axes in 'Listener profile axes' are computed on the full history "
            "and reused as-is across windows. All other indices are recomputed "
            "per window."
        )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )


STAGE_LABELS = {'global': 'Lifetime', 'recent_6q': 'Last 18mo', 'last_90d': 'Last 90d'}