🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# 03_dashboard

**Live version:** https://spotify-listener-portrait-a3resx9aolc4svjcpegwhq.streamlit.app/

The final layer of the project: turns parquet files from `00_prep` into 31 aggregates ready for display in the Streamlit dashboard.

## Structure

```
03_dashboard/
├── dashboard_data_prep.ipynb   calculates 30 aggregates, masks, copies to datasets/
├── dashboard/                  the dashboard itself (Streamlit)
│   ├── app.py                  entry point
│   ├── config/                 JSON configs: themes, thresholds, texts, archetypes
│   ├── data/                   Python modules for loading parquets
│   ├── logic/                  rendering and formatting logic
│   ├── ui/                     five tabs (sound, time, behavior, collection, overview)
│   ├── tests/                  smoke tests
│   └── datasets/               31 parquets — in git; four contain masked personal identifiers, the rest have none
└── README.md
```

## How it works end-to-end

Three layers:

**1. `01_data_analysis/00_prep/`** — builds 15 parquet files from raw Spotify exports into `data/00_output/`. History, features, playlists, library, owners.

**2. `dashboard_data_prep.ipynb`** — reads 6 of these parquets, calculates 30 aggregates. Writes privately to `data/00_output/dashboard/`, then masks and copies to `dashboard/datasets/` (31 parquets).

**3. In `datasets/` only personal identifiers are masked (email, account IDs, personal playlist names), in four parquets. The remaining parquets contain no identifiers. Before writing to `datasets/`, these four are passed through `src/mask.py`:

```
data/00_output/*.parquet   (15 files)
        │
        ↓
dashboard_data_prep.ipynb
   ├─ reads 6 parquets
   ├─ calculates 30 aggregates → data/00_output/dashboard/
   ├─ masks 4 parquets via src/mask.py
   └─ copies to dashboard/datasets/  (31 parquets)
        │
        ↓
dashboard/app.py  →  streamlit run
```

## Prep notebook `dashboard_data_prep.ipynb`

**What it does by cells:**

- **Cells 0–1.** Imports from `src/` (aggregators, detectors, clustering, portrait, indices, mask). Reads 6 parquets: `eda_ready`, `tracks_exportify`, `playlist_links`, `library_tracks`, `owner_ids`, `playlists_metadata`. Runs `enrich` (`valid_play`, `my_music`, `session_id`, `source`). Calculates three windows: `global`, `recent_6q`, `last_90d`.
- **Sound.** Taste core selection (`valid ∩ my_music`), KMeans on 5 audio features, PCA. Trained on global, applied to other windows without retraining.
- **Time.** Time series across three windows. 4 changepoint layers: PELT-A (sound), PELT-B (behavior), Cosine (artists), Storm. Variability via permutation noise floor.
- **Behavior.** Compass (4 axes × 2 stages). Obsessions, funnels, skips, cohorts. 8 behavioral indices.
- **Collection.** Playlist autoportraits, collaborators, fill types, activity.
- **KPI.** `build_kpi_summary` from `src/indices.py` — ~35 indices, but not all are calculated for all windows: 39 (Lifetime) / 34 (Last 18 months) / 33 (Last 90 days) = 106 rows.
- **`eda_enriched.parquet`.** Slim copy of enriched `df` — 32 columns. Separate file so `app.py` doesn't recalculate enrich on every run.
- **Verification.** Checks all 30 parquets: file exists, columns present, keys unique.
- **Masking and copying.** 30 parquets to `dashboard/datasets/` + `playlist_links.parquet` at root. Masks 4 via `src/mask.py`.

**When to run:** after `00_prep`, before launching the dashboard. Once, or again if data in `00_output/` changed.

## What goes into `dashboard/datasets/`

31 parquets: the prep notebook calculates 30 aggregates, 31 parquets go to datasets/ — the difference is `playlist_links.parquet`.

| Location | Count | What |
|---|---|---|
| `sound/` | 4 | `sound_core_global / recent_6q / last_90d` + `sound_clustering_meta` |
| `time/` | 10 | `time_series_*` ×3 + meta + changepoints + storms + variability + meta + contributions + epochs |
| `behavior/` | 10 | portrait + obsessions ×4 + funnels ×2 + skip ×2 + cohorts |
| `collection/` | 4 | portraits + collaborators + fill_summary + activity_scatter |
| root | 3 | `kpi_summary`, `eda_enriched`, `playlist_links` |
| **Total** | **31** | |

Full field-level description of each parquet — in markdown cells at the end of `dashboard_data_prep.ipynb`.

## Masking

Four parquets contain real values. Before writing to `datasets/` they are passed through `src/mask.py`:

| Parquet | What is masked |
|---|---|
| `collection/playlist_portraits` | `playlist_name` |
| `collection/playlist_collaborators` | `playlist_name`, `added_by_id`, `display_name` |
| `collection/collection_activity_scatter` | `name_norm` |
| `playlist_links.parquet` | `account`, `Added By`, `playlist_name`, `name_norm` |

Rules: email → `1@mail.com` / `2@mail.com` / `3@mail.com`, owner_id → `account_N`, display_name → `Account N`, external Added By → `user_NN`, personal playlists → `personal_<theme>_<number>`.

Mapping — in `scripts/mask_config.json`, local, in `.gitignore`. Without it masking is skipped, prep notebook warns.

## Dashboard

**5 tabs × 2 modes × 3 periods.**

| Tab | What it shows |
|---|---|
| **Sound** | Sound clusters, scatter in PCA, signature tracks, top artists, genre donuts |
| **Time** | Time series, changepoints, storms, gray cold-start zone, Variability |
| **Behavior** | Compass (4 axes), obsessions, funnels, skips, cohorts |
| **Collection** | Playlists, autoportraits, participants, fill types |
| **Overview** | Archetype, takeaways, snapshot of indices, biggest shift, full reference |

## Personal / Professional

Same data, two lenses.

**Personal** answers "who am I". Dark theme. Addresses the user as "you". Archetype large, compass geometry, obsessions — "tracks you couldn't stop listening to". No formulas, no bases, no methodology. Cards with names (Niche, Genres, Skipper, Night Owl), not indices. Export — PDF for Lifetime.

**Professional** answers "what's in the data". Light theme. Impersonal. Caption with base in each tab. ⓘ and formulas on index cards. Plus what Personal lacks: funnels, cohorts, skip/full play split, changepoints table, cluster summary, feature contributions. Export — CSV of all indices × 3 windows.

This is not "simplified / full". These are two different languages about the same thing.

**Periods:** `Lifetime` (global), `Last 18 months` (recent_6q), `Last 90 days` (last_90d).

## Configuration

Display thresholds, texts, levels — in `config/*.json`. Local logic constants — in `ui/*.py`.

**JSON:**
- `indices_display.json` — thresholds, polarity, `max_value`, texts, formulas.
- `profile_labels.json` — 9 archetypes with codes.
- `dashboard_config.json` — themes, colors, `cluster_colors`, `profile_colors`, `typography`.
- `product_takeaway.json` — recommendations by axis.
- `time_definitions.json` — definitions for Time annotations.

**Hardcoded in UI** (deliberately): index lists for tabs (`TIME_INDICES`, `BEHAVIOR_INDICES`), compass axes order (`axes_order`), numeric levels (`level_num`), genre palette. Used in one place, rarely changed.

## Data contract

`data/schemas.py` — list of required columns for each parquet. On load, `load_parquet` calls `validate()`. If a column is missing — red banner indicating exactly what. The dashboard doesn't fail silently.

## Tests

From the `dashboard/` folder:

```
python -m pytest tests/ -v
```

Smoke tests check the data contract, not logic: parquets in place, schemas match, `ui/*` modules import, `app.py` parses.

## Launch

**The dashboard is ready to run right after cloning the repository.** 31 parquets are already in `dashboard/datasets/`, no `data/` folder needed.

```
git clone <repo-url>
cd spotify-listener-portrait
pip install -r requirements.txt
streamlit run 03_dashboard/dashboard/app.py
```

Opens at `http://localhost:8501`.

**Online:** https://spotify-listener-portrait-a3resx9aolc4svjcpegwhq.streamlit.app/

### If data changed

Full path:

**1.** Run `00_prep` — build 15 parquets in `data/00_output/`.

**2.** Run the prep notebook:
```
jupyter notebook 03_dashboard/dashboard_data_prep.ipynb
```
Output: 30 aggregates in `data/00_output/dashboard/`, 31 parquets in `dashboard/datasets/`.

**3.** Restart the dashboard:
```
streamlit run 03_dashboard/dashboard/app.py
```

**On Streamlit Cloud** — deploy from GitHub, same `app.py`. All parquets are already in `datasets/`. After `git push` — **Reboot** the app in the control panel.

## Limitations

- **Streamlit version is pinned** in `requirements.txt` (`1.60.0`). Updating — together with checking custom CSS.
- **The dashboard does not recalculate data.** Outdated parquet — will show outdated.
- **Streamlit frontend bug** — when switching modes frequently, React may crash with `NotFoundError: removeChild`. Fixed with F5.
- **Masking depends on `scripts/mask_config.json`**. Without it data goes to `datasets/` unmasked.
- **PDF report** — compass is drawn via matplotlib, visually simpler than in Streamlit (plotly). Limitation known, not a priority.
- **Variability label (Low / Medium / High) is relative to the profile** and is not comparable between users. In the dashboard it is used as an indicator within a user's history, not an absolute scale.
- **Rerun on your own data has not been tested.** The prep notebook can be run on your own Spotify export after `00_prep`, but thresholds (KMeans silhouette, stability 0.10, practical p75) are calibrated on the current data and may need revision. The output schema (`data/schemas.py`) transfers; the numbers do not.

## See also

- [Root README](../README.md) — project overview
- [01_data_analysis](../01_data_analysis/README.md) — EDA and data assembly
- [00_prep](../01_data_analysis/00_prep/README.md) — parquet assembly
- [02_methodology](../02_methodology/README.md) — Time Detector study
- [src](../src/README.md) — pipeline architecture