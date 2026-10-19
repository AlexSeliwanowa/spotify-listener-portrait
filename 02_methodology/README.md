🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# 02_methodology

The core of the project. Here we check whether the changepoints produced by the standard method can be trusted — and why the naive "believe / don't believe" answer doesn't work.

Documentation in two formats:

- **`PELT_JOURNEY.md`** — 12 phases of verification, text without code. Available in English (`PELT_JOURNEY.md`) and Russian (`PELT_JOURNEY_ru.md`).
- **`time_detector_experiments.ipynb`** — the same path with code, cell outputs, and plots.

Both files cover the same ground. If the text disagrees with a cell output, the notebook wins. The notebook is entirely in Russian.

It started with `ruptures.Pelt` on the listening history: 7 changepoints. Independent verification confirmed 5, one — only through a different mechanism, one — nowhere. From this grew a separate folder with 12 phases: BIC instead of `pen=10`, bootstrap, detrend, permutation-null. The result — three point layers (PELT-A, PELT-B, Cosine), a storm zone layer (Storm), and a separate Variability axis. The final architecture is in `## Final Architecture` below.

Other project layers (`00_prep`, EDA, dashboard) are either input or consumers of what is validated here.

## Files

| File | Format | Contents |
|---|---|---|
| `PELT_JOURNEY.md` | text | Summary of 12 phases. No code. |
| `time_detector_experiments.ipynb` | notebook | Code, cell outputs, plots, appendices A/B/C. |

Both files cover the same ground. The notebook is the source of numbers. If the text disagrees with a cell output, the notebook wins. Exception — numbers obtained in separate runs and not reproduced in the notebook (marked in the text): "top-4 of 71" and "×4.8" (appendix in `PELT_JOURNEY.md`); the K-table (`K=1…10`) and the synthetic test on 15 synthetic series — from a separate run, not folded into the notebook (the notebook is fixed as complete). Sensitivity over `pen=5…30` — a run in `01_data_analysis/03_eda_behavioral.ipynb`, not in this notebook.

## Problem Statement

`ruptures.Pelt` on the listening history yields 7 changepoints. Independent verification confirmed one (2022-05) only through a different mechanism, one (2022-10) nowhere.

Instead of choosing "trust the algorithm" or "don't trust" — an independent check. The algorithm searched for shifts in sound and behavior features and by construction cannot see changes in the artist lineup under similar sound. So the pipeline was rebuilt: three point layers, a storm-zone layer, and a separate Variability axis.

## 12 Phases

| # | Phase | What was checked | Outcome |
|---|---|---|---|
| 1 | Naive start | `pen=10` + 7 mixed features | ❌ broke |
| 2 | Bootstrap | Point stability under resampling | 🔄 zones, not points |
| 3 | Cosine | Artist shift under similar sound | ✅ confirmed |
| 4 | Layer split | Sound and behavior as one process | ✅ two separate |
| 5 | Periodization | Stable epochs between points | ❌ 0 of 6 |
| 6 | Self-percentile | Own rank as a level | ❌ structurally impossible |
| 7 | Noise-floor | Permutation null for Variability | ✅ works |
| 8 | Different nulls | One null for all features | 🔄 one per structure |
| 9 | Detrend | Axis correlations | 🔄 2 not established |
| 10 | Behavior Variability | Link to Burnout and Discovery | ⚠️ not in the compass |
| 11 | Toolkit | Generalization into a module | ✅ `VariabilityAnalyzer` |
| 12 | ALL vs VALID | One base for everything | 🔄 by semantics |

## Final Architecture

Three point layers and a zone layer:

| Layer              | Base          | Method                          | Result                                                |
| ------------------ | ------------- | ------------------------------- | ----------------------------------------------------- |
| PELT-A (sound)     | all + trimmed | PELT, L2, BIC penalty           | `2023-09`, `2024-02`, `2024-07`                       |
| PELT-B (behavior)  | all + trimmed | PELT, L2, BIC, smoothing        | `2021-08`, `2024-02`, `2024-12`, `2025-10`, `2026-03` |
| Cosine (artists)   | all + trimmed | cosine distance, MAD peaks      | `2021-02`, `2022-05`, `2024-02`                       |
| Storm (zones)      | all + trimmed | rolling std + binomial test     | `2021-01..2021-06`, `2023-10..2024-05`                |

11 marks across the point layers in 9 unique dates. `2024-02` is the only date visible to all three point layers. It is a single moment in time, so in statistical checks it counts once.

Points and storms do not overlap significantly: 1 of 9 points falls in storms (`p = 0.66`), and by episode range as shown in the dashboard, 2 of 9 (`p = 0.56`). Epochs of high Variability also do not overlap significantly with PELT points (4 of 7, expected 2.5, `p = 0.22`). This is expected: the layers answer different questions — points are about breaks, storms about the speed of change, epochs about variability within a window; overlap is not required.

Separately — the Sound Variability compass axis: share of significant monthly shifts within a 12-month window. Lifetime `0.417` (Medium), Current `0.083` (Low; last rolling-12 window, i.e. the last 12 months). Base — valid.

## Variability: What Determines the Result

- **The statistical threshold does not determine it.** At p90 / p95 / p99 lifetime 0.417 and level Medium are unchanged, High months 29 / 29 / 27.
- **The practical threshold determines the result.** Sweeping the quantile from p50 to p95 moves lifetime from 0.667 (High) down to 0.083 (Low); the level takes all three values. In production — p75.
- **Absolute alternative** (`PRACTICAL_THRESHOLDS × K`) — from a separate run, not folded into the notebook. Checked: at K=5 lifetime and level match p75, High months overlap on 22 of 27. K was fitted to match p75, so this is an alternative, not an independent calibration; sensitivity to K remains (0.750 at K=1, 0.167 at K=7.5).
- **Synthetic data** (15 synthetic time series: 5 stable / 5 moderate / 5 variable — a Variability metric test, not user profiles): medians 0.000 / 0.000 / 0.167. The metric separates stable and variable and does not distinguish moderate from stable — a metric boundary, not a threshold choice.

The Low / Medium / High label therefore describes variability at the chosen threshold and is relative to the profile. It is not comparable between users.

## Compass

Four axes: Discovery, Retention, Burnout, Sound Variability. The axes are built on different data. Checked in phase 9: no strong pairwise link was found. "Independent" here means "no strong link was found", not mathematical orthogonality.

Behavior Variability does not enter the compass. The reason: after detrending it is linked to Burnout (`r = −0.757`), and a fifth axis would break the compass orthogonality. A check for duplication of Discovery (the phase 8 set and the set with `orphan_share`) found no link — so this hypothesis drops out as a second reason; `discovery_rate` is not part of the set. The metric remains a research metric and is not exported to the dashboard.

## Appendices A/B/C

Notebook only. They do not enter the main narrative but justify decisions inside the phases.

| Appendix | Topic | Outcome |
|---|---|---|
| A | SNR | Not a signal criterion (permutation refuted it); before smoothing 5 of 7 features below 1.5 |
| B | Cut-scan + Storm | PELT/Cosine points do not cluster in storms: 1 of 9 (`p = 0.66`); by episode range 2 of 9 (`p = 0.56`) |
| C | Permutation null for Cosine | Does not work for categorical (`69 of 69` significant) |

## Appendix in `PELT_JOURNEY.md`

Text file only: comparison of the 7 primitive-detector points from `01_data_analysis/03_eda_behavioral.ipynb` with the final layers. Five of seven match within ±1 month against PELT-A or PELT-B; one (2022-05) is confirmed exactly through Cosine — a layer of a different nature; one (2022-10) is not confirmed by any layer. The final architecture adds three points the primitive method did not see.

## Consumers

The notebook writes nothing. Results reach the dashboard via `03_dashboard/dashboard_data_prep.ipynb`, which calls the same modules from `src/detectors/` and saves parquet files into `03_dashboard/dashboard/datasets/time/`.

## Reproduction

The notebook is an archival source of numbers, fixed as complete. If a rerun is needed: `00_prep` has run → `Restart & Run All`. Cell order matters — phase 9 uses `var_sound` (phase 7) and `var_beh` (phase 8), leave-one-out (phase 10) uses `events_beh` (phase 8) and `burnout_monthly` (phase 9). Some of the computations are stochastic: after a rerun, numbers in text cells should be cross-checked.

## Dependencies

`ruptures`, `numpy`, `pandas`, `scipy`, `plotly`, `scikit-learn`. Modules from `src/`: `detectors/*`, `diagnostics.py`, `aggregators/*`, `enrich.py`, `temporal.py`. The full list — `requirements-dev.txt` (the methodology layer; `requirements.txt` is dashboard-only).

## Limitations

- **Double-gate thresholds** (p99 null, ≥2 features, p75 practical) are heuristics calibrated on this data. The statistical threshold does not affect the result. The practical threshold determines the result (p50 → p95: lifetime 0.667 High → 0.083 Low), so the Variability label is relative to the profile and is not comparable between users.
- **The absolute threshold** (K=5) was fitted to match p75 and remains an alternative, not a replacement. Calibration on N ≥ 50 is not done. Perceptual thresholds are known only for tempo (JND around 3–6%); for other Spotify features no psychophysical thresholds exist.
- **N=1.** Principles are not validated on other profiles.
- **The metric does not distinguish moderate from stable** on synthetic data (both 0.000).
- Permutation null does not work for high-cardinality categorical features. This is a fact about the method, not an open question.
- Compass is a descriptive frame, not a statistical claim.
- `Behavior Var ↔ Burnout = −0.757` after detrending is the only functional link in the whole analysis. It is stable under leave-one-out across 10 High months (r from −0.614 to −0.842). Overlapping windows (rolling-12 and the yearly Burnout window; effective n below 58) and multiple testing across 10 pairs are not accounted for; bootstrap and correction were not applied.
- Behavior Variability and Sound Variability are not directly comparable: different High rules, different `min_periods` (0.167 at 4 and 0.125 at 12 versus 0.417 for Sound).
- Sound Variability lifetime `0.417` equals `null_high = 0.417` (the p95 of the null obtained by shuffling the month order while keeping the same number of High months). This means: the clustering of High months in time does not exceed chance. It says nothing about the level of variability — the level is set by the practical threshold and shifts from High (0.667) to Low (0.083) as the quantile goes p50 → p95. The dashboard label uses fixed thresholds 0.3 / 0.5.
- The link between Variability epochs and PELT points is not found (4 of 7, `p = 0.22`).
- **The notebook is entirely in Russian.** `time_detector_experiments.ipynb` — markdown cells, code comments, text outputs — all in Russian. `PELT_JOURNEY` is available in two languages (`PELT_JOURNEY.md` — EN, `PELT_JOURNEY_ru.md` — RU); an English-speaking reader should start there.

## Related Documentation

- [src](../src/README.md) — modules and detectors
- [00_prep](../01_data_analysis/00_prep/README.md) — input parquets
- [03_dashboard](../03_dashboard/README.md) — consumer
- [Root README](../README.md) — project overview