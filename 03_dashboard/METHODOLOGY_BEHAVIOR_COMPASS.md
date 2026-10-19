🇬🇧 English | [🇷🇺 Русский](./METHODOLOGY_BEHAVIOR_COMPASS_ru.md)

# Behavior Compass

# Behavior Compass — Methodology

**What this is.** A reference for the compass logic used in `03_dashboard`: four axes, nine archetypes, nearest-neighbor matching. The dashboard implements this document; if they disagree — the code is correct.

An author's tool for listener profiling. Displays the user across four axes and assigns one of nine archetypes.

This is not a psychometric test or a personality typology. A framework for reflection and product segmentation. The user gets an image of themselves through music; the analyst gets a guideline for personalization.

## Four Axes

**Discovery** — how actively the user seeks new music. Median quarterly Discovery Rate, thresholds 0.3 / 0.5. Source — Spotify Research (2022).

**Retention** — how often what is found returns. Share of new tracks that return within 90 days. Thresholds 0.3 / 0.5.

**Burnout** — how quickly favorite tracks fade. Share of core tracks (≥5 valid plays) that left rotation more than a year ago. Thresholds 0.3 / 0.5.

**Sound Variability** — how changeable the profile is over time. Share of significant monthly sound shifts within a 12-month window. Thresholds 0.3 / 0.5, fixed.

Each axis is reduced to a Low / Medium / High level. Four levels yield a four-letter code, e.g. `HHLM`.

## Archetypes

Nine of them. Matching — nearest-neighbor: user levels are converted to numbers (L=0, M=1, H=2), the Euclidean distance to each code is calculated, the closest wins.

`match_distance` is shown next to the archetype — it shows how exact the match is.

Clustering is not used. We tried KMeans on 81 theoretical combinations of levels. Silhouette 0.158 — weak structure: it clusters a uniform grid, not human data. Nearest-neighbor is more honest — it doesn't create an illusion of statistical rigor where there is none.

## Where it is shown in the dashboard

- **Overview (Personal)** — archetype name, personal phrase, radar chart with four axes.
- **Overview (Professional)** — Listener profile block: summary of levels, `match_distance`, recommendations (Key takeaways).
- **Behavior (Personal)** — radar chart, archetype card, explanation of each axis.
- **Behavior (Professional)** — exact axis values and levels (High / Medium / Low), the **Product takeaway** block (recommendations based on the current profile), split into **Recalculated per window** (Discovery and Retention for the selected period) and **Not recalculated per window** (Burnout and Variability are calculated once on the full history).
- **PDF report (Personal)** — compass and archetype are exported to PDF.

**Code.**
- Axis calculation — `src/portrait.py` (`discovery_global`, `retention_90`, `burnout`, `build_axes`).
- Archetype matching — `03_dashboard/dashboard/logic/profile.py`.
- Archetype definitions — `03_dashboard/dashboard/config/profile_labels.json`.
- Axis level thresholds — `03_dashboard/dashboard/config/indices_display.json`.

## Technical Justifications

**MIN_TRANSITIONS_FOR_VARIABILITY = 24.** Sound Variability is calculated via rolling 12 with `min_periods = window`. For the median of the rolling series to be stable, enough valid points are needed. 24 transitions yield 13 valid points. At the previous threshold of 18, there were 7 points — too few, one outlier shifts the median. 24 is the minimum sufficient. This is about 25 months of data.

**Data windows in the compass.** In `Lifetime` mode, all four axes are calculated over the entire history. In `Last 18 months` mode, the Discovery and Retention axes are recalculated for the selected window, while Burnout and Variability remain global (this is indicated by a note in the interface). In `Last 90 days` mode, the compass is hidden because at least 12 months of data are required. For the Variability axis, the compass always uses `lifetime_score` (the median over the entire history) because the compass answers the question "who am I overall". The `current_score` value (the last rolling-12 window) is displayed separately — on the Time tab.

## Limitations

**Thresholds and N=1.** Retention, Burnout, and Sound Variability are calibrated on this single profile. Discovery — from Spotify Research. For another profile, three of the four axes will require recalibration; transferability has not been tested.

**Nine archetypes do not cover the 81 combinations evenly.** `restless_wanderer` covers 10 of 81 (≈12%), `tourist` — 11 of 81 (≈14%). The maximum distance from a combination to the nearest archetype is 1.414: every point of the grid is covered, there are no "holes".

**Ties.** 23 out of 81 combinations yield a tie between the two closest archetypes. These are resolved by weights and the axis hierarchy D → V → R → B in `profile_labels.json`: on a tie, the senior axis decides, then the next one. After applying weights and hierarchy, no ties remain (0 out of 81). Changing the weights or axis order will change the winner for some combinations.

**Sound Variability within the compass depends on the practical threshold.** When the quantile changes from p50 to p95, lifetime changes from 0.667 (High) to 0.083 (Low). Details — in `02_methodology/README.md`, section "Limitations".

## Possible Development

The compass is calibrated on a single profile: thresholds 0.3/0.5, the nearest-neighbor rule, and p75 for Variability are fitted to this data. A test on 10–15 volunteers will show whether they transfer — whether the axes yield a meaningful spread of levels, whether the archetypes collapse into one or two, and whether Variability turns out to be Medium for everyone due to the self-relative threshold. Only after that — calibration on a larger sample and checking whether the archetypes reproduce as stable clusters, rather than a convenient partition of the axis space.