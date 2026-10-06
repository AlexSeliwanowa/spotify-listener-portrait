import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from data.loaders import load_parquet, load_kpi_summary, load_portrait
from logic.profile import nearest_profile, PORTRAIT_AXIS_TO_INDEX
from ui.components import (
    render_personal_card_variant,
    render_single_variant_v3_dot,
    render_single_variant_v4_capsules,
    render_compass,
)


def render(mode, selected_stage, cfg):
    theme = cfg['dashboard']['themes'][mode.lower()]
    kpi_summary = load_kpi_summary()

    st.markdown("<div class='ui-title'>Behavior</div>", unsafe_allow_html=True)



    portrait = load_portrait()

    if portrait is None or portrait.empty:
        st.warning('No behavior data available.')
        return

    axes_order = ['Discovery', 'Retention', 'Burnout', 'Variability']

    if selected_stage == 'last_90d':
        portrait_indexed = None
        user_levels = None
        profile = None
        match_distance = None
    else:
        portrait_stage = portrait[portrait['stage'] == selected_stage].copy()
        portrait_indexed = portrait_stage.set_index('axis')
        user_levels = [portrait_indexed.loc[a, 'level'] for a in axes_order]
        profile, match_distance = nearest_profile(user_levels, cfg['profiles']['profiles'])

    if mode == 'Personal':
        _render_personal(portrait_indexed, user_levels, profile,
                         kpi_summary, selected_stage, theme, cfg)
    elif mode == 'Professional':
        _render_professional(portrait_indexed, user_levels,
                             kpi_summary, selected_stage, theme, cfg)


def _render_personal(portrait_indexed, user_levels, profile,
                     kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']

    st.markdown(
        "<div class='ui-subtitle'>"
        "Your listener portrait — who you are as a listener, and how you treat music."
        "</div>",
        unsafe_allow_html=True
    )

    if selected_stage != 'last_90d':
        axes_order = ['Discovery', 'Retention', 'Burnout', 'Variability']

        profile_color_key = dash_config['profile_colors'].get(profile['id'], 'accent_blue') if profile else 'accent_blue'
        profile_color = theme.get(profile_color_key, theme['accent_blue'])

        render_compass(portrait_indexed, axes_order, user_levels, profile_color,
                       theme, cfg, height=460, key='behavior_personal_compass')

        if selected_stage == 'recent_6q':
            st.markdown(
                "<div class='ui-caption' style='margin-top:8px'>"
                "Discovery and Retention are recalculated for the selected window. "
                "Burnout and Variability reflect your overall history."
                "</div>",
                unsafe_allow_html=True
            )

        if profile:
            st.markdown(
                f"<div style='font-size:2rem; font-weight:900; "
                f"color:{profile_color}; margin-top:14px; margin-bottom:8px; "
                f"line-height:1.15'>{profile['name_en']}</div>"
                f"<div style='font-size:1.25rem; color:{profile_color}; "
                f"opacity:0.95; font-style:italic; line-height:1.4'>"
                f"{profile['personal_phrase_en']}</div>",
                unsafe_allow_html=True
            )

        axis_descriptions = {
            'Discovery': 'How actively you seek new music',
            'Retention': 'How often you return to what you found',
            'Burnout': 'How fast you lose interest in favorites',
            'Variability': 'How often your overall profile shifts',
        }
        level_num = {'Low': 1, 'Medium': 2, 'High': 3}

        for axis in axes_order:
            info = portrait_indexed.loc[axis]
            level = info['level']
            filled = level_num.get(level, 0)

            bars_html = ''.join(
                f"<span style='display:inline-block; width:6px; height:{10 + i*5}px; "
                f"background:{profile_color if i < filled else 'rgba(128,128,128,0.25)'}; "
                f"margin-right:3px; border-radius:2px; vertical-align:bottom'></span>"
                for i in range(3)
            )

            st.markdown(
                f"<div style='display:flex; align-items:center; gap:16px; margin-bottom:12px'>"
                f"<div style='width:120px; font-weight:600; color:{theme['text']}; "
                f"font-size:1.05rem'>{axis}</div>"
                f"<div style='width:40px'>{bars_html}</div>"
                f"<div style='opacity:0.75; font-size:0.95rem; color:{theme['text']}'>"
                f"{axis_descriptions.get(axis, '')}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    else:
        st.markdown(
            "<div class='ui-caption' style='margin-bottom:24px'>"
            "Listener profile requires at least 12 months of data. "
            "Switch to Lifetime or Last 18 months to see it."
            "</div>",
            unsafe_allow_html=True
        )

    obs_base = load_parquet(f'behavior/obsessions_base_{selected_stage}.parquet')
    obs_strong = load_parquet('behavior/obsessions_strong.parquet')

    if obs_base is not None and not obs_base.empty and obs_strong is not None and not obs_strong.empty:
        st.markdown("---")
        st.markdown(
            "<div class='ui-section'>Obsessions</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "The tracks you couldn't stop playing."
            "</div>",
            unsafe_allow_html=True
        )

        obs_strong_peak = obs_strong.loc[obs_strong.groupby('track_uri')['repeats'].idxmax()]

        fig_obs = go.Figure()

        fig_obs.add_trace(go.Bar(
            x=obs_base['date'],
            y=obs_base['obsession_share'],
            name='Base obsession',
            marker_color=dash_config['themes']['personal']['accent_blue'],
            opacity=0.85,
            yaxis='y',
            hovertemplate='%{x}: %{y:.1f}%<extra></extra>'
        ))

        fig_obs.add_trace(go.Scatter(
            x=obs_strong_peak['date'],
            y=obs_strong_peak['repeats'],
            mode='markers',
            marker=dict(
                size=obs_strong_peak['hours'].clip(upper=15) * 3 + 8,
                color=dash_config['themes']['personal']['accent_magenta'],
                symbol='diamond',
                opacity=1.0
            ),
            name='Strong obsession',
            customdata=obs_strong_peak[['track_name', 'artist_name', 'repeats', 'hours']],
            hovertemplate='<b>%{customdata[0]}</b><br>Artist: %{customdata[1]}<br>Repeats: %{customdata[2]}<br>Hours: %{customdata[3]:.1f}<extra></extra>',
            yaxis='y2'
        ))

        fig_obs.update_layout(
            height=420,
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor=theme['bg'],
            plot_bgcolor=theme['bg'],
            font=dict(color=theme['text']),
            xaxis=dict(showgrid=False, zeroline=False, title=''),
            yaxis=dict(
                title='Obsession share, %',
                showgrid=False,
                zeroline=False,
                side='left',
                tickfont=dict(color=theme['text'])
            ),
            yaxis2=dict(
                title='Repeats',
                overlaying='y',
                side='right',
                showgrid=False,
                zeroline=False,
                tickfont=dict(color=theme['text'])
            ),
            legend=dict(font=dict(color=theme['text'])),
            hovermode='x unified'
        )

        st.plotly_chart(fig_obs, width='stretch', config={'displayModeBar': False}, key='behavior_personal_obs')

        st.markdown(
            "<div class='ui-caption' style='margin-top:12px'>"
            "Bars show how much of each month was made up of your repeat tracks.\n\n "
            "Diamonds mark intense streaks — moments when a single track played 5+ times in a row."
            "</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Listening habits</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "How you treat the music you press play on."
        "</div>",
        unsafe_allow_html=True
    )
    behavior_cards = [
        ('Skip Risk Index', 'Skipper'),
        ('Repeat Listening Share', 'Repeat'),
        ('Session Depth Index', 'Sessions'),
    ]
    cols = st.columns(3)
    for col, (idx_name, display) in zip(cols, behavior_cards):
        with col:
            render_personal_card_variant(
                'B', idx_name, kpi_summary, selected_stage, theme, cfg, mode='Personal',
                key_extra=f'behavior_{idx_name}',
                display_name=display
            )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )


def _render_professional(portrait_indexed, user_levels,
                         kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    indices_display = cfg['indices_display']
    takeaway = cfg['takeaway']
    professional_theme = dash_config['themes']['professional']

    period_accent_map = {
        'global': professional_theme.get('accent_blue', professional_theme['accent_blue']),
        'recent_6q': professional_theme.get('accent_cyan', professional_theme['accent_blue']),
        'last_90d': professional_theme.get('accent_purple', professional_theme['accent_blue']),
    }
    period_accent = period_accent_map.get(selected_stage, professional_theme['accent_blue'])

    st.markdown(
        "<div class='ui-subtitle'>"
        "Listener behavior metrics — portrait axes, funnels, skip patterns, and cohort retention."
        "</div>",
        unsafe_allow_html=True
    )

    st.caption("Base: valid plays; Skip Risk Index and Funnels — all events.")
    st.markdown("---")

    if selected_stage == 'last_90d':
        st.info(
            "Listener portrait is not available for the Last 90 days window. "
            "Discovery, Retention, Burnout and Variability require at least "
            "12 months of history to be meaningful. Switch to Lifetime or "
            "Last 18 months."
        )
    else:



        takeaways = []
        for axis in ['discovery', 'retention', 'burnout', 'variability']:
            level = portrait_indexed.loc[axis.capitalize(), 'level']
            level_key = level.lower() if level in ['Low', 'Medium', 'High'] else 'low'
            if axis in takeaway['behavior']:
                t = (
                    takeaway['behavior'][axis].get(level.capitalize() + '_en')
                    or takeaway['behavior'][axis].get(level_key)
                )
                if t:
                    takeaways.append(t)

        if takeaways:
            bg_color = 'rgba(0, 0, 0, 0.04)'
            bullets_html = (
                f"<div style='background:{bg_color}; "
                f"border-radius:10px; padding:20px 24px; "
                f"border-left:3px solid {period_accent}'>"
                f"<div class='ui-section' style='margin-top:0'>Product takeaway</div>"
                f"<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
                f"Recommendations generated from the current listener portrait."
                f"</div>"
                f"<ul style='margin:0; padding-left:18px;'>"
            )
            for t in takeaways:
                bullets_html += (
                    f"<li style='font-size:1rem; font-weight:600; "
                    f"line-height:1.5; margin-bottom:10px'>"
                    f"<span style='color:{period_accent}'>{t}</span>"
                    f"</li>"
                )
            bullets_html += "</ul></div>"
            st.markdown(bullets_html, unsafe_allow_html=True)




        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown("---")
        col1, spacer, col2 = st.columns([1, 0.25, 1])



        def axis_level_color(axis, level, fallback_color):
            idx_name = PORTRAIT_AXIS_TO_INDEX.get(axis, axis)
            info = indices_display.get(idx_name, {})
            polarity = info.get('polarity', 'neutral')

            good = bad = False
            if level and polarity == 'higher_better':
                good, bad = level == 'High', level == 'Low'
            elif level and polarity == 'lower_better':
                good, bad = level == 'Low', level == 'High'

            if good:
                return dash_config['colors']['high']
            if bad:
                return dash_config['colors']['low']
            return fallback_color

        level_num = {'Low': 1, 'Medium': 2, 'High': 3}

        with col1:
            st.markdown(
                "<div class='ui-section'>Recalculated per window</div>"
                "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
                "Axes recomputed from the data of the selected period."
                "</div>",
                unsafe_allow_html=True
            )
            for axis in ['Discovery', 'Retention']:
                val = portrait_indexed.loc[axis, 'value']
                level = portrait_indexed.loc[axis, 'level']
                filled = level_num.get(level, 0)

                c1, c2, c3, c4 = st.columns([2.4, 2.2, 2.2, 0.5])
                with c1:
                    st.markdown(
                        f"<div style='font-weight:600; font-size:0.95rem; "
                        f"padding-top:2px'>{axis}</div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    segs = ''
                    for i in range(3):
                        color = period_accent if i < filled else 'rgba(128,128,128,0.2)'
                        segs += (
                            f"<span style='display:inline-block; width:22px; "
                            f"height:8px; background:{color}; margin-right:4px; "
                            f"border-radius:2px; vertical-align:middle'></span>"
                        )
                    st.markdown(f"<div style='padding-top:4px'>{segs}</div>",
                                unsafe_allow_html=True)
                with c3:
                    lvl_color = axis_level_color(axis, level, period_accent)
                    st.markdown(
                        f"<div style='text-align:right; font-size:0.9rem; "
                        f"padding-top:2px'>"
                        f"{val:.2f} · <span style='color:{lvl_color}; "
                        f"font-weight:600'>{level}</span></div>",
                        unsafe_allow_html=True
                    )
                with c4:
                    idx_name = PORTRAIT_AXIS_TO_INDEX.get(axis, axis)
                    info = indices_display.get(idx_name, {})
                    lvl_key = level.lower()
                    prof_msg = info.get('professional_messages', {}).get(lvl_key, '')
                    notes = info.get('notes_en', '')
                    if prof_msg or notes:
                        with st.popover("ⓘ", width='content', key=f'popover_behavior_recalc_{axis}'):
                            st.markdown(f"**{idx_name}**")
                            if prof_msg:
                                st.markdown(prof_msg)
                            if notes:
                                st.caption(notes)

            st.markdown(
                f"<div style='font-size:0.85rem; opacity:0.65; "
                f"margin-top:16px'>"
                f"Discovery and Retention are recalculated for each window. "
                f"</div>",
                unsafe_allow_html=True
            )

        with col2:
            st.markdown(
                "<div class='ui-section'>Not recalculated per window</div>"
                "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
                "Axes computed once on the full history and reused as-is."
                "</div>",
                unsafe_allow_html=True
            )
            for axis in ['Burnout', 'Variability']:
                val = portrait_indexed.loc[axis, 'value']
                level = portrait_indexed.loc[axis, 'level']
                filled = level_num.get(level, 0)

                c1, c2, c3, c4 = st.columns([2.4, 2.2, 2.2, 0.5])
                with c1:
                    st.markdown(
                        f"<div style='font-weight:600; font-size:0.95rem; "
                        f"padding-top:2px'>{axis}</div>",
                        unsafe_allow_html=True
                    )
                with c2:
                    segs = ''
                    for i in range(3):
                        color = period_accent if i < filled else 'rgba(128,128,128,0.2)'
                        segs += (
                            f"<span style='display:inline-block; width:22px; "
                            f"height:8px; background:{color}; margin-right:4px; "
                            f"border-radius:2px; vertical-align:middle'></span>"
                        )
                    st.markdown(f"<div style='padding-top:4px'>{segs}</div>",
                                unsafe_allow_html=True)
                with c3:
                    lvl_color = axis_level_color(axis, level, period_accent)
                    st.markdown(
                        f"<div style='text-align:right; font-size:0.9rem; "
                        f"padding-top:2px'>"
                        f"{val:.2f} · <span style='color:{lvl_color}; "
                        f"font-weight:600'>{level}</span></div>",
                        unsafe_allow_html=True
                    )
                with c4:
                    idx_name = PORTRAIT_AXIS_TO_INDEX.get(axis, axis)
                    info = indices_display.get(idx_name, {})
                    lvl_key = level.lower()
                    prof_msg = info.get('professional_messages', {}).get(lvl_key, '')
                    notes = info.get('notes_en', '')
                    if prof_msg or notes:
                        with st.popover("ⓘ", width='content', key=f'popover_behavior_fixed_{axis}'):
                            st.markdown(f"**{idx_name}**")
                            if prof_msg:
                                st.markdown(prof_msg)
                            if notes:
                                st.caption(notes)

            st.markdown(
                f"<div style='font-size:0.85rem; opacity:0.65; "
                f"margin-top:16px'>"
                f"Burnout and Variability are computed once on the full history "
                f"and reused as-is. Last 90 days does not show the portrait — "
                f"the window is statistically too short."
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Interaction funnel</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "From raw events to saved music — conversion by events and by unique tracks. "
        "The gap between the two shows how much of the volume comes from repeats."
        "</div>",
        unsafe_allow_html=True
    )

    if selected_stage != 'global':
        st.info(
            "Interaction funnel is computed on the full history. "
            "Switch to Lifetime to see it."
        )
    else:
        funnel_events = load_parquet('behavior/behavior_funnel_events.parquet')
        funnel_tracks = load_parquet('behavior/behavior_funnel_tracks.parquet')

        col_funnel_ev, col_funnel_tr = st.columns(2)

        with col_funnel_ev:
            st.markdown(
                "<div class='ui-label' style='margin-bottom:10px'>By events</div>",
                unsafe_allow_html=True
            )
            if funnel_events is not None and not funnel_events.empty:
                fig_funnel_ev = go.Figure(go.Funnel(
                    y=funnel_events['stage'],
                    x=funnel_events['count'],
                    textinfo='value+percent initial'
                ))
                fig_funnel_ev.update_layout(
                    height=380,
                    margin=dict(t=20, b=20, l=20, r=20),
                    paper_bgcolor=theme['bg'],
                    plot_bgcolor=theme['bg'],
                    font=dict(color=theme['text']),
                    xaxis=dict(tickfont=dict(color=theme['text'])),
                    yaxis=dict(tickfont=dict(color=theme['text']))
                )
                st.plotly_chart(fig_funnel_ev, width='stretch',
                                config={'displayModeBar': False},
                                key='behavior_pro_funnel_events')
            else:
                st.info("No event funnel data.")

        with col_funnel_tr:
            st.markdown(
                "<div class='ui-label' style='margin-bottom:10px'>By unique tracks</div>",
                unsafe_allow_html=True
            )
            if funnel_tracks is not None and not funnel_tracks.empty:
                fig_funnel_tr = go.Figure(go.Funnel(
                    y=funnel_tracks['stage'],
                    x=funnel_tracks['count'],
                    textinfo='value+percent initial'
                ))
                fig_funnel_tr.update_layout(
                    height=380,
                    margin=dict(t=20, b=20, l=20, r=20),
                    paper_bgcolor=theme['bg'],
                    plot_bgcolor=theme['bg'],
                    font=dict(color=theme['text']),
                    xaxis=dict(tickfont=dict(color=theme['text'])),
                    yaxis=dict(tickfont=dict(color=theme['text']))
                )
                st.plotly_chart(fig_funnel_tr, width='stretch',
                                config={'displayModeBar': False},
                                key='behavior_pro_funnel_tracks')
            else:
                st.info("No track funnel data.")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Skip behaviour</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Where skips happen — by source and by top-10 genres."
        "</div>",
        unsafe_allow_html=True
    )

    skip_source = load_parquet('behavior/behavior_skip_by_source.parquet')
    skip_genre = load_parquet('behavior/behavior_skip_by_genre.parquet')

    if skip_source is not None and not skip_source.empty:
        skip_source = skip_source[skip_source['stage'] == selected_stage]

    if skip_genre is not None and not skip_genre.empty:
        skip_genre = skip_genre[skip_genre['stage'] == selected_stage]

    col_skip_src, col_skip_gen = st.columns(2)

    with col_skip_src:
        st.markdown(
            "<div class='ui-label' style='margin-bottom:10px'>By source</div>",
            unsafe_allow_html=True
        )
        if skip_source is not None and not skip_source.empty:
            fig_skip_src = go.Figure()

            fig_skip_src.add_trace(go.Bar(
                x=skip_source['source'],
                y=skip_source['skip_rate'],
                marker=dict(
                    color='rgba(0,0,0,0)',
                    line=dict(color=period_accent, width=2)
                ),
                text=[f"{v:.1%}" for v in skip_source['skip_rate']],
                textposition='outside',
                textfont=dict(color=theme['text'], size=11),
                hovertemplate='<b>%{x}</b><br>Skip rate: %{y:.1%}<extra></extra>'
            ))

            fig_skip_src.update_layout(
                height=340,
                margin=dict(t=20, b=40, l=20, r=20),
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(tickfont=dict(color=theme['text'])),
                yaxis=dict(title='Skip rate', showgrid=False,
                           tickfont=dict(color=theme['text'])),
                showlegend=False
            )
            st.plotly_chart(fig_skip_src, width='stretch',
                            config={'displayModeBar': False},
                            key='behavior_pro_skip_by_source')
        else:
            st.info("No source skip data.")

    with col_skip_gen:
        st.markdown(
            "<div class='ui-label' style='margin-bottom:10px'>By genre (top 10)</div>",
            unsafe_allow_html=True
        )
        if skip_genre is not None and not skip_genre.empty:
            top10_skip = skip_genre.nlargest(10, 'total').sort_values('skip_rate', ascending=False)

            fig_skip_gen = go.Figure(go.Bar(
                x=top10_skip['skip_rate'],
                y=top10_skip['genre'],
                orientation='h',
                marker=dict(
                    color='rgba(0,0,0,0)',
                    line=dict(color=period_accent, width=2)
                ),
                text=[f"{v:.1%}" for v in top10_skip['skip_rate']],
                textposition='outside',
                textfont=dict(color=theme['text'], size=11),
                hovertemplate='<b>%{y}</b><br>Skip rate: %{x:.1%}<extra></extra>'
            ))

            fig_skip_gen.update_layout(
                height=340,
                margin=dict(t=20, b=40, l=140, r=20),
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(title='Skip rate', showgrid=False,
                           tickfont=dict(color=theme['text']),
                           title_font=dict(color=theme['text']),
                           range=[0, top10_skip['skip_rate'].max() * 1.2]),
                yaxis=dict(title='', showgrid=False,
                           tickfont=dict(color=theme['text']),
                           autorange='reversed')
            )
            st.plotly_chart(fig_skip_gen, width='stretch',
                            config={'displayModeBar': False},
                            key='behavior_pro_skip_by_genre')
        else:
            st.info("No genre skip data.")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Full play behaviour</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Where tracks get fully played — by source and by top-10 genres."
        "</div>",
        unsafe_allow_html=True
    )

    col_fp_src, col_fp_gen = st.columns(2)

    with col_fp_src:
        st.markdown(
            "<div class='ui-label' style='margin-bottom:10px'>By source</div>",
            unsafe_allow_html=True
        )
        if skip_source is not None and not skip_source.empty:
            fig_fp_src = go.Figure()

            fig_fp_src.add_trace(go.Bar(
                x=skip_source['source'],
                y=skip_source['full_play_rate'],
                marker_color=period_accent,
                text=[f"{v:.1%}" for v in skip_source['full_play_rate']],
                textposition='outside',
                textfont=dict(color=theme['text'], size=11),
                hovertemplate='<b>%{x}</b><br>Full play rate: %{y:.1%}<extra></extra>'
            ))

            fig_fp_src.update_layout(
                height=340,
                margin=dict(t=20, b=40, l=20, r=20),
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(tickfont=dict(color=theme['text'])),
                yaxis=dict(title='Full play rate', showgrid=False,
                           tickfont=dict(color=theme['text'])),
                showlegend=False
            )
            st.plotly_chart(fig_fp_src, width='stretch',
                            config={'displayModeBar': False},
                            key='behavior_pro_fp_by_source')
        else:
            st.info("No source data.")

    with col_fp_gen:
        st.markdown(
            "<div class='ui-label' style='margin-bottom:10px'>By genre (top 10)</div>",
            unsafe_allow_html=True
        )
        if skip_genre is not None and not skip_genre.empty:
            top10_fp = skip_genre.nlargest(10, 'total').sort_values('full_play_rate', ascending=False)
            fig_fp_gen = go.Figure(go.Bar(
                x=top10_fp['full_play_rate'],
                y=top10_fp['genre'],
                orientation='h',
                marker_color=period_accent,
                text=[f"{v:.1%}" for v in top10_fp['full_play_rate']],
                textposition='outside',
                textfont=dict(color=theme['text'], size=11),
                hovertemplate='<b>%{y}</b><br>Full play rate: %{x:.1%}<extra></extra>'
            ))
            fig_fp_gen.update_layout(
                height=340,
                margin=dict(t=20, b=40, l=140, r=20),
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(title='Full play rate', showgrid=False,
                           tickfont=dict(color=theme['text']),
                           title_font=dict(color=theme['text']),
                           range=[0, top10_fp['full_play_rate'].max() * 1.2]),
                yaxis=dict(title='', showgrid=False,
                           tickfont=dict(color=theme['text']),
                           autorange='reversed')
            )
            st.plotly_chart(fig_fp_gen, width='stretch',
                            config={'displayModeBar': False},
                            key='behavior_pro_fp_by_genre')
        else:
            st.info("No genre data.")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Cohort retention</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Share of tracks from each cohort year that were played again within 30 / 90 / 180 days after their first play."
        "</div>",
        unsafe_allow_html=True
    )

    if selected_stage != 'global':
        st.info(
            "Cohort retention is computed on the full history. "
            "Switch to Lifetime to see it."
        )
    else:
        cohorts = load_parquet('behavior/behavior_cohorts.parquet')
        if cohorts is not None and not cohorts.empty:
            fig_cohorts = go.Figure(data=go.Heatmap(
                z=cohorts[['retention_30d', 'retention_90d', 'retention_180d']].values,
                x=['30d', '90d', '180d'],
                y=cohorts['cohort'],
                colorscale=[
                    [0.0, '#F5F5F5'],
                    [0.25, '#B3D9F5'],
                    [0.5, '#66B2EA'],
                    [0.75, '#2E7BC4'],
                    [1.0, '#0D47A1'],
                ],
                colorbar=dict(
                    title=dict(text='Retention %', font=dict(color=theme['text'])),
                    tickfont=dict(color=theme['text'])
                ),
                hovertemplate=(
                    "<b>Cohort %{y}</b><br>"
                    "Horizon: %{x}<br>"
                    "Retention: %{z:.1f}%<extra></extra>"
                ),
                text=[[f"{v:.0f}%" if pd.notna(v) else "—"
                    for v in row]
                    for row in cohorts[['retention_30d', 'retention_90d', 'retention_180d']].values],
                texttemplate="%{text}",
                textfont=dict(color=theme['text'], size=12),
            ))
            fig_cohorts.update_layout(
                height=400,
                margin=dict(t=20, b=20, l=20, r=20),
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(tickfont=dict(color=theme['text'])),
                yaxis=dict(tickfont=dict(color=theme['text']))
            )
            st.plotly_chart(fig_cohorts, width='stretch',
                            config={'displayModeBar': False},
                            key='behavior_pro_cohorts')
        else:
            st.info("No cohort data.")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Behavioral indices</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Eight indices across four areas — skip, session, depth, repetition. "
        "Per-index trends across three windows."
        "</div>",
        unsafe_allow_html=True
    )

    BEHAVIOR_INDICES = [
        'Skip Risk Index',
        'Contextual Skip Ratio',
        'Session Depth Index',
        'Interrupted Session Share',
        'Mean Played Fraction',
        'Completion Rate',
        'Repeat Listening Share',
        'External Exposure Index',
    ]

    for start in [0, 3, 6]:
        cols = st.columns(3)
        for col, idx_name in zip(cols, BEHAVIOR_INDICES[start:start+3]):
            with col:
                render_single_variant_v4_capsules(
                    idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                    key_extra=f'behavior_idx_{idx_name}'
                )
    st.caption("≈ — value close to category boundary")

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )