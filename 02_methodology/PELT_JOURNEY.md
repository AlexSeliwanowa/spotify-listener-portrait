🇬🇧 English | [🇷🇺 Русский](./PELT_JOURNEY_ru.md)

# PELT Journey: from a naive detector to a validated architecture

This document is the methodological path: 12 iterations checking whether
the changepoints in the listening history can be trusted. Each phase is
either a confirmation or a refutation of the previous step. The numbers
in the text are what was actually obtained; thresholds and choices are
separately marked as justified or heuristic. The source of numbers is
the notebook `time_detector_experiments.ipynb`; if the text disagrees
with a cell output, the notebook wins.

---

## Phase 1. Naive start

First run: `ruptures.Pelt`, `pen=10`, seven features without type
separation — valence, energy, danceability, instrumentalness, skip_rate,
played_frac, orphan_share. Result: 7 changepoints, scenario `cascade`,
Variability classified as High.

**What's wrong.** `pen=10` is a number picked by eye, not derived from a
formula or from the properties of the data. A sensitivity analysis
(`pen=5…30`) showed that the scenario shifts between
`cascade`/`moderate`/`single` depending on the penalty (a run in
`01_data_analysis/03_eda_behavioral.ipynb`) — the claim about "the
user's character" turned out to be an artifact of an arbitrary
parameter. Separately: `orphan_share` in this set semantically overlaps
with the future Discovery axis — the same idea measured twice under
different names. And mixing sound and behavioural features in one model
— different noise in kind, shifts different in meaning, one covariance
estimate for all.

**Decision.** Replace `pen=10` with a BIC formula (`σ²·dim·log(n)`,
MAD noise estimate). Split features by type in later stages.

---

## Phase 2. Bootstrap — zones, not points

500 iterations: 15% of months randomly dropped (order preserved), PELT
recomputed on each subsample. The share of repeats where a given month
yields a changepoint is the stability measure. Bootstrap here runs on
the same mixed 7-feature set (not audio-only).

**Result.** 5 of the 7 original points survived (stability threshold
0.10): `2022-05` (0.078) and `2024-11` (0.022) did not survive
resampling. Stability also showed the opposite: months with high
stability appeared that were not on the `pen=10` list at all — a signal
the naive model missed entirely. The top by stability clustered not
into points but into fuzzy zones of several adjacent months.

**What this means.** Two different checks yield different information:
stability to the penalty (did the point survive varying `pen`) and
stability to the data (did the point survive varying the sample). A
point can be stable to one and unstable to the other — not a
contradiction, but two independent axes of trust.

---

## Phase 3. Cosine — identity shift

PELT on continuous audio features catches a shift in average mood. If
specific artists changed while the mood stayed similar (similar
valence/energy, different names) — PELT cannot see it by construction.

**Method.** Cosine distance between artist share vectors of adjacent
months. Peaks via a `median + 2·MAD` threshold.

**Result.** 6 peaks → 3 clusters (bootstrap ≥0.82, production detector
on the all + trimmed base): `2021-02`, `2022-05`, `2024-02`. The genre
analogue of the same method returned noise — 15 peaks (7 months out of
12 in 2021 and the entire second half of 2023–2024), with no
discernible signal; genres as a separate layer are not used.

---

## Phase 4. Layer split — two independent processes

PELT-A (6 sound features, median, BIC penalty, base all + trimmed) and
PELT-B (6 behavioural, 4 smoothed, BIC penalty, base all + trimmed) are
computed separately.

The intersection between the points of the two layers — **one point**
(`2024-02`), not seven shared. This is not a noisy version of one
process — it is two structurally different processes that change at
different times. Mixing them into one model would have muted both
signals at once.

---

## Phase 5. Periodization — not confirmed

Hypothesis: between changepoints there are stable periods.

**Check.** History split into segments between transition zones (from
cut-scan). For each segment — comparison of first-half and second-half
medians against a practical significance threshold of 0.02.

**Result: 0 of 6 plateaus are stable inside.** The data drift
continuously rather than stepping between stable epochs. Recorded as a
negative result — periodization does not enter the final architecture;
instead a continuous picture is used (storm episodes — zones of
elevated rate of change, not "eras").

---

## Phase 6. Self-percentile — structural failure

Variability as a single compass index needs a Low/Medium/High scale.
First attempt: percentile of a month relative to the user's own history,
tercile bins.

**Synthetic check.** Two modelled profiles — objectively stable and
objectively variable (real shifts every ~5 months). Self-percentile gave
**both** ~34% of months in the High category — by construction,
regardless of the real difference between profiles. A null-based
approach distinguishes them: 8.5% vs 31.9% of High transitions.

**Conclusion.** Self-percentile is mathematically incapable of comparing
entities against each other — it is always uniform within a single
history, however large the real variability. Method dropped, not
calibrated further.

---

## Phase 7. Noise-floor via permutation — a working method

For each pair of adjacent months: events from both months are pooled,
randomly split back into groups of the same sizes, distance recomputed
— this is the null distribution of "random sampling noise for this N".

**Double gate.** A month is marked High only if the observed shift
simultaneously (a) exceeds the 99th percentile of the null distribution
and (b) is at least one practical threshold (calibrated as p75 of raw
monthly shifts, not a universal constant) on at least two features.
Without the practical gate, a large number of observations per month
makes almost any, even negligible, shift "statistically significant".

**Why it works.** The comparison is not against the user's own history
nor against other people's data, but against what pure chance would
give for this sample size — an absolute, not self-relative, criterion.

**Sensitivity to the threshold.** The statistical threshold
(p90 / p95 / p99) barely changes the result: lifetime 0.417 and level
Medium are the same, High months after the gate 29 / 29 / 27. The
practical threshold (p75) has been **checked** for sensitivity (part 2
in the notebook): the result is determined by it — sweeping the
quantile from p50 to p95 moves lifetime from 0.667 (High) down to 0.083
(Low), and the level takes all three values. This is a limitation of
the metric, not stability.

**Epochs vs points.** Epochs of high Variability and PELT points do not
overlap significantly: 4 of 7 with expected 2.5, `p = 0.22`. Layers
answer different questions — epochs about variability in a window,
points about breaks; overlap is not required.

**Current** is the last rolling-12 window, i.e. the last 12 months (not
18).

---

## Phase 8. Different nulls for different structures — Sound ≠ Behavior

The same permutation template does not transfer mechanically between
feature types. Checked on Behaviour: a single "month shuffle" yields a
null calibrated on the **whole-history** spread, not on the local noise
of a specific pair of months — systematically biased.

**Fix by feature structure.** Simple event-level aggregates (hours,
tracks, skip_rate, played_frac) — permutation at the event level, as in
Sound. `obsession_share`, which is a property of a **session**, not of
an event — permutation at the session level, otherwise shuffling
destroys the very structure being checked.

**Side finding.** `skip_rate` and `played_frac` correlate at
`r≈-0.9` — under a "at least N features confirm the shift" vote this
pair counted as two independent votes while being in fact one signal.
Cluster voting was introduced: features are grouped by meaning (volume /
completion / obsession), the vote is counted by clusters, not by raw
features. Behavior Variability is built on these 5 features;
`discovery_rate` is not part of it.

**Comparability with Sound.** Behavior lifetime 0.125 on full windows
(`min_periods=12`, as for Sound) and 0.167 on partial (`min_periods=4`);
Sound — 0.417. The High rule for Behaviour is stricter (≥2 clusters), so
the conclusion "behaviour changes less often than taste" is
preliminary.

---

## Phase 9. Detrend — removing phantom links

Long-running drifting series give inflated correlation simply through
shared direction of motion, with no real link between mechanisms.

**Check.** A linear trend was subtracted from each series (Variability,
Burnout, Discovery, Retention), correlations recomputed on residuals.

**The most important result of the whole path.** Sound Variability ↔
Burnout on raw series — `r=-0.55, p<0.0001`, the strongest link in the
whole project. After detrending — `r=-0.20, p=0.13` (n=58). At n=58 the
power of the test for an effect of this magnitude is about 30–35% — this
is **an unconfirmed link, not a refuted one**: the test is not powerful
enough to distinguish "no link" from "link present but weak". The word
"artifact" for this pair is too categorical; correctly — "the strong
anti-phase was not confirmed, a moderate link is not statistically
excluded".

Sound Variability ↔ Behavior Variability link: raw `r=-0.27` (p=0.039),
after detrending `r=+0.243, p=0.0665` (n=58). The sign flipped, but p is
at the boundary of the test's sensitivity, so the status is the same —
"not established", not "no link".

The only link that strengthened after detrending: Behavior Variability
↔ Burnout, raw `+0.42` → `-0.757`. Leave-one-out over the 10 High
months: r stays in the range −0.614…−0.842 (median −0.703), the sign
does not change. Not accounted for: correlations are computed on
rolling windows (rolling-12 and the yearly Burnout window), adjacent
points overlap, so the effective n is below 58 and p-values are
optimistic; multiple-testing correction across 10 pairs was not applied.

---

## Phase 10. Behavior Variability does not enter the compass

The behavioural version of Variability is computed with the same method
(phases 7–8) as the sound one, but architecturally not included in the
final compass.

**Two reasons.**

1. **Empirical (main).** After detrending Behavior Variability is linked
   to Burnout (`r=-0.757`, phase 9); a fifth axis would break the
   compass "orthogonality".
2. **Check for duplication of Discovery.** Behavior Variability must not
   repeat the Discovery axis. `discovery_rate` is not part of it (phase
   8 set: hours, tracks, skip_rate, played_frac, obsession_share).
   There is no link to Discovery either for this set (`r=-0.094,
   p=0.45`), or for the set with the semantically close `orphan_share`
   (`r=+0.138, p=0.27`).

Behavior Variability remains a research metric: it is valid, but it
does not enter the compass and is not exported to the dashboard.

---

## Phase 11. Generalization into a reusable tool

The logic of phases 6–8 is factored out into `VariabilityAnalyzer` — an
API not tied to Spotify: `period_col`, `value_cols`, an arbitrary
aggregation function, an arbitrary `n_boot`, explicit support for the
multivariate (Mahalanobis on the covariance of differences, not levels,
with Ledoit-Wolf shrinkage) and univariate cases.

**Central principle, documented explicitly: the exchange unit.**
Before running a permutation test, one must define what can be validly
shuffled without losing meaning. Event — for simple aggregates. Session
— for session properties (obsession). Nothing — for metrics that depend
on the whole history at once (discovery: "is it the first time ever" is
not tested by locally swapping two months). For cosine distance on
artist/genre composition (a high-cardinality categorical feature),
permutation-null was checked and rejected: on real data all 69 of 69
month pairs came out "significant" — the condition "no change" for such
a feature is statistically implausible in itself (the law of large
numbers guarantees a difference in composition between any two months),
also confirmed on synthetic data. What remains is MAD peak detection —
an outlier-finding task, not a significance check of a single pair.

**The `min_periods` parameter as a source of discrepancy.** Without an
explicit `min_periods`, the toolkit takes
`max(3, window // 3) = 4`: early points are computed on partial windows,
the median is biased upward. Checked: `min_periods=None` gives lifetime
= 0.500, `min_periods=12` gives 0.417; production passes 12 explicitly.
The value 0.423 from an early run is not reproducible in the notebook.

---

## Phase 12. ALL vs VALID — semantics determines the base

There is no single rule "always valid" or "always all" — the choice is
determined by what the metric measures, not by a wish for uniformity.

| Layer | ALL | VALID | Decision | Why |
|---|---|---|---|---|
| PELT-A (sound) | 3 points | 3 points | **ALL** | result unchanged; track sound does not depend on skip; ALL gives more data (σ² 0.420 vs 0.521); base matches PELT-B, Cosine and Storm |
| PELT-B (behaviour) | works | tautology | **ALL** | skip_rate≡0, played_frac≥0.5 on valid by definition |
| Cosine (identity) | 3 clusters | 1 cluster | **ALL** | on valid the MAD threshold is unstable due to artist-matrix sparsity at lower N; permutation-null is inapplicable to this feature in principle (phase 11) |
| Storm (turbulence) | 2 episodes | 3 episodes | **ALL** | on ALL 2 episodes vs 3 on VALID — more conservative; the base matches Cosine for convenience of comparison, but the choice is ALL, not Cosine |
| Variability (compass) | — | — | **VALID** | measures taste of consciously listened material |

The loss of Cosine signal on valid (3→1) was initially taken for a gap
in the threshold worth recalibrating — a permutation-null that was
supposed to fix it turned out to be inapplicable in principle to this
feature type (see phase 11). This is not "decided not to fix" — there
was nothing to fix, the method does not fit the task from the very
start.

---

## Final architecture

Four independent layers of points, not one universal detector:

- **PELT-A** (sound, all, BIC) — global shifts of average mood
- **PELT-B** (behaviour, all, BIC) — global shifts of behavioural patterns
- **Cosine** (identity, all, MAD peaks) — shifts in artist lineup
- **Storm** (all, rolling std + binomial test) — zones of elevated turbulence, not periods

Plus a separate compass axis **Sound Variability** (valid,
permutation-noise-floor + double gate, `VariabilityAnalyzer`) — not the
same as any of the four point detectors, but the aggregated share of
"statistically and practically significant" monthly shifts within a
window.

**The numerical value of Sound Variability** in the latest confirmed
cross-check between the manual computation and `VariabilityAnalyzer`
(`min_periods=12`, 5 seeds) matched at **0.417** (Medium); current (last
rolling-12 window) — **0.083** (Low). The value 0.500 is obtained with
`min_periods=None` (partial windows). Before putting the number into
the final documentation — cross-check with the current output of the
code.

---

## Appendix: comparison with the primitive detector (behavioural EDA)

The behavioural EDA notebook (`03_eda_behavioral` / in the new numbering
— the corresponding file in `01_data_analysis`) is deliberately left on
the primitive version: `pen=10`, 7 mixed features, no bootstrap, no
cold-start trimming. This is not a forgotten default — an explicit
architectural decision not to duplicate the methodology inside the
descriptive EDA (see the reasoning in the notebook itself).

Comparison of the primitive detector's points (7, scenario `cascade`)
with the final layers:

| Primitive PELT | Final layer | Status |
|---|---|---|
| 2021-07 | 2021-08 (PELT-B) | matches, ±1 month |
| 2022-05 | Cosine | did not survive bootstrap of the naive PELT (0.078), but found by Cosine (stability 0.825, production detector); independently confirmed by an artist shift (top-4 of 71) and an obsession spike (×4.8 of baseline) — both numbers from a separate run, not reproduced in the notebook |
| 2022-10 | — | not confirmed by any layer, by any independent check |
| 2023-08 | 2023-09 (PELT-A) | matches, ±1 month |
| 2024-06 | 2024-07 (PELT-A) | matches, ±1 month |
| 2024-11 | 2024-12 (PELT-B) | matches, ±1 month |
| 2025-09 | 2025-10 (PELT-B) | matches, ±1 month |
| — | 2021-02 (Cosine) | new, not found by the primitive detector |
| — | 2024-02 | new; the only point visible simultaneously in all three layers (sound, behaviour, identity) |
| — | 2026-03 (PELT-B) | new, not found by the primitive detector |

Of the 7 points of the primitive detector, **five match within ±1 month
against PELT-A or PELT-B**; one (2022-05) is confirmed **exactly**
through Cosine — a layer of a different nature (identity, not mood);
one (2022-10) is not confirmed by any layer. The final architecture adds
three points the primitive method did not see at all — two of them
(2021-02, 2026-03) do not pass through audio mood and are found only by
layers designed later.

`2024-11` is an example of the same principle as `2022-05`: the naive
PELT bootstrap rejected it (0.022), but PELT-B found `2024-12` on the
behavioural layer (stability 0.105). Bootstrap of one layer is not the
final instance — independent confirmation by another layer is stronger.

---

## Limitations relevant to the whole document

- All double-gate thresholds (99th percentile, at least 2 features, p75
  practical) are heuristics calibrated on this data, not derived from
  general theory; on another profile they may require recalibration.
  Sensitivity to the statistical threshold (p90/p95/p99) has been
  checked and is small; to the practical one — **checked and large**:
  the result is fully determined by the chosen quantile (p50 → p95:
  lifetime 0.667 High → 0.083 Low). The label is relative to the
  profile.
- The method is validated on N=1. The stability of the principles (not
  the specific numbers) to other profiles has not been checked.
- The orthogonality of compass axes after detrending is confirmed in the
  sense of "no strong link was found"; for links of magnitude
  r≈0.15–0.20 at n=58 the power of the test is insufficient to rule
  them out completely.
- Correlations of phase 9 are computed on overlapping rolling windows:
  the effective n is below 58, p-values are optimistic; multiple-testing
  correction was not applied.
- Permutation-null for categorical identity features (artists, genres)
  does not work in principle — an established fact of the method, not
  an open question for future work.