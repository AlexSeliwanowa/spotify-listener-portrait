🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# src/ — project architecture

Modules for processing Spotify events, building behavioural metrics, and
assembling dashboard parquets.

Used in the prep notebook (`03_dashboard/dashboard_data_prep.ipynb`).
Each cell calls functions from here; it does no calculations itself.

## Principles

**1. Layers only know about the layer below.**
A lower layer never references an upper one. `enrich` doesn't know about
`indices`; `bases` doesn't know about `detectors`. Change an upper layer
— the lower one is untouched.

**2. Rule of two.**
If a function is used in 2+ notebooks or 2+ places — it lives in `src/`.
If in one — inline in the notebook.

**3. Module by the nature of the entity, not by consumer.**
A base definition doesn't know who uses it. `bases.py` doesn't mention
PELT. The consumer states explicitly: "I take valid" or "I take trimmed".

**4. Single source of truth.**
`valid_play` is defined once in `enrich.add_valid_play`. Everyone —
`bases.valid`, `indices.skip_risk_index`, `portrait` — reads the column.
Change the definition — edit in one place.

**5. Folder — if there are 3+ files.**
Otherwise — flat. `bases.py`, `temporal.py`, `indices.py` sit side by
side. `detectors/`, `aggregators/`, `clustering/` are folders.

## Tree

```
src/
├── README.md                     ← this file
├── __init__.py
│
├── paths.py                      infrastructure: paths, folders
├── loaders.py                    infrastructure: parquet loading
├── mask.py                       infrastructure: masking personal data
│
├── helpers.py                    pure utilities, no domain
├── temporal.py                   windows and cold-start trimming
├── bases.py                      df slices (all / valid / trimmed / …)
├── enrich.py                     adding columns to df
├── diagnostics.py                SNR, permutation (for research)
├── indices.py                    ~35 indices + kpi_summary orchestrator
├── portrait.py                   compass: Discovery, Retention, Burnout
├── variability_export.py         Variability export to parquet
│
├── aggregators/                  event-to-period rollups
│   ├── music.py                  monthly sound medians
│   ├── behavior.py               behavioural aggregates + obsessions
│   └── temporal.py               time series M/W/D for dashboard
│
├── clustering/                   splitting sound into groups
│   ├── kmeans.py                 k selection, KMeans, PCA
│   └── sound_core.py             taste core by window
│
└── detectors/                    pattern detection in aggregates
    ├── pelt_common.py            BIC penalty + bootstrap
    ├── pelt_sound.py             PELT-A (sound)
    ├── pelt_behavior.py          PELT-B (behaviour)
    ├── cosine_identity.py        identity shift (artists)
    ├── storm.py                  storm episodes
    ├── cut_scan.py               transition regions
    ├── variability.py            Variability via toolkit
    ├── variability_toolkit.py    universal toolkit
    └── changepoints.py           orchestrator: assembles 4 point layers
```

## Layers

Each layer works with the output of the previous one. There are no
backward references.

```
5. Detectors           pattern detection (PELT, Cosine, Storm)
   ▲
6. Aggregators         events → periods (medians, shares)
   ▲
7. Indices             number metrics from slices
   ▲
8. Bases               df slices (valid, trimmed, …)
   ▲
9. Enrich              adding columns (valid_play, my_music, …)
   ▲
10. Infrastructure      paths, loading, masking (no data work)
```

**Masking is outside the layers.** `mask.py` is called at the very end
of the prep notebook, before writing parquets to the public `datasets/`
folder. This is not part of the calculation pipeline — it is a separate
pass over the final aggregates. It reads `scripts/mask_config.json`
(local, not in git), replaces real identifiers with masks. Only personal
identifiers (email, account IDs, personal playlist names) are masked in
four parquets; track names, artists, and timestamps are not masked.

## Modules

### Infrastructure

**`paths.py`** — paths and folders.
- `get_project_root()` — repository root
- `get_base_path()` — data root `data/00_output/`
- `get_dashboard_path()` — private parquets `data/00_output/dashboard/`
- `get_datasets_path()` — public parquets `03_dashboard/dashboard/datasets/`
- `get_public_dashboard_path()` — root `03_dashboard/dashboard/`
- `get_config_path()` — dashboard configs
- `ensure_dashboard_subdirs()` — creates `sound/`, `time/`, `behavior/`, `collection/` in the private folder
- `ensure_datasets_subdirs()` — same in the public folder
- `get_references_path()`, `get_genre_mapping_path()` — reference data

**`loaders.py`** — loading.
- `load_all(base_path)` — returns a dict with `df`, `tracks_exportify`, `playlist_links`, `library_tracks`, `owner_ids`, `playlists_metadata`.

**`mask.py`** — masking personal data.
- `mask_all(**dfs)` — takes dataframes by name, returns masked ones.
- Works in memory: receives and returns dataframes, writes nothing.
- Reads `scripts/mask_config.json` (in `.gitignore`). Without config — warning and return as is.
- Masks: `account`, `owner_id`, `display_name`, `email`, `Added By`, `collaborators`, `playlist_name`, `name_norm`, `added_by_id`.

### Primitives

**`helpers.py`** — pure utilities. No imports from `src/`.
- `normalized_entropy(counts)` — Shannon entropy in [0, 1]
- `platform_type(platform)` — `mobile / desktop / web / other`
- `is_desktop(platform)`, `is_mobile(platform)`
- `desktop_share(df)`, `mobile_share(df)`
- `night_share(df, hours=(0, 5))`

**`temporal.py`** — time.
- `compute_windows(df, playlist_links)` — three windows: `global`, `recent_6q` (18 months), `last_90d` (90 days). Returns `max_data_date`, `recent_start`, `last90_start`, `windows`.
- `trim_cold_start(df, gap_months=1)` — cuts the incomplete last month and the cold start (gap > 1 month in the first year).

**`bases.py`** — df slices. Reads columns only, creates nothing.
- `all_events(df)` — whole df
- `valid(df)` — `valid_play == True`
- `trimmed(df)` — after `trim_cold_start`
- `trimmed_valid(df)` — trimmed ∩ valid

**`enrich.py`** — adds columns. Removes no rows.
- `add_timestamps(df)` — `ts_naive`, `period`
- `add_valid_play(df)` — `valid_play`
- `add_first_valid_seen(df)` — `first_valid_seen`
- `add_my_music(df, library_tracks, playlist_links, owner_ids)` — `my_music`
- `add_track_source(df, library_tracks, playlist_links, owner_ids)` — `source` (my_music / foreign / orphan)
- `add_sessions(df, gap_min=30)` — `session_id`, `gap_min`, `new_session`
- `session_stats(df)` — aggregate by session

**`diagnostics.py`** — signal checks for research.
- `compute_snr(series, window=3)` — signal-to-noise ratio
- `snr_gain_permutation(series, n_perm=200, …)` — permutation test

**`indices.py`** — metric indices.
- ~35 public functions: `hipster_index`, `genre_diversity_index`, `music_day_share`, `skip_risk_index`, `session_depth_index`, …
- Orchestrator `build_kpi_summary(df, windows, tracks_exportify, playlist_links)` — assembles everything into a DataFrame (106 rows: 39 / 34 / 33 indices by global / recent_6q / last_90d windows)
- `INDEX_SPECS` — index metadata (unit / category / audience)

**`portrait.py`** — compass. Three public functions + two orchestrators.
- `discovery_global(df_valid)` — Discovery (quarterly median)
- `retention_90(df_valid)` — Retention (90-day)
- `burnout(df_valid)` — Burnout
- `build_axes(df, windows)` — three axes without Variability
- `build(df, windows, output_path, variability_score)` — assembles `portrait.parquet` (Variability comes from outside)
- **Variability and Burnout in `recent_6q`** are intentionally equal to the `global` value: both axes reflect the whole history (as stated to the user in `ui/behavior.py`). The current Variability (last rolling-12 window) lives separately — `variability_meta.parquet['current_score']`, Time panel.
- **Behavior Variability does not enter the compass:** after detrending it is linked to Burnout (r ≈ −0.76), a fifth axis would break compass independence. Source — `02_methodology`, phases 9–10. It is not computed in `src/` and is not exported to the dashboard.

**`variability_export.py`** — Variability export.
- `export_variability(R, out_dir)` — writes 4 files: `variability`, `meta`, `feature_contributions`, `epochs_sound`

### Aggregators

**`aggregators/music.py`** — monthly sound.
- `SOUND_FEATURES` — 6 features (valence, energy, danceability, instrumentalness, acousticness, tempo)
- `build_monthly_sound(df)` — monthly medians

**`aggregators/behavior.py`** — monthly behaviour + obsessions.
- `BEHAVIOR_FEATURES_PELT` — 6 features for PELT-B
- `build_monthly_behavior(df)` — hours, tracks, skip_rate, played_frac, obsession_share, discovery_rate + smoothed
- `is_obsession_event(df)` — obsession flag per event
- `build_strong_obsessions(df)` — runs of ≥5 in a row
- `build_obsession_base(df, freq)` — share of obsession events by period

**`aggregators/temporal.py`** — time series for the dashboard.
- `AGG_WINDOWS` — frequencies (global→M, recent_6q→W, last_90d→D)
- `build_time_series(df, label, start, end, freq, first_post_gap_month)` — with NaN rows for missing periods
- `build_time_series_meta(df, first_post_gap_month)` — metadata (first event, gaps, etc.)

### Clustering

**`clustering/kmeans.py`** — generic KMeans/PCA.
- `find_optimal_k(X_scaled)` — k sweep by silhouette
- `fit_clustering(X_scaled, k)`, `fit_pca(X_scaled)`
- `mark_characteristic(df, top_n=5)` — characteristic track flag

**`clustering/sound_core.py`** — Sound specifics.
- `CLUSTER_FEATURES` — 5 features (without tempo)
- `prepare_core(df, start, end, my_music_uris)` — valid ∩ my_music
- `apply_to_window(core, scaler, kmeans, pca)` — models trained on global applied to a window

### Detectors

**`detectors/pelt_common.py`** — shared PELT logic.
- `compute_bic_pen(X)` — BIC penalty (Lavielle)
- `pelt_points(X_norm, sigma2, n_dims, index)` — points + bootstrap

**`detectors/pelt_sound.py`** — PELT-A (sound). Uses `SOUND_FEATURES` and `pelt_common`.
- `detect(monthly_sound)` → dict with points and stability

**`detectors/pelt_behavior.py`** — PELT-B (behaviour). Uses `BEHAVIOR_FEATURES_PELT` and `pelt_common`.
- `detect(monthly_behavior)` → dict

**`detectors/cosine_identity.py`** — identity shift.
- `detect(df, id_col='artist_name')` → points (cosine distance peaks)

**`detectors/storm.py`** — storm episodes.
- `detect(monthly_sound)` → df with `std_all`, `is_storm`, `episode_id`

**`detectors/cut_scan.py`** — transition regions.
- `detect(monthly_sound)` → regions (not used in the dashboard)

**`detectors/variability.py`** — Variability via toolkit.
- `run_variability_pipeline(df, monthly_sound, window, seed)` → dict
- Constant `MIN_TRANSITIONS_FOR_VARIABILITY = 24`

**`detectors/variability_toolkit.py`** — universal toolkit.
- `VariabilityAnalyzer` — class with `fit`, `variability_score`, `check_stability`, `feature_contributions`.
- Generalized tool, not tied to Spotify. Candidate for extraction into a separate `variability-toolkit` repository — decision not yet made.

**`detectors/changepoints.py`** — orchestrator.
- `build(df, output_path)` — calls 4 detectors, assembles `time_changepoints.parquet` + `time_storms.parquet`
- The `confidence` column in `time_changepoints` is bootstrap stability, but scales from different layers are not comparable (Cosine ≈ 0.8 — MAD threshold stability; PELT ≈ 0.1–0.37 — point stability to month exclusion).

## Bases

Which layer is computed on which base. **Single project-wide decision.**

| Layer | Base | Why |
|---|---|---|
| **Discovery / Retention / Burnout** | valid | conscious listening |
| **Variability** | trimmed_valid | taste without cold start |
| **PELT-A (sound)** | trimmed | track sound does not depend on skip; result on valid is the same (same 3 points), on all there is more data; base matches other point layers |
| **PELT-B (behaviour)** | trimmed | skip_rate and played_frac are dead on valid |
| **Cosine (artists)** | trimmed | artist lineup across all events |
| **Storm** | trimmed | rate of change across all events |
| **Obsessions** | df (all) | session-level and event-level on all events |
| **Time series** | df (all); valid for all metrics except skip_rate (all) | dashboard shows full history, including cold start (gray zone) |
| **Collection** | df (all) | reference data, playlists |
| **kpi_summary** | by index | some valid, some all — each decides for itself |

## Calculation principles

**1. dropna by own columns.**
Each index/detector does `dropna` only on the columns it uses. Not on the
common set.
Example: `acoustic_energy_balance` uses `energy` and `acousticness`,
dropna on them. `loudness` (with NaN) does not affect it.

**2. Smoothing for noisy features.**
`tracks`, `skip_rate`, `played_frac`, `discovery_rate` are smoothed with
rolling(3) before PELT-B.

**3. Bootstrap — for point stability.**
PELT points are filtered by bootstrap ≥ 0.10 (drop 15% months, 200
iterations).

**4. Windows — relative to max_data_date.**
`recent_6q` = max_data_date − 18 months. `last_90d` = max_data_date −
90 days.
Not calendar-based — otherwise an incomplete quarter distorts the window.

**5. Variability thresholds.**
Statistical threshold permutation-null — p99; practical — p75 of raw
shifts (≥2 features). Sensitivity to p90/p95/p99 is checked
(`02_methodology`, phase 7): the final level does not change.

## What is NOT in src/

Anything used only once stays **inline in the notebook**:
- Behavior specifics: funnel, skips, cohorts
- Collection specifics: portraits, collab, fill
- One-off research in separate notebooks (backbtn, immediate saves, dynamic save status)

**Rule:** second consumer → move to `src/`. Until then — inline.

## Who uses what

- **Prep notebook** (`03_dashboard/dashboard_data_prep.ipynb`) — orchestrator.
  Imports everything needed, calls in the right order, saves parquets.
  At the end — `mask_all` for four parquets with personal data.
- **Separate research notebooks** (`01_eda_basic`, `02_eda_temporal`,
  `03_eda_behavioral`, `04_eda_playlists`) — take `get_base_path` from `paths`.
  Only `04_eda_playlists` additionally calls `mask_all` in block 0.
  Do not duplicate analysis logic — it is inline in the notebooks.
- **Dashboard** (`03_dashboard/dashboard/app.py`) — reads only `datasets/`,
  does not work with `src/` directly.
- **`scripts/mask_config.json`** — read from `src/mask.py`, not in git.