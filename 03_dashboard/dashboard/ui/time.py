import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from data.loaders import load_parquet, load_kpi_summary
from ui.components import render_personal_card_variant, render_single_variant_v3_dot


def render(mode, selected_stage, cfg):
    theme = cfg['dashboard']['themes'][mode.lower()]
    kpi_summary = load_kpi_summary()

    st.markdown("<div class='ui-title'>Time</div>", unsafe_allow_html=True)

    time_global = load_parquet('time/time_series_global.parquet')
    time_changepoints = load_parquet('time/time_changepoints.parquet')
    time_storms = load_parquet('time/time_storms.parquet')
    time_meta = load_parquet('time/time_series_meta.parquet')

    if time_global is None or time_global.empty:
        st.warning('No time data available.')
        return

    def normalize(series):
        mn, mx = series.min(), series.max()
        if mx - mn == 0:
            return pd.Series(0.5, index=series.index)
        return (series - mn) / (mx - mn)

    all_metrics = [
        'valence_mean', 'energy_mean', 'instrumentalness_mean',
        'hours', 'tracks', 'discovery_rate', 'completion_rate',
        'skip_rate', 'desktop_share'
    ]
    for metric in all_metrics:
        time_global[f'{metric}_norm'] = normalize(time_global[metric])

    if mode == 'Personal':
        _render_personal(time_global, time_changepoints, time_storms, time_meta,
                         kpi_summary, selected_stage, theme, cfg)
    elif mode == 'Professional':
        _render_professional(time_global, time_changepoints, time_storms, time_meta,
                             kpi_summary, selected_stage, theme, cfg)


def _render_personal(time_global, time_changepoints, time_storms, time_meta,
                     kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']

    st.markdown(
        "<div class='ui-subtitle'>"
        "Your listening rhythm — how it changed over time, and where you are now."
        "</div>",
        unsafe_allow_html=True
    )

    theme_colors = dash_config['themes']['personal']
    period_accent = {
        'global': theme_colors['accent_blue'],
        'recent_6q': theme_colors['accent_cyan'],
        'last_90d': theme_colors['accent_purple'],
    }.get(selected_stage, theme_colors['accent_blue'])

    metric_colors = {
        'valence_mean': theme_colors['accent_pink'],
        'energy_mean': theme_colors['accent_blue'],
        'instrumentalness_mean': theme_colors['accent_green'],
        'hours': theme_colors['accent_purple'],
        'tracks': theme_colors['accent_orange'],
        'discovery_rate': theme_colors['accent_yellow'],
        'completion_rate': theme_colors['accent_cyan'],
        'skip_rate': theme_colors['accent_red'],
        'desktop_share': theme_colors['accent_lime']
    }
    metric_labels = {
        'valence_mean': 'Valence',
        'energy_mean': 'Energy',
        'instrumentalness_mean': 'Instrumentalness',
        'hours': 'Hours',
        'tracks': 'Tracks',
        'discovery_rate': 'Discovery',
        'completion_rate': 'Completion',
        'skip_rate': 'Skip',
        'desktop_share': 'Desktop'
    }

    fig = go.Figure()

    default_visible = ['valence_mean', 'energy_mean', 'instrumentalness_mean']

    for metric, color in metric_colors.items():
        fig.add_trace(go.Scatter(
            x=time_global['date'],
            y=time_global[f'{metric}_norm'],
            mode='lines',
            name=metric_labels[metric],
            line=dict(color=color, width=2),
            customdata=time_global[[metric]],
            hovertemplate=f'{metric_labels[metric]}: %{{customdata[0]:.2f}}<extra></extra>',
            visible=True if metric in default_visible else 'legendonly'
        ))

    # ---------- АВТОДЕТЕКТ ПИКА И ПРОВАЛА ----------
    MIN_TRACKS_FOR_DETECTION = 20
    reliable = time_global[time_global['tracks'] >= MIN_TRACKS_FOR_DETECTION]

    sound_norm_cols = ['valence_mean_norm', 'energy_mean_norm', 'instrumentalness_mean_norm']
    mood_combo = reliable[sound_norm_cols].mean(axis=1)
    idx_min = mood_combo.idxmin()
    idx_max = mood_combo.idxmax()

    y_min = reliable.loc[idx_min, sound_norm_cols].min()
    y_max = reliable.loc[idx_max, sound_norm_cols].max()

    for idx, y_val, label, arrow_color, ay in [
        (idx_min, y_min, 'Sound low',  theme_colors['accent_pink'],   80),
        (idx_max, y_max, 'Sound peak', theme_colors['accent_green'], -80),
    ]:
        fig.add_annotation(
            x=time_global.loc[idx, 'date'],
            y=y_val,
            text=f"{label}<br>{time_global.loc[idx, 'date'].strftime('%b %Y')}",
            showarrow=True, arrowhead=2, arrowcolor=arrow_color,
            font=dict(color=arrow_color, size=12),
            ax=0, ay=ay
        )

    # ---------- LEGEND-ONLY ----------
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
        line=dict(color='rgba(128,128,128,0.6)', width=10),
        name='Cold start (no data)', hoverinfo='skip', showlegend=True,
        legend='legend2'))

    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
        line=dict(color='rgba(255,140,0,0.6)', width=10),
        name='Storm episodes', hoverinfo='skip', showlegend=True,
        legend='legend2'))

    layer_colors = {
        'sound': theme_colors['accent_blue'],
        'behavior': theme_colors['accent_pink'],
        'identity': theme_colors['accent_green'],
    }
    layer_labels = {
        'sound': 'Shift: sound',
        'behavior': 'Shift: behavior',
        'identity': 'Shift: identity',
    }
    for layer in ['sound', 'behavior', 'identity']:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color=layer_colors[layer], width=2, dash='dot'),
            name=layer_labels[layer], hoverinfo='skip', showlegend=True,
            legend='legend2', legendgroup=layer))

    # ---------- СЕРАЯ ЗОНА ХОЛОДНОГО СТАРТА ----------
    if time_meta is not None and not time_meta.empty:
        meta_row = time_meta.iloc[0]
        fpg = pd.to_datetime(meta_row['first_post_gap_month'] + '-01')
        fig.add_vrect(
            x0=time_global['date'].min(), x1=fpg,
            fillcolor='rgba(128,128,128,0.15)', line_width=0,
            layer='below'
        )

    # ---------- ЗАЛИВКА ШТОРМОВ ----------
    if time_storms is not None and not time_storms.empty:
        storms = time_storms[time_storms['is_storm']]
        for ep_id in storms['episode_id'].dropna().unique():
            ep = storms[storms['episode_id'] == ep_id]
            fig.add_vrect(
                x0=ep['date'].min(), x1=ep['date'].max(),
                fillcolor='rgba(255,140,0,0.10)', line_width=0,
                layer='below'
            )

    # ---------- 3 СЛОЯ ПУНКТИРОВ ----------
    if time_changepoints is not None and not time_changepoints.empty:
        for _, cp in time_changepoints.iterrows():
            x = pd.to_datetime(cp['date'] + '-01')
            fig.add_trace(go.Scatter(
                x=[x, x], y=[-0.25, 1.35],
                mode='lines',
                line=dict(
                    color=layer_colors.get(cp['layer'], theme_colors['text']),
                    width=2, dash='dot'
                ),
                opacity=0.3 + 0.6 * float(cp['confidence']),
                legendgroup=cp['layer'],
                showlegend=False,
                hovertemplate=(
                    f"<b>{layer_labels.get(cp['layer'], cp['layer'])}</b><br>"
                    f"{cp['method']}<br>{cp['date']}<br>"
                    f"confidence: {cp['confidence']:.2f}<extra></extra>"
                )
            ))

    # ---------- ПОДСВЕТКА ВЫБРАННОГО ПЕРИОДА ----------
    if selected_stage != 'global':
        period_df = load_parquet(f'time/time_series_{selected_stage}.parquet')
        if period_df is not None and not period_df.empty:
            period_start = period_df['date'].min()
            period_end = min(period_df['date'].max(), time_global['date'].max())
            period_highlight_color = {
                'recent_6q': theme_colors['accent_cyan'],
                'last_90d': theme_colors['accent_purple'],
            }.get(selected_stage, theme_colors['accent_blue'])
            fig.add_vrect(
                x0=period_start, x1=period_end,
                fillcolor=period_highlight_color, opacity=0.08,
                line_width=0, layer='below'
            )

    fig.update_layout(
        height=560,
        margin=dict(t=40, b=160, l=30, r=20),
        paper_bgcolor=theme['bg'],
        plot_bgcolor=theme['bg'],
        font=dict(color=theme['text']),
        showlegend=True,
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.01,
            font=dict(color=theme['text'], size=11)
        ),
        legend2=dict(
            orientation='h',
            yanchor='top',
            y=-0.35,
            xanchor='center',
            x=0.5,
            font=dict(color=theme['text'], size=11),
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(color=theme['text']),
            title=''
        ),
        yaxis=dict(
            showgrid=False, zeroline=False,
            showticklabels=False, title='',
            range=[-0.25, 1.35]
        ),
        hovermode='x unified'
    )

    st.plotly_chart(fig, width='stretch', config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
        'displaylogo': False
    }, key='time_personal_main')

    metric_descriptions = {
        'Valence': 'How positive or sad the music sounds. High = brighter, low = more melancholic.',
        'Energy': 'How intense and active the music is. High = loud, driving; low = calm.',
        'Instrumentalness': 'Whether tracks have vocals. High = instrumental; low = vocal-driven.',
        'Hours': 'Total time you spent listening in each period.',
        'Tracks': 'How many tracks you played. Reflects listening volume.',
        'Discovery': 'Share of tracks you heard for the first time. High = lots of new music.',
        'Completion': 'How often you listen to tracks all the way through.',
        'Skip': 'How often you skip. Higher = more tracks rejected early.',
        'Desktop': 'Share of listening on desktop (Windows/Linux) vs mobile.',
    }

    with st.expander('What do these metrics mean?'):
        for label, desc in metric_descriptions.items():
            st.markdown(
                f"<div style='margin-bottom:8px'>"
                f"<span style='color:{period_accent}; font-weight:600'>{label}</span>"
                f"<span style='opacity:0.85'> — {desc}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

   
    with st.expander('Chart annotations — definitions'):
        time_defs = cfg['time_defs']
        for key in ['cold_start', 'storm_episodes', 'shift_sound', 'shift_behavior', 'shift_identity']:
            info = time_defs.get(key, {})
            text = info.get('personal_en', '')
            if not text:
                continue
            label = key.replace('_', ' ').title()
            st.markdown(
                f"<div style='margin-bottom:10px'>"
                f"<span style='color:{period_accent}; font-weight:600'>{label}</span>"                f"<span style='opacity:0.85'> — {text}</span>"
                f"</div>",
                unsafe_allow_html=True
            )        

    st.caption(
        "Click any metric in the legend to show or hide it — only three are on by default.\n\n"
        "Vertical marks show where your listening profile shifted significantly.\n\n"
        "Incomplete periods (months/weeks) excluded to avoid false drops."
    )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Your daily rhythm</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Three quick signals about how and when you listen."
        "</div>",
        unsafe_allow_html=True
    )
    time_cards = [
        ('Music Day Share', 'Regularity'),
        ('Music Recency Index', 'Freshness'),
        ('Night Listening Share', 'Night Owl'),
    ]
    cols = st.columns(3)
    for col, (idx_name, display) in zip(cols, time_cards):
        with col:
            render_personal_card_variant(
                'B', idx_name, kpi_summary, selected_stage, theme, cfg, mode='Personal',
                key_extra=f'time_{idx_name}',
                display_name=display
            )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )


def _render_professional(time_global, time_changepoints, time_storms, time_meta,
                         kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    indices_display = cfg['indices_display']
    professional_theme = dash_config['themes']['professional']
    period_accent = {
        'global': professional_theme['accent_blue'],
        'recent_6q': professional_theme['accent_cyan'],
        'last_90d': professional_theme['accent_purple'],
    }.get(selected_stage, professional_theme['accent_blue'])
    interactive_accent = period_accent

    st.markdown(
        "<div class='ui-subtitle'>"
        "Temporal dynamics of listening: discovery rate, skip behaviour, and platform shift over the selected window."
        "</div>",
        unsafe_allow_html=True
    )

    st.caption("Base: valid plays; `skip_rate` — all events.")

    if time_meta is not None and not time_meta.empty:
        meta_row = time_meta.iloc[0]
        if bool(meta_row['has_mid_history_gaps']):
            st.warning(
                f"History has gaps in the middle: {meta_row['mid_gaps']}. "
                f"Detectors and Variability may be less stable around these periods."
            )

    st.markdown(
        "<div class='ui-section'>Temporal dynamics</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:12px'>"
        "Four time series over the selected window: Discovery Rate (share of first-heard tracks), "
        "Skip Rate (share of skipped events), Platform Desktop Share, Completion Rate (share of tracks "
        "played to ≥90% of duration). "
        "</div>",
        unsafe_allow_html=True
    )

    pro_metric_colors = {
        'discovery_rate': professional_theme['accent_blue'],
        'skip_rate': professional_theme['accent_pink'],
        'desktop_share': professional_theme['accent_green'],
        'completion_rate': professional_theme['accent_orange'],
    }
    pro_metric_labels = {
        'discovery_rate': 'Discovery Rate',
        'skip_rate': 'Skip Rate',
        'desktop_share': 'Platform (Desktop Share)',
        'completion_rate': 'Completion Rate',
    }

    fig_pro = go.Figure()
    for metric, color in pro_metric_colors.items():
        fig_pro.add_trace(go.Scatter(
            x=time_global['date'],
            y=time_global[f'{metric}_norm'],
            mode='lines',
            name=pro_metric_labels[metric],
            line=dict(color=color, width=2),
            opacity=0.7,
            customdata=time_global[[metric]],
            hovertemplate=f'{pro_metric_labels[metric]}: %{{customdata[0]:.2f}}<extra></extra>',
        ))

    # ---------- LEGEND-ONLY ----------
    fig_pro.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
        line=dict(color='rgba(128,128,128,0.6)', width=10),
        name='Cold start (no data)', hoverinfo='skip', showlegend=True,
        legend='legend2'))

    fig_pro.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
        line=dict(color='rgba(255,140,0,0.6)', width=10),
        name='Storm episodes', hoverinfo='skip', showlegend=True,
        legend='legend2'))

    layer_colors = {
        'sound': professional_theme['accent_purple'],
        'behavior': professional_theme['accent_magenta'],
        'identity': professional_theme['accent_teal'],
    }
    layer_labels = {
        'sound': 'Shift: sound',
        'behavior': 'Shift: behavior',
        'identity': 'Shift: identity',
    }
    for layer in ['sound', 'behavior', 'identity']:
        fig_pro.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
            line=dict(color=layer_colors[layer], width=2, dash='dot'),
            name=layer_labels[layer], hoverinfo='skip', showlegend=True,
            legend='legend2', legendgroup=layer))

    # ---------- СЕРАЯ ЗОНА ----------
    if time_meta is not None and not time_meta.empty:
        meta_row = time_meta.iloc[0]
        fpg = pd.to_datetime(meta_row['first_post_gap_month'] + '-01')
        fig_pro.add_vrect(
            x0=time_global['date'].min(), x1=fpg,
            fillcolor='rgba(128,128,128,0.15)', line_width=0,
            layer='below'
        )

    # ---------- ШТОРМЫ ----------
    if time_storms is not None and not time_storms.empty:
        storms = time_storms[time_storms['is_storm']]
        for ep_id in storms['episode_id'].dropna().unique():
            ep = storms[storms['episode_id'] == ep_id]
            fig_pro.add_vrect(
                x0=ep['date'].min(), x1=ep['date'].max(),
                fillcolor='rgba(255,140,0,0.10)', line_width=0,
                layer='below'
            )

    # ---------- ПУНКТИРЫ ----------
    if time_changepoints is not None and not time_changepoints.empty:
        layer_offset = {'sound': -8, 'behavior': 0, 'identity': 8}
        for _, cp in time_changepoints.iterrows():
            x = pd.to_datetime(cp['date'] + '-01') + pd.Timedelta(days=layer_offset.get(cp['layer'], 0))
            fig_pro.add_trace(go.Scatter(
                x=[x, x], y=[-0.05, 1.05],
                mode='lines',
                line=dict(
                    color=layer_colors.get(cp['layer'], professional_theme['text']),
                    width=2, dash='dot'
                ),
                opacity=0.6 + 0.4 * float(cp['confidence']),
                legendgroup=cp['layer'],
                showlegend=False,
                hovertemplate=(
                    f"<b>{layer_labels.get(cp['layer'], cp['layer'])}</b><br>"
                    f"{cp['method']}<br>{cp['date']}<br>"
                    f"confidence: {cp['confidence']:.2f}<extra></extra>"
                )
            ))

    # ---------- ПОДСВЕТКА ПЕРИОДА ----------
    if selected_stage != 'global':
        period_df = load_parquet(f'time/time_series_{selected_stage}.parquet')
        if period_df is not None and not period_df.empty:
            period_start = period_df['date'].min()
            period_end = min(period_df['date'].max(), time_global['date'].max())
            period_highlight_color = {
                'recent_6q': professional_theme['accent_cyan'],
                'last_90d': professional_theme['accent_purple'],
            }.get(selected_stage, professional_theme['accent_blue'])
            fig_pro.add_vrect(
                x0=period_start, x1=period_end,
                fillcolor=period_highlight_color, opacity=0.08,
                line_width=0, layer='below'
            )

    fig_pro.update_layout(
        height=560,
        margin=dict(t=40, b=170, l=30, r=20),
        paper_bgcolor=theme['bg'],
        plot_bgcolor=theme['bg'],
        font=dict(color=theme['text']),
        showlegend=True,
        legend=dict(
            orientation='v',
            yanchor='top',
            y=0.98,
            xanchor='left',
            x=1.01,
            font=dict(color=theme['text'], size=11)
        ),
        legend2=dict(
            orientation='h',
            yanchor='top',
            y=-0.20,
            xanchor='center',
            x=0.5,
            font=dict(color=theme['text'], size=11),
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(
            showgrid=False, zeroline=False,
            tickfont=dict(color=theme['text']), title=''
        ),
        yaxis=dict(
            title=dict(text='Normalized value', font=dict(color=theme['text'])),
            tickfont=dict(color=theme['text']),
            gridcolor='rgba(128,128,128,0.15)',
            range=[-0.05, 1.05]
        ),
        hovermode='x unified'
    )

    st.plotly_chart(fig_pro, width='stretch', config={'displayModeBar': False}, key='time_pro_main')

    if time_changepoints is not None and not time_changepoints.empty:
        st.markdown(
            "<div class='ui-section' style='margin-top:28px'>Changepoints</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "All detected points where your listening profile shifted."
            "</div>",
            unsafe_allow_html=True
        )
        cp_table = time_changepoints.sort_values('date').reset_index(drop=True)

        html = (
            f'<table style="width:100%; border-collapse:collapse; font-size:0.9rem; '
            f'background:{professional_theme["bg"]}; color:{professional_theme["text"]}">'
            '<thead><tr>'
        )
        for h in ['date', 'method', 'layer', 'confidence']:
            html += (
                f'<th style="text-align:left; padding:10px 14px; '
                f'border-bottom:1px solid rgba(128,128,128,0.3); font-weight:600; '
                f'color:{professional_theme["text"]}">{h}</th>'
            )
        html += '</tr></thead><tbody>'

        for _, row in cp_table.iterrows():
            layer_color = layer_colors.get(row['layer'], professional_theme['text'])
            html += '<tr>'
            html += (
                f'<td style="padding:8px 14px; '
                f'border-bottom:1px solid rgba(128,128,128,0.15)">{row["date"]}</td>'
            )
            html += (
                f'<td style="padding:8px 14px; '
                f'border-bottom:1px solid rgba(128,128,128,0.15)">{row["method"]}</td>'
            )
            html += (
                f'<td style="padding:8px 14px; '
                f'border-bottom:1px solid rgba(128,128,128,0.15); '
                f'color:{layer_color}; font-weight:600">{row["layer"]}</td>'
            )
            html += (
                f'<td style="padding:8px 14px; text-align:right; '
                f'border-bottom:1px solid rgba(128,128,128,0.15)">'
                f'{row["confidence"]:.3f}</td>'
            )
            html += '</tr>'

        html += '</tbody></table>'
        st.markdown(html, unsafe_allow_html=True)

    st.caption(
        "Incomplete months and weeks are excluded to avoid false drops at the end of the window."
    )

    with st.expander('Chart annotations — definitions'):
        time_defs = cfg['time_defs']
        for key in ['cold_start', 'storm_episodes', 'shift_sound', 'shift_behavior', 'shift_identity']:
            info = time_defs.get(key, {})
            text = info.get('professional_en', '')
            if not text:
                continue
            label = key.replace('_', ' ').title()
            st.markdown(
                f"<div style='margin-bottom:10px'>"
                f"<span style='color:{interactive_accent}; font-weight:600'>{label}</span>"
                f"<span style='opacity:0.85'> — {text}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
    with st.expander('Chart metrics — definitions'):
        chart_defs = [
            ('Discovery Rate',
             'Share of tracks heard for the first time within the period.',
             'first-heard tracks / total tracks per period'),
            ('Skip Rate',
             'Share of all events classified as skips.',
             'skip events / all events'),
            ('Platform Desktop Share',
             'Share of valid plays on desktop platforms.',
             'desktop plays / valid plays'),
            ('Completion Rate',
             'Share of valid plays reaching ≥90% of track duration.',
             'plays with played_frac ≥ 0.90 / valid plays'),
        ]

        for name, what, formula in chart_defs:
            st.markdown(
                f"<div style='margin-bottom:14px'>"
                f"<div style='font-weight:600; color:{interactive_accent}; "
                f"font-size:1rem'>{name}</div>"
                f"<div style='font-size:0.9rem; color:{theme['text']}; "
                f"opacity:0.85; margin-top:2px'>{what}</div>"
                f"<div style='font-size:0.85rem; color:{theme['text']}; "
                f"opacity:0.7; margin-top:4px; font-family:monospace'>"
                f"Formula: {formula}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.markdown(
            f"<div style='font-size:0.85rem; color:{theme['text']}; "
            f"opacity:0.6; margin-top:8px'>Chart curves are min–max normalized "
            f"for visual comparison.</div>",
            unsafe_allow_html=True
        )


    # ===== Variability panel =====
    vmeta = load_parquet('time/variability_meta.parquet')

    if vmeta is not None and not vmeta.empty and bool(vmeta.iloc[0]['short_history']):
        st.markdown("---")
        st.markdown(
            "<div class='ui-section'>Variability</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "How often your sound profile shifts over time."
            "</div>",
            unsafe_allow_html=True
        )
        st.info("Not enough history for Variability — need ≥ 24 months of data.")
    else:
        variability = load_parquet('time/variability.parquet')
        feat_contrib = load_parquet('time/feature_contributions.parquet')
        epochs = load_parquet('time/epochs_sound.parquet')

        if variability is not None and not variability.empty and vmeta is not None and not vmeta.empty:
            meta_row = vmeta.iloc[0]
            lifetime_score = meta_row['lifetime_score']
            current_score = meta_row['current_score']
            null_low = meta_row['null_low']
            null_high = meta_row['null_high']
            n_transitions = int(meta_row['n_transitions'])
            n_valid = int(meta_row['n_valid_rolling_points'])

            st.markdown("---")
            st.markdown(
                "<div class='ui-section'>Variability</div>"
                "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
                "How often the sound profile shifts, measured as the share of High-shift "
                "months in a rolling 12-month window."
                "</div>",
                unsafe_allow_html=True
            )

            st.markdown(
                f"<div style='font-size:1.05rem; color:{professional_theme['text']}; margin-bottom:16px'>"
                f"Lifetime: <b>{lifetime_score:.3f}</b> · "
                f"Current: <b>{current_score:.3f}</b> · "
                f"Full windows: <b>{n_valid} of {n_transitions}</b>"
                f"</div>",
                unsafe_allow_html=True
            )

            var = variability.dropna(subset=['score']).copy()
            var['date'] = pd.to_datetime(var['period'] + '-01')

            fig_var = go.Figure()

            fig_var.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                line=dict(color='rgba(128,128,128,0.5)', width=10),
                name='Null range', hoverinfo='skip', showlegend=True))

            fig_var.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                line=dict(color='rgba(244,81,30,0.5)', width=10),
                name='High-variability epochs', hoverinfo='skip', showlegend=True))

            fig_var.add_hrect(
                y0=null_low, y1=null_high,
                fillcolor='rgba(128,128,128,0.12)',
                line_width=0, layer='below'
            )

            if epochs is not None and not epochs.empty:
                for _, ep in epochs.iterrows():
                    ep_start = pd.to_datetime(ep['start'] + '-01')
                    ep_end = pd.to_datetime(ep['end'] + '-01')
                    fig_var.add_vrect(
                        x0=ep_start, x1=ep_end,
                        fillcolor=professional_theme['accent_orange'],
                        opacity=0.10, line_width=0, layer='below'
                    )

            fig_var.add_trace(go.Scatter(
                x=var['date'], y=var['score'],
                mode='lines+markers',
                line=dict(color=professional_theme['accent_blue'], width=2),
                marker=dict(size=6, color=professional_theme['accent_blue']),
                name='Variability score',
                hovertemplate='%{x|%b %Y}<br>Score: %{y:.3f}<extra></extra>',
            ))

            fig_var.add_hline(
                y=lifetime_score,
                line=dict(color=professional_theme['text'], width=1, dash='dash'),
                opacity=0.5,
                annotation_text=f'Lifetime {lifetime_score:.3f}',
                annotation_position='right',
                annotation_font=dict(color=professional_theme['text'], size=11),
            )

            last = var.iloc[-1]
            fig_var.add_trace(go.Scatter(
                x=[last['date']], y=[last['score']],
                mode='markers',
                marker=dict(size=14, color=professional_theme['accent_pink'],
                            line=dict(color=professional_theme['text'], width=2)),
                name='Current',
                hovertemplate='Current: %{y:.3f}<extra></extra>',
            ))

            fig_var.update_layout(
                height=360,
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(
                    type='date',
                    showgrid=False, zeroline=False,
                    tickfont=dict(color=theme['text']), title='',
                    range=[var['date'].min(), var['date'].max()],
                ),
                yaxis=dict(
                    title=dict(text='Score', font=dict(color=theme['text'])),
                    tickfont=dict(color=theme['text']),
                    gridcolor='rgba(128,128,128,0.15)',
                    range=[0, 1.0],
                ),
                showlegend=True,
                legend=dict(
                    orientation='h',
                    yanchor='top', y=-0.18,
                    xanchor='center', x=0.5,
                    font=dict(color=theme['text'], size=11),
                    bgcolor='rgba(0,0,0,0)',
                ),
                margin=dict(t=30, b=80, l=40, r=80),
                hovermode='x unified',
            )

            st.plotly_chart(fig_var, width='stretch',
                            config={'displayModeBar': False},
                            key='time_pro_variability')

            st.caption(
                f"First 12 months excluded — rolling window not complete. "
                f"Grey band: null range ({null_low:.3f}–{null_high:.3f}). "
                f"Shaded areas: epochs of high variability."
            )

            if feat_contrib is not None and not feat_contrib.empty:
                st.markdown(
                    "<div class='ui-section' style='margin-top:20px'>Feature contributions</div>"
                    "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:12px'>"
                    "Which features drove the sound profile shifts most."
                    "</div>",
                    unsafe_allow_html=True
                )

                contrib = (
                    feat_contrib.groupby('feature')['contribution']
                    .mean()
                    .reset_index()
                )
                contrib['abs'] = contrib['contribution'].abs()
                contrib = contrib.sort_values('abs', ascending=True)

                colors = [
                    professional_theme['accent_blue'] if v >= 0 else professional_theme['accent_pink']
                    for v in contrib['contribution']
                ]

                fig_fc = go.Figure(go.Bar(
                    x=contrib['contribution'],
                    y=contrib['feature'],
                    orientation='h',
                    marker_color=colors,
                    text=[f"{v:+.2f}" for v in contrib['contribution']],
                    textposition='outside',
                    textfont=dict(color=theme['text'], size=11),
                    hovertemplate='<b>%{y}</b><br>Contribution: %{x:+.3f}<extra></extra>',
                ))

                fig_fc.update_layout(
                    height=300,
                    margin=dict(t=20, b=40, l=140, r=40),
                    paper_bgcolor=theme['bg'],
                    plot_bgcolor=theme['bg'],
                    font=dict(color=theme['text']),
                    xaxis=dict(
                        title='Contribution',
                        showgrid=True, gridcolor='rgba(128,128,128,0.15)',
                        zeroline=True, zerolinecolor='rgba(128,128,128,0.4)',
                        tickfont=dict(color=theme['text']),
                        title_font=dict(color=theme['text']),
                    ),
                    yaxis=dict(
                        showgrid=False, title='',
                        tickfont=dict(color=theme['text']),
                    ),
                    showlegend=False,
                )

                st.plotly_chart(fig_fc, width='stretch',
                                config={'displayModeBar': False},
                                key='time_pro_variability_fc')

                st.caption(
                    "Average contribution across High-shift months. "
                    "Positive = pushed the profile away from baseline; "
                    "negative = pulled it back."
                )









    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Time indices</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Per-index trends across three windows: Lifetime → Last 18 months → Last 90 days. "
        "Cards show the value for the selected window and its change against the previous one."
        "</div>",
        unsafe_allow_html=True
    )

    TIME_INDICES = [
        'Music Day Share',
        'Listening Consistency Index',
        'Listening Variability',
        'Music Recency Index',
        'Night Listening Share',
        'Platform Desktop Share',
        'Average Sessions per Day',
        'Declining Engagement Rate',
        'Total Listening Hours',
        'Average Tracks per Day',
        'Session Depth Index'
    ]

    for start in [0, 3, 6, 9]:
        cols = st.columns(3)
        for col, idx_name in zip(cols, TIME_INDICES[start:start+3]):
            with col:
                render_single_variant_v3_dot(
                    idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                    key_extra=f'time_v3_{start}',
                    phrase_placement='inline'
                )
    st.caption("≈ — value close to category boundary")

    with st.expander('Index definitions'):
        for idx_name in [
            'Music Day Share',
            'Listening Consistency Index',
            'Listening Variability',
            'Music Recency Index',
            'Night Listening Share',
            'Platform Desktop Share',
            'Average Sessions per Day',
            'Declining Engagement Rate',
            'Total Listening Hours',
            'Average Tracks per Day',
            'Session Depth Index',
        ]:
            info = indices_display.get(idx_name, {})
            what = info.get('description_en', '')
            notes = info.get('notes_en', '')

            if not what and not notes:
                continue

            block = (
                f"<div style='margin-bottom:14px'>"
                f"<div style='font-weight:600; color:{interactive_accent}; "
                f"font-size:1rem'>{idx_name}</div>"
            )
            if what:
                block += (
                    f"<div style='font-size:0.9rem; color:{theme['text']}; "
                    f"opacity:0.85; margin-top:2px'>{what}</div>"
                )
            if notes:
                block += (
                    f"<div style='font-size:0.85rem; color:{theme['text']}; "
                    f"opacity:0.6; margin-top:4px; font-family:monospace'>"
                    f"{notes}</div>"
                )
            block += "</div>"
            st.markdown(block, unsafe_allow_html=True)

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )
    