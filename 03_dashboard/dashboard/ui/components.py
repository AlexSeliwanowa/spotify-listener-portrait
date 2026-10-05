import streamlit as st
import plotly.graph_objects as go
import numpy as np

from logic.formatting import format_value, is_borderline


STAGE_ORDER = ['global', 'recent_6q', 'last_90d']
STAGE_LABELS = {'global': 'Lifetime', 'recent_6q': 'Last 18mo', 'last_90d': 'Last 90d'}


def render_single_variant_v3_dot(index_name, kpi_df, selected_stage, theme, cfg, mode,
                                  key_extra='', phrase_placement='popover'):
    indices_display = cfg['indices_display']
    dash_config = cfg['dashboard']

    rows = kpi_df[kpi_df['index_name'] == index_name].set_index('stage')
    available = [s for s in STAGE_ORDER if s in rows.index]

    if not available:
        with st.container(border=True):
            st.markdown(f"**{index_name}**")
            st.caption("no data")
        return

    effective_stage = selected_stage if selected_stage in available else available[-1]
    values = {s: rows.loc[s, 'value'] for s in available}
    unit = rows.loc[effective_stage, 'unit']
    neutral = theme['text']

    accent_map = {
        'global': theme.get('accent_blue', theme['accent_blue']),
        'recent_6q': theme.get('accent_cyan', theme['accent_blue']),
        'last_90d': theme.get('accent_purple', theme['accent_blue']),
    }
    accent = accent_map.get(effective_stage, theme['accent_blue'])

    idx_info = indices_display.get(index_name, {})

    is_dark = theme['bg'].lower() in ('#0f0c1b', '#1d1833')
    fill_color = 'rgba(255,255,255,0.06)' if is_dark else 'rgba(0,0,0,0.05)'

    thresholds = idx_info.get('thresholds')
    if thresholds and len(thresholds) == 2:
        low_t, high_t = thresholds
        v = values[effective_stage]
        if v < low_t:
            level = 'low'
        elif v <= high_t:
            level = 'medium'
        else:
            level = 'high'
    else:
        level = None

    if mode == 'Professional':
        main_phrase = idx_info.get('professional_messages', {}).get(level or 'default', '')
        notes = idx_info.get('notes_en', '')
    else:
        main_phrase = idx_info.get('personal_messages', {}).get(level or 'default', '')
        notes = idx_info.get('description_en', '')

    if main_phrase and '{value' in main_phrase:
        try:
            main_phrase = main_phrase.format(value=values[effective_stage])
        except (KeyError, ValueError, IndexError):
            pass

    with st.container(border=True, key=f"pro-card-v3-{index_name}-{effective_stage}-{key_extra}"):
        head_col1, head_col2 = st.columns([6, 1])
        with head_col1:
            st.markdown(
                f"<div style='font-size:1.5rem; font-weight:700; "
                f"color:{neutral}; margin-top:12px; margin-bottom:2px; line-height:1.15; "
                f'display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; '
                f"overflow:hidden; min-height:3.45rem'>{index_name}</div>",
                unsafe_allow_html=True
            )
        with head_col2:
            if notes or (main_phrase and phrase_placement == 'popover'):
                with st.popover("ⓘ", width='content', key=f'popover_v3_{index_name}_{effective_stage}_{key_extra}'):
                    st.markdown(f"**{index_name}**")
                    if main_phrase and phrase_placement == 'popover':
                        st.markdown(main_phrase)
                    if notes:
                        st.caption(notes)

        polarity = idx_info.get('polarity', 'neutral')

        val_str = format_value(values[effective_stage], unit) + ('≈' if is_borderline(values[effective_stage], thresholds) else '')
        diff = None
        if effective_stage == 'last_90d' and 'recent_6q' in available:
            diff = values['last_90d'] - values['recent_6q']
        elif effective_stage == 'recent_6q' and 'global' in available:
            diff = values['recent_6q'] - values['global']

        delta_html = ''
        if diff is not None:
            d_str = format_value(diff, unit)
            if diff > 1e-9:
                d_str = '+' + d_str

            is_good = is_bad = False
            if mode == 'Professional' and polarity != 'neutral':
                if polarity == 'higher_better':
                    is_good, is_bad = diff > 1e-9, diff < -1e-9
                else:
                    is_good, is_bad = diff < -1e-9, diff > 1e-9

            if is_good:
                delta_color = "#4AA85C"
            elif is_bad:
                delta_color = "#AE2B28"
            else:
                delta_color = neutral

            delta_html = (f"<span style='font-size:1rem; color:{delta_color}; "
                          f"margin-left:10px; font-weight:500'>{d_str}</span>")

        if phrase_placement == 'inline' and main_phrase:
            good = bad = False
            if mode == 'Professional' and level and polarity != 'neutral':
                if polarity == 'higher_better':
                    good, bad = level == 'high', level == 'low'
                elif polarity == 'lower_better':
                    good, bad = level == 'low', level == 'high'

            if good:
                phrase_color = dash_config['colors']['high']
            elif bad:
                phrase_color = dash_config['colors']['low']
            else:
                phrase_color = accent
            st.markdown(
                f"<div style='display:flex; flex-wrap:wrap; align-items:flex-start; gap:8px; margin:4px 0 12px 0'>"
                f"<div style='flex:0 0 auto; font-size:2rem; font-weight:700; color:{accent}; line-height:1.05; white-space:nowrap'>{val_str}{delta_html}</div>"
                f"<div style='flex:1 1 140px; font-size:1rem; color:{phrase_color}; font-weight:500; line-height:1.2; text-align:left; "
                f'display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden' f"'>{main_phrase}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='font-size:2rem; font-weight:700; color:{accent}; "
                f"margin:2px 0 12px 0; line-height:1.05'>{val_str}{delta_html}</div>",
                unsafe_allow_html=True
            )

        if len(available) < 2:
            st.caption(f"Only available for {STAGE_LABELS[available[0]]}")
            notes = idx_info.get('notes_en', '')
            if notes:
                st.markdown(
                    f"<div style='font-size:1rem; opacity:0.7; "
                    f"color:{neutral}; margin-top:10px; line-height:1.45'>"
                    f"{notes}</div>",
                    unsafe_allow_html=True
                )
            return

        vals = [values[s] for s in available]
        x_pos = [STAGE_ORDER.index(s) for s in available]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_pos, y=vals,
            mode='lines',
            line=dict(width=0),
            fill='tozeroy',
            fillcolor=fill_color,
            hoverinfo='skip',
            showlegend=False
        ))

        for i, s in enumerate(available):
            is_sel = (s == effective_stage)
            fig.add_trace(go.Scatter(
                x=[STAGE_ORDER.index(s)], y=[vals[i]],
                mode='markers+text',
                marker=dict(size=20 if is_sel else 11,
                            color=accent if is_sel else 'rgba(128,128,128,0.5)'),
                text=[format_value(vals[i], unit)],
                textposition='top center',
                textfont=dict(color=accent if is_sel else neutral, size=11),
                hoverinfo='skip',
                showlegend=False
            ))

        y_max = max(vals) if max(vals) > 0 else 0.1
        y_range_top = y_max * 1.35

        fig.update_layout(
            height=130,
            margin=dict(t=30, b=25, l=0, r=0),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False, zeroline=False,
                tickvals=[0, 1, 2],
                ticktext=[STAGE_LABELS[s] for s in STAGE_ORDER],
                tickfont=dict(size=9, color=neutral),
                range=[-0.2, 2.2]
            ),
            yaxis=dict(visible=False, range=[-0.01, y_range_top]),
            showlegend=False
        )
        st.plotly_chart(fig, width='stretch',
                        config={'displayModeBar': False},
                        key=f'v3_dot_{index_name}_{effective_stage}_{key_extra}')


def render_single_variant_v4_capsules(index_name, kpi_df, selected_stage, theme, cfg, mode, key_extra=''):
    indices_display = cfg['indices_display']
    dash_config = cfg['dashboard']

    rows = kpi_df[kpi_df['index_name'] == index_name].set_index('stage')
    available = [s for s in STAGE_ORDER if s in rows.index]

    if not available:
        with st.container(border=True, key=f"pro-card-v4-{index_name}-{effective_stage}-{key_extra}"):
            st.markdown(f"**{index_name}**")
            st.caption("no data")
        return

    effective_stage = selected_stage if selected_stage in available else available[-1]
    values = {s: rows.loc[s, 'value'] for s in available}
    unit = rows.loc[effective_stage, 'unit']
    neutral = theme['text']

    accent_map = {
        'global': theme.get('accent_blue', theme['accent_blue']),
        'recent_6q': theme.get('accent_cyan', theme['accent_blue']),
        'last_90d': theme.get('accent_purple', theme['accent_blue']),
    }
    accent = accent_map.get(effective_stage, theme['accent_blue'])

    idx_info = indices_display.get(index_name, {})

    thresholds = idx_info.get('thresholds')
    if thresholds and len(thresholds) == 2:
        low_t, high_t = thresholds
        v = values[effective_stage]
        if v < low_t:
            level = 'low'
        elif v <= high_t:
            level = 'medium'
        else:
            level = 'high'
    else:
        level = None

    if mode == 'Professional':
        main_phrase = idx_info.get('professional_messages', {}).get(level or 'default', '')
        notes = idx_info.get('notes_en', '')
    else:
        main_phrase = idx_info.get('personal_messages', {}).get(level or 'default', '')
        notes = idx_info.get('description_en', '')

    if main_phrase and '{value' in main_phrase:
        try:
            main_phrase = main_phrase.format(value=values[effective_stage])
        except (KeyError, ValueError, IndexError):
            pass

    with st.container(border=True, key=f"pro-card-v4-{index_name}-{effective_stage}-{key_extra}"):
        head_col1, head_col2 = st.columns([6, 1])
        with head_col1:
            st.markdown(
                f"<div style='font-size:1.5rem; font-weight:700; "
                f"color:{neutral}; margin-top:12px; margin-bottom:2px; line-height:1.15; "
                f'display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; '
                f"overflow:hidden; min-height:3.45rem'>{index_name}</div>",
                unsafe_allow_html=True
            )
        with head_col2:
            if notes or main_phrase:
                with st.popover("ⓘ", width='content', key=f'popover_v4_{index_name}_{effective_stage}_{key_extra}'):
                    st.markdown(f"**{index_name}**")
                    if main_phrase:
                        st.markdown(main_phrase)
                    if notes:
                        st.caption(notes)

        polarity = idx_info.get('polarity', 'neutral')

        val_str = format_value(values[effective_stage], unit) + ('≈' if is_borderline(values[effective_stage], thresholds) else '')
        diff = None
        if effective_stage == 'last_90d' and 'recent_6q' in available:
            diff = values['last_90d'] - values['recent_6q']
        elif effective_stage == 'recent_6q' and 'global' in available:
            diff = values['recent_6q'] - values['global']

        delta_html = ''
        if diff is not None:
            d_str = format_value(diff, unit)
            if diff > 1e-9:
                d_str = '+' + d_str

            is_good = is_bad = False
            if mode == 'Professional' and polarity != 'neutral':
                if polarity == 'higher_better':
                    is_good, is_bad = diff > 1e-9, diff < -1e-9
                else:
                    is_good, is_bad = diff < -1e-9, diff > 1e-9

            if is_good:
                delta_color = "#4AA85C"
            elif is_bad:
                delta_color = "#AE2B28"
            else:
                delta_color = neutral

            delta_html = (f"<span style='font-size:1rem; color:{delta_color}; "
                          f"margin-left:10px; font-weight:500'>{d_str}</span>")

        if main_phrase:
            good = bad = False
            if mode == 'Professional' and level and polarity != 'neutral':
                if polarity == 'higher_better':
                    good, bad = level == 'high', level == 'low'
                elif polarity == 'lower_better':
                    good, bad = level == 'low', level == 'high'

            if good:
                phrase_color = dash_config['colors']['high']
            elif bad:
                phrase_color = dash_config['colors']['low']
            else:
                phrase_color = accent

            st.markdown(
                f"<div style='display:flex; flex-wrap:wrap; align-items:flex-start; gap:8px; margin:12px 0 12px 0'>"
                f"<div style='flex:0 0 auto; font-size:2rem; font-weight:700; color:{accent}; line-height:1.05; white-space:nowrap'>{val_str}{delta_html}</div>"
                f"<div style='flex:1 1 140px; font-size:1rem; color:{phrase_color}; font-weight:500; line-height:1.2; text-align:left; "
                f'display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden' f"'>{main_phrase}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div style='font-size:2rem; font-weight:700; color:{accent}; "
                f"margin:12px 0 12px 0; line-height:1.05'>{val_str}{delta_html}</div>",
                unsafe_allow_html=True
            )

        if len(available) < 2:
            st.caption(f"Only available for {STAGE_LABELS[available[0]]}")
            notes = idx_info.get('notes_en', '')
            if notes:
                st.markdown(
                    f"<div style='font-size:1rem; opacity:0.7; "
                    f"color:{neutral}; margin-top:10px; line-height:1.45'>"
                    f"{notes}</div>",
                    unsafe_allow_html=True
                )
            return

        max_from_json = idx_info.get('max_value')
        if max_from_json:
            max_v = max_from_json
        elif unit in ('percent', 'index'):
            max_v = 1.0
        else:
            max_v = max(values[s] for s in available) if max(values[s] for s in available) > 0 else 1

        for s in STAGE_ORDER:
            if s not in available:
                continue
            is_sel = (s == effective_stage)
            v = values[s]
            pct = (v / max_v) * 100 if max_v > 0 else 0
            color = accent if is_sel else 'rgba(128,128,128,0.35)'
            text_color = accent if is_sel else neutral
            weight = '700' if is_sel else '400'
            st.markdown(
                f"<div style='display:flex; align-items:center; margin:5px 0; gap:8px'>"
                f"<div style='width:70px; font-size:0.8rem; color:{text_color}; font-weight:{weight}'>{STAGE_LABELS[s]}</div>"
                f"<div style='flex:1; height:14px; background:rgba(128,128,128,0.12); border-radius:7px; overflow:hidden'>"
                f"<div style='width:{pct:.0f}%; height:100%; background:{color}'></div>"
                f"</div>"
                f"<div style='width:60px; text-align:right; font-size:0.85rem; color:{text_color}; font-weight:{weight}'>"
                f"{format_value(v, unit)}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

def render_personal_card_variant(variant, index_name, kpi_df, selected_stage, theme, cfg,
                                  mode, key_extra='', display_name=None):
    indices_display = cfg['indices_display']
    dash_config = cfg['dashboard']

    rows = kpi_df[kpi_df['index_name'] == index_name].set_index('stage')
    available = [s for s in STAGE_ORDER if s in rows.index]

    if not available:
        with st.container(border=True):
            st.markdown(f"**{display_name or index_name}**")
            st.caption("no data")
        return

    effective_stage = selected_stage if selected_stage in available else available[-1]
    values = {s: rows.loc[s, 'value'] for s in available}
    unit = rows.loc[effective_stage, 'unit']
    neutral = theme['text']
    title = display_name or index_name

    period_accent_map = {
        'global': theme.get('accent_blue', theme['accent_blue']),
        'recent_6q': theme.get('accent_cyan', theme['accent_blue']),
        'last_90d': theme.get('accent_purple', theme['accent_blue']),
    }
    period_accent = period_accent_map.get(effective_stage, theme['accent_blue'])

    idx_info = indices_display.get(index_name, {})

    thresholds = idx_info.get('thresholds')
    if thresholds and len(thresholds) == 2:
        low_t, high_t = thresholds
        v = values[effective_stage]
        if v < low_t:
            level = 'low'
        elif v <= high_t:
            level = 'medium'
        else:
            level = 'high'
    else:
        level = None

    main_phrase = idx_info.get('personal_messages', {}).get(level or 'default', '')
    desc = idx_info.get('description_en', '')

    if main_phrase and '{value' in main_phrase:
        try:
            main_phrase = main_phrase.format(value=values[effective_stage])
        except (KeyError, ValueError, IndexError):
            pass

    diff = None
    if effective_stage == 'last_90d' and 'recent_6q' in available:
        diff = values['last_90d'] - values['recent_6q']
    elif effective_stage == 'recent_6q' and 'global' in available:
        diff = values['recent_6q'] - values['global']

    triangle = ''
    if diff is not None:
        if diff > 1e-9:
            triangle = f"<span style='color:{period_accent}; font-size:1rem'>▲</span>"
        elif diff < -1e-9:
            triangle = f"<span style='color:{period_accent}; font-size:1rem'>▼</span>"
        else:
            triangle = f"<span style='color:{period_accent}; font-size:1rem'>→</span>"

    if index_name == 'Session Depth Index':
        val_str = f"~{int(values[effective_stage] * 60)} min"
    else:
        val_str = format_value(values[effective_stage], unit)

    border_style = f"border:1px solid {period_accent}; border-radius:10px; padding:16px; min-height:180px"

    with st.container(border=False):
        if variant == 'A':
            st.markdown(
                f"<div style='{border_style}'>"
                f"<div style='font-size:0.85rem; color:{neutral}; opacity:0.6; margin-bottom:8px'>{title}</div>"
                f"<div style='font-size:2.8rem; font-weight:700; color:{period_accent}; line-height:1'>{val_str} {triangle}</div>"
                f"<div style='font-size:1rem; color:{neutral}; margin-top:14px; line-height:1.3'>{main_phrase}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        elif variant == 'B':
            st.markdown(
                f"<div style='{border_style}'>"
                f"<div style='font-size:1.05rem; font-weight:500; color:{neutral}; margin-bottom:10px; line-height:1.2'>{title}</div>"
                f"<div style='font-size:1.3rem; color:{period_accent}; font-weight:600; line-height:1.25; margin-bottom:14px; "
                f"min-height:6.5rem; "
                f'display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical; overflow:hidden' f"'>{main_phrase}</div>"
                f"<div style='font-size:1.6rem; font-weight:700; color:{neutral}; opacity:0.85'>{val_str} {triangle}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        elif variant == 'C':
            st.markdown(
                f"<div style='{border_style}'>"
                f"<div style='font-size:1.2rem; font-weight:700; color:{period_accent}; margin-bottom:12px; line-height:1.2'>{title}</div>"
                f"<div style='display:flex; align-items:baseline; gap:14px; margin-bottom:10px'>"
                f"<div style='font-size:2rem; font-weight:700; color:{neutral}; line-height:1'>{val_str}</div>"
                f"<div style='font-size:1rem; color:{period_accent}; font-weight:600'>{triangle}</div>"
                f"</div>"
                f"<div style='font-size:1rem; color:{neutral}; opacity:0.8; line-height:1.3'>{main_phrase}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
        elif variant == 'D':
            st.markdown(
                f"<div style='{border_style}; display:flex; flex-direction:column; justify-content:space-between'>"
                f"<div style='font-size:0.85rem; color:{neutral}; opacity:0.6; margin-bottom:6px'>{title}</div>"
                f"<div style='display:flex; align-items:center; gap:16px; margin:8px 0'>"
                f"<div style='font-size:2.4rem; font-weight:700; color:{period_accent}; line-height:1; white-space:nowrap'>{val_str}</div>"
                f"<div style='font-size:0.95rem; color:{neutral}; line-height:1.3; flex:1'>{main_phrase}</div>"
                f"</div>"
                f"<div style='text-align:right; font-size:0.9rem; color:{period_accent}'>{triangle}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        if desc:
            with st.popover("ⓘ", width='content', key=f'popover_personal_{index_name}_{key_extra}'):
                st.markdown(f"**{title}**")
                st.write(desc)


COMPASS_AXIS_ANGLES = {'Discovery': 90, 'Variability': 0, 'Retention': 270, 'Burnout': 180}


def render_compass(portrait_idx, axes_order, user_levels, profile_color, theme, cfg,
                   height=460, key='compass'):
    dash_config = cfg['dashboard']

    level_colors = dash_config['colors']
    level_radius = dash_config['level_radius']

    r_values = [level_radius[l.lower()] for l in user_levels]
    colors_list = [level_colors[l.lower()] for l in user_levels]

    numeric_theta = [COMPASS_AXIS_ANGLES[a] for a in axes_order]
    circle_theta = np.linspace(0, 360, 200).tolist()
    ring_r = [1.28] * 200

    fig = go.Figure()

    fig.add_trace(go.Barpolar(
        r=[1.10, 1.10, 1.10, 1.10],
        theta=[45, 135, 225, 315],
        width=[90, 90, 90, 90],
        marker_color='#E0E0FF',
        marker_line_width=0,
        hoverinfo='skip',
        showlegend=False
    ))

    fig.add_trace(go.Barpolar(
        r=r_values,
        theta=numeric_theta,
        width=[80] * 4,
        marker_color=colors_list,
        hoverinfo='text',
        text=[f'{a}: {portrait_idx.loc[a, "value"]:.3f} ({l})'
              for a, l in zip(axes_order, user_levels)]
    ))

    fig.add_trace(go.Scatterpolar(
        r=ring_r,
        theta=circle_theta,
        mode='lines',
        line=dict(color=profile_color, width=2),
        hoverinfo='skip',
        showlegend=False
    ))

    fig.update_layout(
        height=height,
        margin=dict(t=30, b=30, l=30, r=30),
        paper_bgcolor=theme['bg'],
        font=dict(color=theme['text']),
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=False, range=[0, 1.40]),
            angularaxis=dict(
                tickvals=numeric_theta,
                ticktext=axes_order,
                showgrid=False,
                showline=False,
                tickfont=dict(color=theme['text'], size=12)
            )
        ),
        showlegend=False
    )

    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False}, key=key)            