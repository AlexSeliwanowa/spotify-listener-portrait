import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from data.loaders import load_parquet, load_kpi_summary
from logic.profile import get_cluster_name
from ui.components import render_personal_card_variant, render_single_variant_v4_capsules




def render(mode, selected_stage, cfg):
    theme = cfg['dashboard']['themes'][mode.lower()]
    kpi_summary = load_kpi_summary()

    st.markdown("<div class='ui-title'>Sound</div>", unsafe_allow_html=True)

    sound_core = load_parquet(f'sound/sound_core_{selected_stage}.parquet')
    if sound_core is None or sound_core.empty:
        st.warning('No data for the selected period.')
        return

    COMPARE_FEATURES = ['energy', 'acousticness', 'instrumentalness', 'valence', 'danceability']
    DELTA_THRESHOLD = 0.05

    sound_core_global = load_parquet('sound/sound_core_global.parquet')

    base_names = {}
    global_medians = {}
    if sound_core_global is not None and not sound_core_global.empty:
        stats_g = sound_core_global.groupby('cluster').agg(
            energy=('energy', 'median'),
            acousticness=('acousticness', 'median'),
            instrumentalness=('instrumentalness', 'median'),
            valence=('valence', 'median'),
            danceability=('danceability', 'median')
        ).reset_index()
        stats_g['cluster_name'] = stats_g.apply(get_cluster_name, axis=1)
        base_names = dict(zip(stats_g['cluster'], stats_g['cluster_name']))
        global_medians = stats_g.set_index('cluster').to_dict('index')

    stats_w = sound_core.groupby('cluster').agg(
        energy=('energy', 'median'),
        acousticness=('acousticness', 'median'),
        instrumentalness=('instrumentalness', 'median'),
        valence=('valence', 'median'),
        danceability=('danceability', 'median')
    ).reset_index()

    def resolve_name(row):
        cid = row['cluster']
        base = base_names.get(cid, f'Cluster {cid}')
        if cid not in global_medians:
            return base
        shifted = any(
            abs(row[f] - global_medians[cid][f]) > DELTA_THRESHOLD
            for f in COMPARE_FEATURES
        )
        if shifted:
            return get_cluster_name(row)
        return base

    stats_w['cluster_name'] = stats_w.apply(resolve_name, axis=1)
    cluster_names = dict(zip(stats_w['cluster'], stats_w['cluster_name']))

    sound_core['cluster_name'] = sound_core['cluster'].map(cluster_names).fillna('Mixed Style')

    cluster_stats = sound_core.groupby('cluster').agg(
        pc1_median=('pc1', 'median'),
        pc2_median=('pc2', 'median'),
    ).reset_index()
    cluster_stats = cluster_stats.merge(
        sound_core[['cluster', 'cluster_name']].drop_duplicates(),
        on='cluster'
    )
    cluster_stats = cluster_stats.sort_values('pc1_median')
    cluster_order = cluster_stats['cluster_name'].tolist()
    clusters = cluster_stats['cluster'].tolist()

    if mode == 'Personal':
        _render_personal(sound_core, sound_core_global, cluster_stats, cluster_order, clusters,
                         base_names, kpi_summary, selected_stage, theme, cfg)
    elif mode == 'Professional':
        _render_professional(sound_core, cluster_order, clusters, cluster_names,
                             kpi_summary, selected_stage, theme, cfg)


def _render_personal(sound_core, sound_core_global, cluster_stats, cluster_order, clusters,
                     base_names, kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']

    st.markdown(
        "<div class='ui-subtitle'>"
        "What worlds your taste is made of — clusters, signature tracks, and key traits."
        "</div>",
        unsafe_allow_html=True
    )

    theme_colors = dash_config['themes']['personal']
    cluster_color_config = dash_config.get('cluster_colors', {}).get('personal', {})
    cluster_color_map = {
        name: theme_colors[color_key]
        for name, color_key in cluster_color_config.items()
    }

    _all_g = []
    for g in sound_core['genres_normalized'].dropna():
        for item in str(g).split(','):
            item = item.strip()
            if item and item != 'unknown':
                _all_g.append(item)
    _global_gc = pd.Series(_all_g).value_counts()

    GENRE_PALETTE = [
        theme_colors['accent_pink'],
        theme_colors['accent_blue'],
        theme_colors['accent_green'],
        theme_colors['accent_purple'],
        theme_colors['accent_orange'],
        theme_colors['accent_yellow'],
        theme_colors['accent_cyan'],
        theme_colors['accent_red'],
        theme_colors['accent_lime'],
        theme_colors['accent_magenta'],
        theme_colors['accent_teal'],
        theme_colors['accent_amber'],
    ]
    needed_genres = list(_global_gc.head(12).index)

    for _cl in sound_core['cluster_name'].dropna().unique():
        _cl_df = sound_core[sound_core['cluster_name'] == _cl]
        _cl_g = []
        for g in _cl_df['genres_normalized'].dropna():
            for item in str(g).split(','):
                item = item.strip()
                if item and item != 'unknown':
                    _cl_g.append(item)
        _cl_gc = pd.Series(_cl_g).value_counts()
        for _genre in _cl_gc.head(7).index:
            if _genre not in needed_genres:
                needed_genres.append(_genre)

    GENRE_COLOR_MAP = {
        genre: GENRE_PALETTE[i % len(GENRE_PALETTE)]
        for i, genre in enumerate(needed_genres)
    }

    view_options = ['All'] + cluster_order
    selected_view = st.radio('View', view_options, horizontal=True, key='sound_view_selector')

    st.markdown(
        "<div class='ui-section'>Your taste core</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:12px'>"
        "Every dot is a track. Dots that sit close together share a similar sound."
        "</div>",
        unsafe_allow_html=True
    )

    fig = px.scatter(
        sound_core,
        x='pc1',
        y='pc2',
        color='cluster_name',
        category_orders={'cluster_name': cluster_order},
        color_discrete_map=cluster_color_map,
        size='play_count',
        size_max=35,
        hover_name='track_name',
        hover_data={
            'artist_name': True,
            'play_count': True,
            'popularity': True,
            'pc1': False,
            'pc2': False,
            'cluster_name': False
        },
        labels={'pc1': '', 'pc2': ''}
    )

    for trace in fig.data:
        if selected_view == 'All':
            trace.marker.opacity = 0.7
        else:
            if trace.name == selected_view:
                trace.marker.opacity = 0.7
            else:
                trace.marker.opacity = 0.15

    for trace in fig.data:
        trace.marker.line.width = 0
        trace.marker.line.color = 'rgba(0,0,0,0)'

    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Artist: %{customdata[0]}<br>"
            "Plays: %{customdata[1]}<br>"
            "Popularity: %{customdata[2]}"
            "<extra></extra>"
        )
    )

    pc1_min = sound_core['pc1'].min()
    pc1_max = sound_core['pc1'].max()
    pc2_min = sound_core['pc2'].min()
    pc2_max = sound_core['pc2'].max()

    padding_x = (pc1_max - pc1_min) * 0.08
    padding_y = (pc2_max - pc2_min) * 0.08

    xaxis_range = [pc1_min - padding_x, pc1_max + padding_x]
    yaxis_range = [pc2_min - padding_y, pc2_max + padding_y]

    fig.update_layout(
        margin=dict(t=60, b=40, l=40, r=30),
        paper_bgcolor=theme['bg'],
        plot_bgcolor=theme['bg'],
        font=dict(color=theme['text']),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', range=xaxis_range),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title='', range=yaxis_range),
        showlegend=False,
    )

    color_map = {name: cluster_color_map.get(name, theme_colors['accent_amber']) for name in cluster_order}

    if len(cluster_order) == 2:
        fig.add_annotation(
            x=pc1_min, y=pc2_max, text=cluster_order[0], showarrow=False,
            font=dict(color=color_map[cluster_order[0]], size=14),
            xanchor='left', yanchor='top'
        )
        fig.add_annotation(
            x=pc1_max, y=pc2_min, text=cluster_order[1], showarrow=False,
            font=dict(color=color_map[cluster_order[1]], size=14),
            xanchor='right', yanchor='bottom'
        )
    else:
        for _, row in cluster_stats.iterrows():
            fig.add_annotation(
                x=row['pc1_median'],
                y=row['pc2_median'] + (pc2_max - pc2_min) * 0.05,
                text=row['cluster_name'],
                showarrow=False,
                font=dict(color=color_map[row['cluster_name']], size=12),
                xanchor='center', yanchor='bottom'
            )

    cluster_centroids = sound_core.groupby('cluster_name')[['pc1', 'pc2']].median()

    sig_tracks = []
    for name in cluster_order:
        if name not in cluster_centroids.index:
            continue
        cx, cy = cluster_centroids.loc[name, 'pc1'], cluster_centroids.loc[name, 'pc2']
        sub = sound_core[sound_core['cluster_name'] == name].copy()
        sub['dist'] = ((sub['pc1'] - cx) ** 2 + (sub['pc2'] - cy) ** 2) ** 0.5
        sig_tracks.append(sub.nsmallest(3, 'dist'))
    sig_tracks_df = pd.concat(sig_tracks) if sig_tracks else pd.DataFrame()

    if not sig_tracks_df.empty:
        fig.add_trace(go.Scatter(
            x=sig_tracks_df['pc1'],
            y=sig_tracks_df['pc2'],
            mode='markers',
            marker=dict(
                size=22,
                color='rgba(0,0,0,0)',
                line=dict(width=2, color=theme['text'])
            ),
            hovertext=sig_tracks_df.apply(
                lambda r: f"{r['track_name']} — {r['artist_name']}", axis=1
            ),
            hoverinfo='text',
            showlegend=False
        ))

    st.plotly_chart(fig, width='stretch',
                    config={'displayModeBar': True, 'displaylogo': False},
                    key='sound_core_scatter')

    cluster_info = {}
    for name in cluster_order:
        cluster_data = sound_core[sound_core['cluster_name'] == name]
        if not cluster_data.empty:
            medians = cluster_data[['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']].median().round(3)
            cluster_info[name] = {
                'count': len(cluster_data),
                'medians': medians.to_dict()
            }

    st.markdown("---")
    st.markdown(
        "<div class='ui-section' style='margin-top:8px'>Your sonic worlds</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:20px'>"
        "Each cluster is a distinct sound world. Signature tracks, genres, and top artists inside."
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    n_cols = len(cluster_order)
    cols = st.columns(n_cols, gap='large')

    def col_align(i, total):
        if i == 0:
            return 'left'
        if i == total - 1:
            return 'right'
        return 'center'

    for i, name in enumerate(cluster_order):
        if selected_view != 'All' and selected_view != name:
            continue
        align = col_align(i, len(cluster_order))
        with cols[i]:
            cluster_color = color_map.get(name, theme['text'])
            cluster_id = clusters[i]
            original_name = base_names.get(cluster_id, name)
            was_renamed = (name != original_name) and (selected_stage != 'global')

            if was_renamed:
                display_name = (
                    f"{name} "
                    f"<span style='font-size:0.75rem; opacity:0.7; font-weight:400'>"
                    f"· shifted from {original_name}</span>"
                )
            else:
                display_name = name

            st.markdown(
                f"<div style='font-size:1.3rem; font-weight:600; "
                f"color:{cluster_color}; margin-bottom:8px; text-align:{align}'>"
                f"{display_name}</div>",
                unsafe_allow_html=True
            )

            if name in cluster_info:
                info = cluster_info[name]
                st.markdown(
                    f"<div style='font-size:1.1rem; font-weight:600; margin-bottom:6px; margin-bottom:10px; text-align:{align}'>"
                    f"Tracks: {info['count']}</div>",
                    unsafe_allow_html=True
                )
                feature_labels = {
                    'valence': 'Mood',
                    'energy': 'Energy',
                    'danceability': 'Dance',
                    'acousticness': 'Acoustic',
                    'instrumentalness': 'Instr.'
                }
                for feature, value in info['medians'].items():
                    label = feature_labels.get(feature, feature.capitalize())
                    pct = int(round(value * 100))
                    st.markdown(
                        f"<div style='display:flex; align-items:center; gap:8px; margin-bottom:4px; "
                        f"width:90%; "
                        f'{"margin-right:auto" if align == "left" else ("margin-left:auto" if align == "right" else "margin:0 auto")}' f"'>"
                        f"<div style='width:65px; font-size:0.85rem; color:{cluster_color}'>{label}</div>"
                        f"<div style='flex:1; height:10px; background:rgba(128,128,128,0.15); border-radius:5px; overflow:hidden'>"
                        f"<div style='width:{pct}%; height:100%; background:{cluster_color}'></div>"
                        f"</div>"
                        f"<div style='width:42px; text-align:right; font-size:0.85rem; color:{cluster_color}'>{pct}%</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                st.markdown("---")
                st.markdown(
                    f"<div style='font-size:1.1rem; font-weight:600; margin-top:8px; margin-bottom:20px; text-align:{align}'>Signature tracks:</div>",
                    unsafe_allow_html=True
                )
                sig_sub = sig_tracks_df[sig_tracks_df['cluster_name'] == name] \
                    if not sig_tracks_df.empty else pd.DataFrame()
                if not sig_sub.empty:
                    for _, tr in sig_sub.iterrows():
                        st.markdown(
                            f"<div style='line-height:1.7; font-size:1rem; "
                            f"color:{cluster_color}; margin-bottom:4px; text-align:{align}'>"
                            f"• {tr['track_name']} — {tr['artist_name']}</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.caption("no data")

                st.markdown("---")
                cluster_data_c = sound_core[sound_core['cluster_name'] == name]

                c_genres = []
                for g in cluster_data_c['genres_normalized'].dropna():
                    for item in str(g).split(','):
                        item = item.strip()
                        if item and item != 'unknown':
                            c_genres.append(item)
                gc = pd.Series(c_genres).value_counts()

                unknown_c = (
                    cluster_data_c['genres_normalized']
                    .fillna('').str.strip().eq('unknown').sum()
                )

                top7 = gc.head(7)
                others_c = gc.iloc[7:].sum()

                parts_c = [top7]
                if others_c > 0:
                    parts_c.append(pd.Series({'Others': others_c}))
                if unknown_c > 0:
                    parts_c.append(pd.Series({'Unknown': unknown_c}))
                c_data = pd.concat(parts_c)

                if not c_data.empty:
                    seg_colors = []
                    for lbl in c_data.index:
                        if lbl == 'Others':
                            seg_colors.append('rgba(128,128,128,0.5)')
                        elif lbl == 'Unknown':
                            seg_colors.append('rgba(60,60,60,0.7)')
                        else:
                            seg_colors.append(GENRE_COLOR_MAP.get(lbl, 'rgba(128,128,128,0.35)'))

                    fig_c = go.Figure(go.Pie(
                        labels=c_data.index,
                        values=c_data.values,
                        hole=0.55,
                        rotation=-90,
                        direction='clockwise',
                        sort=False,
                        marker=dict(
                            colors=seg_colors,
                            line=dict(color='rgba(0,0,0,0)', width=0)
                        ),
                        textinfo='percent',
                        textposition='outside',
                        textfont=dict(color=theme['text'], size=10),
                        hovertemplate='<b>%{label}</b><br>%{value} tracks (%{percent})<extra></extra>'
                    ))
                    fig_c.update_layout(
                        height=280,
                        margin=dict(t=40, b=20, l=10, r=10),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=theme['text'], size=10),
                        showlegend=True,
                        legend=dict(
                            orientation='v',
                            yanchor='middle',
                            y=0.5,
                            xanchor='left',
                            x=1.02,
                            font=dict(size=9, color=theme['text'])
                        )
                    )
                    st.plotly_chart(
                        fig_c, width='stretch',
                        config={'displayModeBar': False},
                        key=f'cluster_donut_{name}'
                    )
                else:
                    st.caption("no genre data")

                artist_counts_c = (
                    cluster_data_c['artist_name']
                    .dropna()
                    .value_counts()
                    .head(7)
                )

                if not artist_counts_c.empty:
                    ac = artist_counts_c.iloc[::-1]
                    fig_a = go.Figure()

                    for artist, cnt in ac.items():
                        fig_a.add_trace(go.Scatter(
                            x=[0, cnt], y=[artist, artist],
                            mode='lines',
                            line=dict(color=cluster_color, width=2),
                            hoverinfo='skip',
                            showlegend=False
                        ))

                    fig_a.add_trace(go.Scatter(
                        x=ac.values,
                        y=ac.index,
                        mode='markers+text',
                        marker=dict(size=14, color=cluster_color),
                        text=[str(v) for v in ac.values],
                        textposition='middle right',
                        textfont=dict(color=theme['text'], size=10),
                        hovertemplate='<b>%{y}</b><br>%{x} tracks<extra></extra>',
                        showlegend=False
                    ))

                    fig_a.update_layout(
                        height=260,
                        margin=dict(t=10, b=10, l=10, r=30),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=theme['text'], size=10),
                        xaxis=dict(
                            showgrid=False, zeroline=False, showticklabels=False,
                            range=[0, ac.max() * 1.25]
                        ),
                        yaxis=dict(
                            showgrid=False,
                            tickfont=dict(color=theme['text'], size=10),
                            automargin=True
                        ),
                        showlegend=False
                    )
                    st.plotly_chart(
                        fig_a, width='stretch',
                        config={'displayModeBar': False},
                        key=f'cluster_artists_{name}'
                    )
                else:
                    st.caption("no artist data")

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Your key traits</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Nine facets of your taste — tap ⓘ on any card to learn more."
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    sound_cards = [
        ('Hipster Index', 'Niche'),
        ('Genre Diversity Index', 'Genres'),
        ('Artist Diversity Index', 'Artists'),
        ('Acoustic-Energy Balance', 'Synthetic / Organic'),
        ('Mood Bias', 'Mood'),
        ('Groove Index', 'Groove'),
        ('Vocalness Index', 'Vocals'),
        ('Ambient Factor', 'Ambient'),
        ('Commercial Pressure', 'Mainstream'),
    ]
    for start in [0, 3, 6]:
        cols = st.columns(3)
        for col, (idx_name, display) in zip(cols, sound_cards[start:start+3]):
            with col:
                render_personal_card_variant(
                    'B', idx_name, kpi_summary, selected_stage, theme, cfg, mode='Personal',
                    key_extra=f'sound_{idx_name}',
                    display_name=display
                )

    st.markdown(
        "<div style='text-align:center; margin-top:40px'>"
        "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
        "text-decoration:none'>↑ Back to tabs</a>"
        "</div>",
        unsafe_allow_html=True
    )


def _render_professional(sound_core, cluster_order, clusters, cluster_names,
                         kpi_summary, selected_stage, theme, cfg):
    dash_config = cfg['dashboard']
    professional_theme = dash_config['themes']['professional']


    st.caption("Base: my_music ∩ valid plays. Only saved tracks.")


    cluster_color_config = dash_config.get('cluster_colors', {}).get('professional', {})
    cluster_color_map = {
        name: professional_theme[color_key]
        for name, color_key in cluster_color_config.items()
    }

    st.markdown(
        "<div class='ui-section'>Audio features by cluster</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:12px'>"
        "Distribution of five audio features across clusters: valence, energy, danceability, acousticness, instrumentalness."
        "</div>",
        unsafe_allow_html=True
    )

    features = ['valence', 'energy', 'danceability', 'acousticness', 'instrumentalness']

    long_df = sound_core.melt(
        id_vars=['cluster_name'],
        value_vars=features,
        var_name='feature',
        value_name='value'
    )
    long_df['feature'] = long_df['feature'].str.capitalize()

    fig_box = px.box(
        long_df,
        x='feature',
        y='value',
        color='cluster_name',
        category_orders={
            'cluster_name': cluster_order,
            'feature': [f.capitalize() for f in features]
        },
        color_discrete_map=cluster_color_map, points=False
    )

    fig_box.update_traces(line=dict(width=2), boxmean=True)

    fig_box.update_layout(
        height=480,
        margin=dict(t=40, b=40, l=40, r=20),
        paper_bgcolor=theme['bg'],
        plot_bgcolor=theme['bg'],
        font=dict(color=theme['text']),
        boxmode='group',
        boxgap=0.25,
        boxgroupgap=0.15,
        legend_title_text='',
        xaxis=dict(
            title='',
            tickfont=dict(color=theme['text'], size=13),
            showgrid=False,
        ),
        yaxis=dict(
            title=dict(text='Value', font=dict(color=theme['text'])),
            tickfont=dict(color=theme['text']),
            gridcolor='rgba(128,128,128,0.15)',
            zerolinecolor='rgba(128,128,128,0.3)',
        ),
        legend=dict(
            orientation='h', yanchor='bottom', y=1.05,
            xanchor='center', x=0.5,
            font=dict(color=theme['text'], size=13)
        )
    )

    st.plotly_chart(fig_box, width='stretch', config={'displayModeBar': False}, key='sound_pro_boxplot')

    clustering_meta = load_parquet('sound/sound_clustering_meta.parquet')
    if clustering_meta is not None and not clustering_meta.empty:
        meta_row = clustering_meta.iloc[0]
        sil = meta_row['silhouette']

        if sil >= 0.5:
            grade, grade_color = 'Good structure', theme['accent_green']
        elif sil >= 0.25:
            grade, grade_color = 'Moderate structure', theme['accent_orange']
        else:
            grade, grade_color = 'Weak structure', theme['accent_red']

        st.markdown(
            f"<div class='ui-caption' style='margin-top:8px'>"
            f"Cluster separation: "
            f"<span style='color:{grade_color}; font-weight:600'>{grade}</span> · "
            f"silhouette {sil:.3f} · "
            f"k={int(meta_row['k'])} · "
            f"{int(meta_row['n_tracks']):,} tracks · "
            f"measured on Lifetime — the same model is applied to all windows."
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<div class='ui-section' style='margin-top:28px'>Cluster summary</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Per-cluster aggregates: track count, share of the taste core, total plays, "
        "median audio features, and top genres."
        "</div>",
        unsafe_allow_html=True
    )

    cluster_summary = sound_core.groupby('cluster').agg(
        tracks=('track_name', 'count'),
        total_plays=('play_count', 'sum'),
        valence_med=('valence', 'median'),
        energy_med=('energy', 'median'),
        danceability_med=('danceability', 'median'),
        acousticness_med=('acousticness', 'median'),
        instrumentalness_med=('instrumentalness', 'median')
    ).reset_index()

    def get_top_genres_with_counts(cluster_df, top_n=5):
        all_genres = []
        for genres_str in cluster_df['genres_normalized'].dropna():
            all_genres.extend([
                g.strip() for g in genres_str.split(',')
                if g.strip() != 'unknown'
            ])
        genre_counts = pd.Series(all_genres).value_counts()
        top = genre_counts.head(top_n)
        return ', '.join(f"{g} ({n})" for g, n in top.items()) if len(top) > 0 else '—'

    top_genres_map = {}
    for cluster_id in clusters:
        cluster_df = sound_core[sound_core['cluster'] == cluster_id]
        top_genres_map[cluster_id] = get_top_genres_with_counts(cluster_df)

    cluster_summary['top_genres'] = cluster_summary['cluster'].map(top_genres_map)

    total_tracks = cluster_summary['tracks'].sum()
    cluster_summary['share'] = (cluster_summary['tracks'] / total_tracks * 100).round(1)

    cluster_summary = cluster_summary.rename(columns={
        'tracks': 'Tracks',
        'share': 'Share',
        'total_plays': 'Plays',
        'valence_med': 'Valence',
        'energy_med': 'Energy',
        'danceability_med': 'Danceability',
        'acousticness_med': 'Acousticness',
        'instrumentalness_med': 'Instrumentalness',
        'top_genres': 'Top Genres'
    })

    for col in ['Valence', 'Energy', 'Danceability', 'Acousticness', 'Instrumentalness']:
        cluster_summary[col] = cluster_summary[col].round(2)

    cluster_summary['Share'] = cluster_summary['Share'].apply(lambda x: f"{x}%")

    cluster_summary['Cluster'] = cluster_summary['cluster'].apply(
        lambda x: cluster_names.get(x, f'Cluster {x}')
    )
    cluster_summary = cluster_summary.drop('cluster', axis=1)

    cluster_summary = cluster_summary[
        ['Cluster', 'Tracks', 'Share', 'Plays',
         'Valence', 'Energy', 'Danceability', 'Acousticness', 'Instrumentalness',
         'Top Genres']
    ]

    def color_cluster_name(name):
        c = cluster_color_map.get(name, theme['text'])
        return f"<span style='color:{c}; font-weight:700'>{name}</span>"

    cluster_summary_html = cluster_summary.copy()
    cluster_summary_html['Cluster'] = cluster_summary_html['Cluster'].apply(color_cluster_name)

    html_table = cluster_summary_html.to_html(index=False, escape=False)
    html_table = html_table.replace(
        '<table border="1" class="dataframe">',
        '<table style="width:100%; border-collapse:collapse; '
        'border:1px solid rgba(128,128,128,0.3)">'
    )
    html_table = html_table.replace(
        '<th>',
        '<th style="padding:8px; text-align:left; '
        'border-bottom:1px solid rgba(128,128,128,0.3)">'
    )
    html_table = html_table.replace(
        '<td>',
        '<td style="padding:8px; text-align:left; '
        'border-bottom:1px solid rgba(128,128,128,0.15)">'
    )

    st.markdown(html_table, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "<div class='ui-section'>Core indices</div>"
        "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
        "Primary quantitative characteristics of the taste core. Computed for the selected period; values reflect valid plays only."
        "</div>",
        unsafe_allow_html=True
    )

    if kpi_summary is not None and not kpi_summary.empty:

        core_indices = [
            'Hipster Index',
            'Genre Diversity Index',
            'Artist Diversity Index',
            'Acoustic-Energy Balance',
            'Mood Bias',
            'Commercial Pressure'
        ]
        for start in [0, 3]:
            cols = st.columns(3)
            for col, idx_name in zip(cols, core_indices[start:start+3]):
                with col:
                    render_single_variant_v4_capsules(
                        idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                        key_extra=f'sound_core_{start}'
                    )

        st.markdown(
            "<div class='ui-section' style='margin-top:20px'>Additional metrics</div>"
            "<div class='ui-subtitle' style='margin-top:-8px; margin-bottom:16px'>"
            "Additional indicators for listening scale and depth: total volume,"
            "daily intensity, and emotional spread relative to the personal baseline."
            "Not part of core taste indices."
            "</div>",
            unsafe_allow_html=True
        )

        additional_indices = [
            'Total Listening Hours',
            'Average Tracks per Day',
            'Average Events per Day',
            'Mood Diversity Index (personal median)'
        ]
        for start in [0, 3]:
            cols = st.columns(3)
            for col, idx_name in zip(cols, additional_indices[start:start+3]):
                with col:
                    render_single_variant_v4_capsules(
                        idx_name, kpi_summary, selected_stage, theme, cfg, mode='Professional',
                        key_extra=f'sound_add_{start}'
                    )
        st.caption("≈ — value close to category boundary")

        st.markdown(
            "<div style='text-align:center; margin-top:40px'>"
            "<a href='#tabs-top' style='font-size:0.9rem; opacity:0.6; "
            "text-decoration:none'>↑ Back to tabs</a>"
            "</div>",
            unsafe_allow_html=True
        )