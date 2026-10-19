🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# 03_dashboard

The final layer. Takes 31 parquets from `datasets/` and renders them in Streamlit — no recalculation. 

**Live version:** https://spotify-listener-portrait-a3resx9aolc4svjcpegwhq.streamlit.app/

**The dashboard is ready to run right after cloning the repository.** 31 parquets are already in `dashboard/datasets/` — the `data/` folder is not needed. Recalculation is only required if the data in `00_output/` has changed.

Five tabs (Sound, Time, Behavior, Collection, Overview) × three periods (Lifetime, Last 18 months, Last 90 days). Two modes — **Personal** and **Professional** — are described below in the "Personal vs. Professional Modes" section.

Data comes from two sources:
- **`00_prep`** — 15 parquets in `data/00_output/`.
- **`dashboard_data_prep.ipynb`** — 30 aggregates + masking → 31 parquets in `dashboard/datasets/`.

Calculation logic lives in `src/` and `dashboard_data_prep.ipynb`. The `app.py` itself only reads parquets and draws.

## Directory Structure

```text
03_dashboard/
├── dashboard_data_prep.ipynb           builds 31 parquets for the dashboard, copies to datasets/
├── METHODOLOGY_BEHAVIOR_COMPASS.md     archetype and compass logic
├── METHODOLOGY_BEHAVIOR_COMPASS_ru.md
├── README.md
├── README_ru.md
└── dashboard/                          the dashboard itself (Streamlit)
    ├── app.py                          entry point
    ├── pdf_report.py                   PDF generation
    ├── config/                         JSON configs: themes, thresholds, texts, archetypes
    ├── data/                           Python modules for loading parquets
    ├── logic/                          rendering and formatting logic
    ├── ui/                             five tabs (sound, time, behavior, collection, overview)
    ├── tests/                          smoke tests
    └── datasets/                       31 parquets — in git; four contain masked personal identifiers
```

## Data Flow & Architecture

Three layers:

**1. `01_data_analysis/00_prep/`** — assembles 15 parquets from raw Spotify exports into `data/00_output/`. History, features, playlists, library, owners.

**2. `dashboard_data_prep.ipynb`** — reads 6 of these parquets, calculates 30 aggregates. Writes privately to `data/00_output/dashboard/`, then masks and copies to `dashboard/datasets/` (31 parquets).

**3. Data masking.** In `datasets/`, only personal identifiers (email, account IDs, personal playlist names) are masked, in four parquets. The remaining parquets contain no identifiers. Before writing to `datasets/`, these four are passed through `src/mask.py`:

```text
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

## Data Preparation Pipeline

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

## Output Datasets

The output folder contains **31 parquets**: 30 new aggregates calculated by the prep notebook, plus the transferred `playlist_links.parquet`.

| Location | Count | What |
|---|---|---|
| `sound/` | 4 | `sound_core_global / recent_6q / last_90d` + `sound_clustering_meta` |
| `time/` | 10 | `time_series_*` ×3 + meta + changepoints + storms + variability + meta + contributions + epochs |
| `behavior/` | 10 | portrait + obsessions ×4 + funnels ×2 + skip ×2 + cohorts |
| `collection/` | 4 | portraits + collaborators + fill_summary + activity_scatter |
| root | 3 | `kpi_summary`, `eda_enriched`, `playlist_links` |
| **Total** | **31** | |

Full field-level description of each parquet — in markdown cells at the end of `dashboard_data_prep.ipynb`.

## Data Masking

Four parquets contain real values. Before writing to `datasets/` they are passed through `src/mask.py`:

| Parquet | What is masked |
|---|---|
| `collection/playlist_portraits` | `playlist_name` |
| `collection/playlist_collaborators` | `playlist_name`, `added_by_id`, `display_name` |
| `collection/collection_activity_scatter` | `name_norm` |
| `playlist_links.parquet` | `account`, `Added By`, `playlist_name`, `name_norm` |

Rules: email → `1@mail.com` / `2@mail.com` / `3@mail.com`, owner_id → `account_N`, display_name → `Account N`, external Added By → `user_NN`, personal playlists → `personal_<theme>_<number>`.

Mapping — in `scripts/mask_config.json`, local, in `.gitignore`. Without it masking is skipped, prep notebook warns.

## Dashboard Overview

**5 tabs × 2 modes × 3 periods.**

| Tab | What it shows |
|---|---|
| **Sound** | Sound clusters, scatter in PCA, signature tracks, top artists, genre donuts |
| **Time** | Time series, changepoints, storms, gray cold-start zone, Variability |
| **Behavior** | Compass (4 axes), obsessions, funnels, skips, cohorts |
| **Collection** | Playlists, autoportraits, participants, fill types |
| **Overview** | Archetype, takeaways, snapshot of indices, biggest shift, full reference |

## Personal vs. Professional Modes

One dashboard, two lenses on the data.

**Personal** answers the question "who are you as a listener". The person here is the **subject**: a warm, neutral tone; facts without judgment; not a single phrase like "this is good" or "this is bad". Even trend arrows remain uncolored by evaluation. Methodological caveats (like `≈` for borderline values or warnings about model fragility) do not appear here, because they are not facts about the person.

**Professional** answers the question "what does this mean, and how much can we trust it". The person here is the **object of analysis**. Metrics are evaluated through polarity (green and red only where "good" and "bad" actually make sense; taste metrics have no color). Exact values, formulas, applicability limits, and model quality (silhouette, match_distance) are shown.

**Core idea:** evaluation and uncertainty are shown only where they are appropriate, and neither is passed off as a fact about the person.

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

## Data Schema & Validation

`data/schemas.py` — list of required columns for each parquet. On load, `load_parquet` calls `validate()`. If a column is missing — red banner indicating exactly what. The dashboard doesn't fail silently.

## Testing

From the `dashboard/` folder:

```bash
python -m pytest tests/ -v
```

Smoke tests check the data contract, not logic: parquets in place, schemas match, `ui/*` modules import, `app.py` parses.

## Getting Started

**The dashboard is ready to run right after cloning the repository.** 31 parquets are already in `dashboard/datasets/`, no `data/` folder needed.

```bash
git clone https://github.com/AlexSeliwanowa/spotify-listener-portrait.git
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
```bash
jupyter notebook 03_dashboard/dashboard_data_prep.ipynb
```
Output: 30 aggregates in `data/00_output/dashboard/`, 31 parquets in `dashboard/datasets/`.

**3.** Restart the dashboard:
```bash
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
- **Rerun on other data has not been tested.** The data schema will match, and the dashboard will render a different number of clusters (KMeans sweeps `k` from 2 to 6, and another profile's optimum may shift). However, the cluster naming rules (`get_cluster_name` in `logic/profile.py`) use fixed absolute thresholds. If the user's audio feature distribution does not fall into these ranges, clusters may get uninformative names (e.g., `Mixed Style`).

## Related Documentation

- [Root README](../README.md) — project overview
- [01_data_analysis](../01_data_analysis/README.md) — EDA and data assembly
- [00_prep](../01_data_analysis/00_prep/README.md) — parquet assembly
- [02_methodology](../02_methodology/README.md) — Time Detector study
- [src](../src/README.md) — pipeline architecture
- [Compass methodology](./METHODOLOGY_BEHAVIOR_COMPASS.md) — archetype and compass logic