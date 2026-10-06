import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from data.loaders import load_parquet, load_kpi_summary
from logic.profile import get_cluster_name
from ui.components import render_personal_card_variant, render_single_variant_v4_capsules



def _hex_to_rgba(hex_code, alpha=0.12):
    h = hex_code.lstrip('#')
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    return f'rgba(255,0,127,{alpha})'


def render(mode, selected_stage, cfg):
    theme = cfg['dashboard']['themes'][mode.lower()]
    kpi_summary = load_kpi_summary()

    st.markdown("<div class='ui-title'>Collection</div>", unsafe_allow_html=True)
   

    playlist_portraits = load_parquet('collection/playlist_portraits.parquet')
    playlist_collaborators = load_parquet('collection/playlist_collaborators.parquet')

    if playlist_portraits is None or playlist_portraits.empty:
        st.warning('No collection data available.')
        return

    if mode == 'Personal':
        _render_personal(playlist_portraits, playlist_collaborators,
                         kpi_summary, selected_stage, theme, cfg)
    elif mode == 'Professional':
        _render_professional(playlist_portraits, selected_stage, theme, cfg)


def _render_personal(playlist_portraits, playlist_collaborators,
                     kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']

    st.markdown(
        "<div class='ui-subtitle'>"
        "Your playlist collection — how each one was built and how you use it."
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<div class='ui-section'>Your playlists</div>",
        unsafe_allow_html=True
    )

    available_types = sorted(playlist_portraits['playlist_type'].dropna().unique().tolist())
    type_filter = st.radio(
        'Playlist type',
        ['All'] + available_types,
        horizontal=True,
        label_visibility='collapsed',
        key='collection_type_filter'
    )

    filtered = playlist_portraits.copy()
    if type_filter != 'All':
        filtered = filtered[filtered['playlist_type'] == type_filter]
    filtered = filtered.sort_values('total_valid_listens', ascending=False)
    playlist_names = filtered['playlist_name'].dropna().unique().tolist()

    if not playlist_names:
        st.info('No playlists match this filter.')
        return

    selected_playlist = st.selectbox(
        'Pick a playlist',
        playlist_names,
        key='collection_playlist_select'
    )
    pl_row = playlist_portraits[playlist_portraits['playlist_name'] == selected_playlist].iloc[0]

    st.markdown(
        f"<div style='font-size:1.7rem; font-weight:700; "
        f"color:{theme['text']}; margin-top:20px; margin-bottom:4px'>"
        f"{selected_playlist}</div>"
        f"<div style='font-size:0.95rem; opacity:0.7; color:{theme['text']}'>"
        f"{pl_row.get('playlist_type', '')} · {pl_row.get('total_tracks', 0)} tracks · "
        f"{pl_row.get('total_valid_listens', 0):,} valid plays</div>",
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='ui-section'>How it sounds</div>",
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        radar_metrics = ['valence_med', 'energy_med', 'danceability_med', 'acousticness_med', 'instrumentalness_med']
        radar_values = [pl_row.get(m, 0) for m in radar_metrics]
        radar_labels = ['Valence', 'Energy', 'Danceability', 'Acousticness', 'Instrumentalness']
        radar_values_closed = radar_values + [radar_values[0]]
        radar_labels_closed = radar_labels + [radar_labels[0]]

        sound_core_local = load_parquet(f'sound/sound_core_{selected_stage}.parquet')
        theme_colors_local = dash_config['themes']['personal']
        cluster_color_config = dash_config.get('cluster_colors', {}).get('personal', {})
        cluster_color_map = {
            name: theme_colors_local[color_key]
            for name, color_key in cluster_color_config.items()
        }

        cluster_names_local = {}
        if sound_core_local is not None and not sound_core_local.empty:
            cs = sound_core_local.groupby('cluster').agg(
                energy=('energy', 'median'),
                acousticness=('acousticness', 'median'),
                instrumentalness=('instrumentalness', 'median'),
                valence=('valence', 'median'),
                danceability=('danceability', 'median')
            ).reset_index()
            cs['cluster_name'] = cs.apply(get_cluster_name, axis=1)
            cluster_names_local = dict(zip(cs['cluster'], cs['cluster_name']))

        fig_radar = go.Figure()

        fig_radar.add_trace(go.Scatterpolar(
            r=radar_values_closed, theta=radar_labels_closed,
            fill='toself', name='This playlist',
            line=dict(color=theme['accent_pink'], width=2),
            fillcolor='rgba(255,0,127,0.15)',
            hovertemplate='<b>%{theta}</b><br>This playlist: %{r:.2f}<extra></extra>',
            hoverlabel=dict(
                bgcolor=theme['sidebar_bg'],
                bordercolor=theme['accent_pink'],
                font=dict(color=theme['text'], size=12)
            )
        ))

        if sound_core_local is not None and not sound_core_local.empty:
            core_metrics = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']
            for cluster_id in sorted(sound_core_local['cluster'].unique()):
                cluster_df = sound_core_local[sound_core_local['cluster'] == cluster_id]
                cluster_values = [cluster_df[m].mean() for m in core_metrics]
                cluster_values_closed = cluster_values + [cluster_values[0]]
                cluster_name = cluster_names_local.get(cluster_id, f'Cluster {cluster_id}')
                cluster_color = cluster_color_map.get(cluster_name, theme['accent_pink'])
                fig_radar.add_trace(go.Scatterpolar(
                    r=cluster_values_closed, theta=radar_labels_closed,
                    fill='toself', name=cluster_name,
                    line=dict(color=cluster_color, width=2, dash='dot'),
                    fillcolor=_hex_to_rgba(cluster_color, 0.1),
                    opacity=0.75,
                    hovertemplate=f'<b>%{{theta}}</b><br>{cluster_name}: %{{r:.2f}}<extra></extra>',
                    hoverlabel=dict(
                        bgcolor=theme['sidebar_bg'],
                        bordercolor=cluster_color,
                        font=dict(color=theme['text'], size=12)
                    )
                ))

        fig_radar.update_layout(
            height=420,
            margin=dict(t=20, b=60, l=40, r=40),
            paper_bgcolor=theme['bg'],
            font=dict(color=theme['text']),
            polar=dict(
                bgcolor=theme['bg'],
                radialaxis=dict(visible=False, range=[0, 1]),
                angularaxis=dict(gridcolor='rgba(255,255,255,0.15)')
            ),
            showlegend=True,
            legend=dict(
                orientation='h', yanchor='bottom', y=-0.15,
                xanchor='center', x=0.5,
                font=dict(color=theme['text'], size=10)
            )
        )
        st.plotly_chart(fig_radar, width='stretch', config={'displayModeBar': False}, key='collection_personal_radar')

        st.markdown(
            f"<div class='ui-caption' style='margin-top:8px; text-align:center'>"
            f"Clusters shown are your sound core for <b>{STAGE_LABELS[selected_stage]}</b>. "
            f"Switching the period changes which clusters appear."
            f"</div>",
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-bottom:6px'>Top genres</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='font-size:1rem; color:{theme['text']}; "
            f"line-height:1.5'>{pl_row.get('top_genres', '—')}</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-top:16px; margin-bottom:6px'>Breadth</div>"
            f"<div style='font-size:1rem; color:{theme['text']}'>"
            f"{pl_row.get('unique_genres', 0)} genres · "
            f"diversity {pl_row.get('genre_diversity', 0):.2f} · "
            f"popularity {pl_row.get('popularity_med', 0):.0f}/100</div>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-top:16px; margin-bottom:6px'>Era</div>",
            unsafe_allow_html=True
        )
        decade_2000s = pl_row.get('decade_2000s', 0)
        decade_pre_2000 = pl_row.get('decade_pre_2000', 0)
        older_share = decade_2000s + decade_pre_2000
        st.markdown(
            f"<div style='font-size:1rem; color:{theme['text']}; line-height:1.5'>"
            f"Mode year: {pl_row.get('mode_release_year', '—')}<br>"
            f"2020s: {pl_row.get('decade_2020s', 0):.0%} · "
            f"2010s: {pl_row.get('decade_2010s', 0):.0%} · "
            f"older: {older_share:.0%}</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<div class='ui-section' style='margin-top:24px'>How you use it</div>",
        unsafe_allow_html=True
    )

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-bottom:6px'>Engagement</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='font-size:1rem; color:{theme['text']}; line-height:1.6'>"
            f"Listened: {pl_row.get('share_listened', 0):.0%}<br>"
            f"Skip rate: {pl_row.get('skip_rate_all_events', 0):.1%}<br>"
            f"Full play: {pl_row.get('full_play_share_valid', 0):.1%}</div>",
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-bottom:6px'>Top tracks</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='font-size:0.95rem; color:{theme['text']}; "
            f"line-height:1.5'>{pl_row.get('top_tracks', '—')}</div>",
            unsafe_allow_html=True
        )

    if selected_playlist in playlist_collaborators['playlist_name'].values:
        st.markdown(
            f"<div style='font-size:0.9rem; opacity:0.65; "
            f"color:{theme['text']}; margin-top:16px; margin-bottom:6px'>Participants</div>",
            unsafe_allow_html=True
        )
        collab_data = playlist_collaborators[playlist_collaborators['playlist_name'] == selected_playlist]
        for _, c in collab_data.iterrows():
            st.markdown(
                f"<div style='font-size:0.95rem; color:{theme['text']}'>"
                f"{c.get('display_name', 'Unknown')} — "
                f"{c.get('additions', 0)} additions ({c.get('role', '')})</div>",
                unsafe_allow_html=True
            )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Your collection highlights</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Three signals about how you build and use playlists overall."
        "</div>",
        unsafe_allow_html=True
    )
    collection_cards = [
        ('Playlist Stickiness Rate', 'Stickiness'),
        ('Social Music Share', 'Social'),
        ('Playlist Update Frequency', 'Update'),
    ]
    cols = st.columns(3)
    for col, (idx_name, display) in zip(cols, collection_cards):
        with col:
            render_personal_card_variant(
                'B', idx_name, kpi_summary, selected_stage, theme, cfg, mode='Personal',
                key_extra=f'collection_{idx_name}',
                display_name=display
            )


def _render_professional(playlist_portraits, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    takeaway = cfg['takeaway']
    professional_theme = dash_config['themes']['professional']
    st.markdown(
        "<div class='ui-subtitle'>"
        "Playlist collection metrics — how playlists were built, "
        "how they're maintained, and how they age."
        "</div>",
        unsafe_allow_html=True
    )

    st.caption("Base: playlist-level metadata, not event-based.")

    st.markdown("---")
    
    if selected_stage != 'global':
        st.info(
            "Playlist collection metrics (takeaway, fill types, activity) "
            "are computed on the full history. Switch to Lifetime to see them."
        )
    else:

        takeaways_col = []

        fill_summary = load_parquet('collection/collection_fill_summary.parquet')
        if fill_summary is not None and not fill_summary.empty:
            dominant_fill = fill_summary.loc[fill_summary['playlists'].idxmax(), 'fill_type']
            dominant_dict = takeaway.get('collection', {}).get('dominant_fill_type', {})
            takeaway_text = (
                dominant_dict.get(dominant_fill + '_en')
                or dominant_dict.get(dominant_fill)
            )
            if takeaway_text:
                takeaways_col.append(takeaway_text)

        activity_scatter = load_parquet('collection/collection_activity_scatter.parquet')
        if activity_scatter is not None and not activity_scatter.empty:
            active_share = (activity_scatter['activity_group'].str.startswith('active')).mean()
            active_share_level = 'high' if active_share >= 0.5 else 'low'
            active_share_dict = takeaway.get('collection', {}).get('active_share', {})
            active_share_text = active_share_dict.get(active_share_level + '_en')
            if active_share_text:
                takeaways_col.append(active_share_text)

        if takeaways_col:
            bg_color = _hex_to_rgba(professional_theme['text'], 0.05)
            bullets_html = (
                f"<div style='background:{bg_color}; "
                f"border-radius:10px; padding:20px 24px; "
                f"border-left:3px solid {professional_theme['accent_blue']}'>"
                f"<div class='ui-section' style='margin-top:0'>Product takeaway</div>"
                f"<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
                f"Recommendations generated from the current playlist collection."
                f"</div>"
                f"<ul style='margin:0; padding-left:18px;'>"
            )
            for t in takeaways_col:
                bullets_html += (
                    f"<li style='font-size:1rem; font-weight:600; "
                    f"line-height:1.5; margin-bottom:10px'>"
                    f"<span style='color:{professional_theme['accent_blue']}'>{t}</span>"
                    f"</li>"
                )
            bullets_html += "</ul></div>"
            st.markdown(bullets_html, unsafe_allow_html=True)
        else:
            st.info("No takeaway data available.")









        st.markdown("---")
        st.markdown(
            "<div class='ui-section'>Fill types summary</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "Distribution of playlist fill patterns — how each playlist was built."
            "</div>",
            unsafe_allow_html=True
        )
        if fill_summary is not None and not fill_summary.empty:
            fill_summary_display = fill_summary.copy()
            fill_summary_display['share'] = fill_summary_display['share'].round(1)
            fill_summary_display['avg_size'] = fill_summary_display['avg_size'].round(0).astype(int)

            headers = ['fill_type', 'playlists', 'avg_size', 'total_listens', 'share']
            header_labels = ['Fill type', 'Playlists', 'Avg size', 'Total listens', 'Share %']

            html = (
                '<table style="width:100%; border-collapse:collapse; '
                'border:1px solid rgba(128,128,128,0.3); font-size:0.95rem">'
                '<thead><tr>'
            )
            for h in header_labels:
                html += (
                    f'<th style="padding:8px 12px; text-align:left; '
                    f'border-bottom:1px solid rgba(128,128,128,0.3); '
                    f'font-weight:600">{h}</th>'
                )
            html += '</tr></thead><tbody>'

            for _, row in fill_summary_display[headers].iterrows():
                html += '<tr>'
                for h in headers:
                    html += (
                        f'<td style="padding:8px 12px; text-align:left; '
                        f'border-bottom:1px solid rgba(128,128,128,0.15)">'
                        f'{row[h]}</td>'
                    )
                html += '</tr>'

            html += '</tbody></table>'
            st.markdown(html, unsafe_allow_html=True)

            with st.expander('Fill types — definitions'):
                st.markdown(
                    f"<div style='margin-bottom:10px'>"
                    f"<span style='font-weight:600; color:{professional_theme['accent_blue']}'>curated</span>"
                    f"<span style='opacity:0.85'> — additions with at least one single-track "
                    f"addition OR gaps > 2 minutes.</span></div>"
                    f"<div style='margin-bottom:10px'>"
                    f"<span style='font-weight:600; color:{professional_theme['accent_blue']}'>batch</span>"
                    f"<span style='opacity:0.85'> — all additions in dense packets "
                    f"(intervals ≤ 2 min), no single-track additions.</span></div>"
                    f"<div style='margin-bottom:10px'>"
                    f"<span style='font-weight:600; color:{professional_theme['accent_blue']}'>mass_import</span>"
                    f"<span style='opacity:0.85'> — ≥100 tracks in one day, ≤15 min, "
                    f"<30% listened before.</span></div>"
                    f"<div style='margin-bottom:10px'>"
                    f"<span style='font-weight:600; color:{professional_theme['accent_blue']}'>empty</span>"
                    f"<span style='opacity:0.85'> — no tracks.</span></div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("No fill summary data.")

        st.markdown("---")
        st.markdown(
            "<div class='ui-section'>Playlist activity</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "Days since last update vs total valid listens. "
            "Marker size — unique tracks. Dashed lines mark medians."
            "</div>",
            unsafe_allow_html=True
        )



        if activity_scatter is not None and not activity_scatter.empty:
            # Защита от нулей и NaN — log(0) не существует
            activity_scatter = activity_scatter.copy()
            activity_scatter['listens_plot'] = (
                activity_scatter['total_listens'].fillna(1).clip(lower=1)
            )

            fig_scatter = px.scatter(
                activity_scatter,
                x='days_since_update',
                y='listens_plot',
                size='unique_tracks',
                size_max=30, 
                color='fill_type',
                hover_name='name_norm',
                color_discrete_map={
                    'mass_import': professional_theme['accent_pink'],
                    'batch': professional_theme['accent_orange'],
                    'curated': professional_theme['accent_green'],
                    'empty': professional_theme['text']
                },
                labels={
                    'days_since_update': 'Days since update',
                    'listens_plot': 'Total valid listens',
                    'unique_tracks': 'Unique tracks'
                }
            )

            fig_scatter.update_traces(
                marker=dict(line=dict(color='rgba(255,255,255,0.3)', width=0.5)),
                hoverlabel=dict(
                    bgcolor=theme['sidebar_bg'],
                    bordercolor=professional_theme['accent_pink'],
                    font=dict(color=theme['text'], size=12)
                )
            )            

            # Границы лог-шкалы — как в ноуте
            max_listens = activity_scatter['listens_plot'].max()
            fig_scatter.update_yaxes(type='log', range=[0, np.log10(max_listens * 1.5)])

            fig_scatter.update_layout(
                height=450,
                paper_bgcolor=theme['bg'],
                plot_bgcolor=theme['bg'],
                font=dict(color=theme['text']),
                xaxis=dict(tickfont=dict(color=theme['text']),
                           title_font=dict(color=theme['text'])),
                yaxis=dict(tickfont=dict(color=theme['text']),
                           title_font=dict(color=theme['text']),
                           showgrid=True, gridcolor='rgba(128,128,128,0.15)',
                           zeroline=False),
                legend=dict(font=dict(color=theme['text']))
            )

            median_days = activity_scatter['days_since_update'].median()
            median_listens = activity_scatter['total_listens'].median()

            fig_scatter.add_vline(
                x=median_days, line_dash='dash',
                line_color=professional_theme['text'], opacity=0.5,
                annotation_text=f'Median days: {median_days:.0f}',
                annotation_position='top right'
            )
            fig_scatter.add_hline(
                y=median_listens, line_dash='dash',
                line_color=professional_theme['text'], opacity=0.5,
                annotation_text=f'Median listens: {median_listens:.0f}',
                annotation_position='right'
            )

            st.plotly_chart(fig_scatter, width='stretch',
                            config={'displayModeBar': False},
                            key='collection_pro_activity')
            st.caption(
                "Dashed vertical line — median days since update. "
                "Dashed horizontal line — median total listens."
            )
        else:
            st.info("No activity data.")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Engagement</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "How actively playlists are maintained and used over time."
        "</div>",
        unsafe_allow_html=True
    )
    kpi_summary = load_kpi_summary()
    cols = st.columns(3)
    for col, idx_name in zip(cols, ['Playlist Stickiness Rate',
                                    'Playlist Update Frequency',
                                    'Active Playlist Days per Year']):
        with col:
            render_single_variant_v4_capsules(
                idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                key_extra=f'collection_engagement_{idx_name}'
            )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Diversity</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Breadth of the collection — social input, collaborators, and track variety."
        "</div>",
        unsafe_allow_html=True
    )
    cols = st.columns(3)
    for col, idx_name in zip(cols, ['Social Music Share',
                                    'Collaborator Diversity Index',
                                    'Track Diversity Index']):
        with col:
            render_single_variant_v4_capsules(
                idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                key_extra=f'collection_diversity_{idx_name}'
            )

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Structure</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "How playlists are organized — redundancy, creation pace, and artist concentration."
        "</div>",
        unsafe_allow_html=True
    )
    cols = st.columns(3)
    for col, idx_name in zip(cols, ['Playlist Redundancy Index',
                                    'Playlist Creation Frequency',
                                    'Top Artist Share']):
        with col:
            render_single_variant_v4_capsules(
                idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                key_extra=f'collection_structure_{idx_name}'
            )

    st.caption("≈ — value close to category boundary")

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )


STAGE_LABELS = {'global': 'Lifetime', 'recent_6q': 'Last 18mo', 'last_90d': 'Last 90d'}