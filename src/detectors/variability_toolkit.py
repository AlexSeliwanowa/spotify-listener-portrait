"""
variability_toolkit.py

A general, dataset-agnostic toolkit for measuring "variability" - how much a
multi-feature profile changes from period to period - using a PERMUTATION-BASED
NOISE FLOOR instead of an assumed distribution, plus a PRACTICAL-SIGNIFICANCE
GATE so that "statistically detectable" is not confused with "meaningful".

Core idea, in one sentence:
    Compare the observed change between two adjacent periods to the change you
    would expect from pure resampling noise, given the ACTUAL number of
    observations available in those periods - and only call a change "real"
    if it both survives that noise floor AND is large enough in raw units to
    matter.

--------------------------------------------------------------------------
THE ONE RULE THAT MATTERS MORE THAN ANY PARAMETER: the exchangeability unit
--------------------------------------------------------------------------
Every row of the dataframe you pass in must be the unit that would be
EXCHANGEABLE between two periods under the null hypothesis of "no real
change". Concretely:

  - For a simple per-event average (skip rate, mean loudness, mean price) -
    pass one row per event. Row-level permutation is valid.

  - For a property that only makes sense at a COARSER grain (e.g. "was this
    SESSION unusually repetitive", "did this CUSTOMER churn this quarter") -
    pre-aggregate your data to one row per session / customer / whatever the
    property actually belongs to, BEFORE calling this tool. Do not pass raw
    events for such features - permuting events will destroy the very
    structure the property depends on.

  - Metrics that depend on the ENTIRE history rather than just the two
    periods being compared (e.g. "is this the first time this item has ever
    appeared", "is this an all-time high") CANNOT be validly tested with
    local permutation at all. Exclude them from value_cols and analyze them
    with a different method.

Getting this wrong silently produces numbers that look fine and mean nothing.
There is no parameter in this module that can safely automate this decision
for you - it requires knowing what your data actually represents.

--------------------------------------------------------------------------
Typical usage
--------------------------------------------------------------------------

    analyzer = VariabilityAnalyzer(
        period_col='month',
        value_cols=['valence', 'energy', 'danceability'],
        agg='median',
    )
    analyzer.fit(events_df)                     # one row per event
    print(analyzer.transitions_)                # per-period-pair labels
    score = analyzer.variability_score(window=12)
    print(score['lifetime_level'], score['lifetime_score'])
    stability = analyzer.check_stability(window=12)
    print(stability['mean'], stability['ci_95'])

For a session-scoped (or any coarser-unit) feature, pre-aggregate first:

    session_df = build_one_row_per_session(events_df)   # your own code
    analyzer2 = VariabilityAnalyzer(period_col='month', value_cols=['is_obsession_episode'])
    analyzer2.fit(session_df)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Sequence, Dict, Any

try:
    from sklearn.covariance import LedoitWolf
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


@dataclass
class VariabilityScore:
    lifetime_score: float
    lifetime_level: str
    current_score: float
    current_level: str
    null_low: float
    null_high: float
    rolling_series: pd.Series


class VariabilityAnalyzer:
    """
    Measures period-to-period variability of a (possibly multi-feature)
    profile using permutation nulls and a practical-significance gate.

    Parameters
    ----------
    period_col : str
        Column identifying the period (e.g. month, week, sprint number).
    value_cols : sequence of str
        Columns to track. If more than one, a Mahalanobis distance (using the
        covariance of period-to-period DIFFERENCES, not of levels - see
        module docstring in the analysis this was built from) is used so
        that correlated joint movement counts less than a movement that
        breaks the usual correlation structure. If exactly one, a plain
        absolute difference is used.
    agg : {'median', 'mean'}
        How to aggregate value_cols within a period. Median is more robust
        to outliers; mean is appropriate for rates/proportions computed as
        an average over many events (e.g. skip rate).
    n_boot : int
        Number of permutation draws used to build the noise floor for each
        period-to-period transition. 200 is a reasonable default; raise it
        if your min_obs_per_period is small and you see unstable percentiles.
    p_low, p_high : float
        Percentiles of the permutation null used to separate Low / Medium /
        High. Defaults (75, 99) mirror a loose/strict significance split;
        adjust to taste, but note this affects downstream calibration.
    min_obs_per_period : int
        Periods with fewer observations than this are skipped entirely
        (too few to build a meaningful permutation null). Do not lower this
        much below 5.
    practical_thresholds : dict or None
        Per-column absolute-difference thresholds below which a change is
        never labeled Medium/High regardless of statistical significance,
        even if every observation clears the noise floor. If None, each
        column's threshold is auto-calibrated as the MEDIAN of that column's
        own raw (non-normalized) period-to-period absolute differences
        across the whole series - a data-grounded default, not a universal
        constant. Override this if you have a domain-meaningful minimum
        (e.g. "less than $50 doesn't matter for this business metric").
    min_practical_features : int
        How many of value_cols must individually clear their practical
        threshold for a transition to be allowed to count as Medium/High.
        Default 1. Raise this if you have many correlated features and want
        to require convergent evidence (see the module's parent analysis for
        why 2 nearly-identical features can otherwise look like double
        confirmation).
    random_state : int
        Seed for reproducibility.
    """

    def __init__(
        self,
        period_col: str,
        value_cols: Sequence[str],
        agg: str = "median",
        n_boot: int = 200,
        p_low: float = 75,
        p_high: float = 99,
        min_obs_per_period: int = 5,
        practical_thresholds: Optional[Dict[str, float]] = None,
        min_practical_features: int = 1,
        random_state: int = 42,
    ):
        self.period_col = period_col
        self.value_cols = list(value_cols)
        self.agg = agg
        self.n_boot = n_boot
        self.p_low = p_low
        self.p_high = p_high
        self.min_obs_per_period = min_obs_per_period
        self.practical_thresholds = practical_thresholds
        self.min_practical_features = min_practical_features
        self.random_state = random_state

        if agg not in ("median", "mean"):
            raise ValueError("agg must be 'median' or 'mean'")
        if len(self.value_cols) > 1 and not _HAS_SKLEARN:
            raise ImportError(
                "Multi-feature mode needs scikit-learn (for LedoitWolf covariance "
                "shrinkage). Install it, or use a single value_col."
            )

        self.transitions_: Optional[pd.DataFrame] = None
        self._Sigma_inv = None
        self._level_mean = None
        self._level_std = None
        self.practical_thresholds_: Dict[str, float] = {}

    # ------------------------------------------------------------------
    def _aggregate(self, obs_df: pd.DataFrame) -> pd.Series:
        fn = "median" if self.agg == "median" else "mean"
        return obs_df[self.value_cols].agg(fn)

    def _distance(self, agg_a: pd.Series, agg_b: pd.Series) -> float:
        if self._Sigma_inv is not None:
            za = (agg_a - self._level_mean) / self._level_std
            zb = (agg_b - self._level_mean) / self._level_std
            d = (zb - za).values.astype(float)
            return float(np.sqrt(max(d @ self._Sigma_inv @ d, 0.0)))
        else:
            col = self.value_cols[0]
            return float(abs(agg_b[col] - agg_a[col]))

    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "VariabilityAnalyzer":
        """
        Compute per-transition labels for every pair of adjacent periods.

        `df` must have one row per exchangeable unit - see the module
        docstring's "exchangeability unit" section before calling this.
        """
        missing = [c for c in [self.period_col] + self.value_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Columns not found in df: {missing}")

        df = df.copy()
        periods = sorted(df[self.period_col].unique())
        if len(periods) < 3:
            raise ValueError("Need at least 3 periods to compute any transitions.")

        # Per-period aggregates - used for covariance-of-differences and for
        # auto-calibrating practical thresholds.
        period_aggs = df.groupby(self.period_col)[self.value_cols].agg(self.agg)
        period_aggs = period_aggs.reindex(periods)
        raw_diffs = period_aggs.diff().dropna()

        if self.practical_thresholds is None:
            self.practical_thresholds_ = raw_diffs.abs().median().to_dict()
        else:
            self.practical_thresholds_ = dict(self.practical_thresholds)

        n_features = len(self.value_cols)
        if n_features > 1:
            mean = period_aggs.mean()
            std = period_aggs.std().replace(0, 1)
            self._level_mean, self._level_std = mean, std
            z_diffs = ((period_aggs - mean) / std).diff().dropna()
            cov = LedoitWolf().fit(z_diffs.values).covariance_
            self._Sigma_inv = np.linalg.pinv(cov)
            # Index as str to match transitions_.index (period_to is stringified there) -
            # a prior version left this as the raw period dtype and silently failed lookups.
            self._z_diffs_ = z_diffs.set_axis([str(p) for p in z_diffs.index])
        else:
            self._level_mean = None
            self._level_std = None
            self._Sigma_inv = None
            self._z_diffs_ = None

        rng = np.random.default_rng(self.random_state)
        rows = []
        for i in range(len(periods) - 1):
            p_from, p_to = periods[i], periods[i + 1]
            obs_from = df[df[self.period_col] == p_from]
            obs_to = df[df[self.period_col] == p_to]
            n_from, n_to = len(obs_from), len(obs_to)
            if n_from < self.min_obs_per_period or n_to < self.min_obs_per_period:
                continue

            agg_from, agg_to = self._aggregate(obs_from), self._aggregate(obs_to)
            observed = self._distance(agg_from, agg_to)

            pooled = pd.concat([obs_from, obs_to], ignore_index=True)
            null_dists = np.empty(self.n_boot)
            for b in range(self.n_boot):
                perm = rng.permutation(len(pooled))
                a = pooled.iloc[perm[:n_from]]
                c = pooled.iloc[perm[n_from : n_from + n_to]]
                null_dists[b] = self._distance(self._aggregate(a), self._aggregate(c))

            thr_low, thr_high = np.percentile(null_dists, [self.p_low, self.p_high])
            excess = observed / (np.median(null_dists) + 1e-12)

            if observed <= thr_low:
                stat_label = "Low"
            elif observed <= thr_high:
                stat_label = "Medium"
            else:
                stat_label = "High"

            raw_diff = (agg_to - agg_from).abs()
            n_practical = int(
                sum(raw_diff[c] >= self.practical_thresholds_.get(c, 0.0) for c in self.value_cols)
            )
            practical_ok = n_practical >= self.min_practical_features

            final_label = stat_label if (stat_label in ("Medium", "High") and practical_ok) else "Low"

            rows.append(
                dict(
                    period_from=str(p_from),
                    period_to=str(p_to),
                    n_from=n_from,
                    n_to=n_to,
                    observed=observed,
                    null_p_low=thr_low,
                    null_p_high=thr_high,
                    excess_ratio=excess,
                    statistical_label=stat_label,
                    n_practical_features=n_practical,
                    practical_ok=practical_ok,
                    label=final_label,
                )
            )

        if not rows:
            raise ValueError(
                "No transitions survived min_obs_per_period - lower it, or check your data."
            )

        self.transitions_ = pd.DataFrame(rows).set_index("period_to")
        return self

    # ------------------------------------------------------------------
    def variability_score(
        self,
        window: int = 12,
        n_boot: int = 500,
        min_periods: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate per-transition labels into a single Variability score.
        min_periods: if None, falls back to max(3, window // 3).
        """
        if self.transitions_ is None:
            raise RuntimeError("Call .fit() first.")

        labels = (self.transitions_["label"] == "High").astype(int).values

        if min_periods is None:
            min_periods = max(3, window // 3)

        rolling = pd.Series(labels, index=self.transitions_.index).rolling(
            window, min_periods=min_periods
        ).mean()

        current_score = rolling.iloc[-1] if rolling.notna().any() else float("nan")
        lifetime_score = rolling.median()

        rng = np.random.default_rng(self.random_state)
        null_scores = np.empty(n_boot)
        for b in range(n_boot):
            shuffled = rng.permutation(labels)
            null_scores[b] = (
                pd.Series(shuffled)
                .rolling(window, min_periods=min_periods)
                .mean()
                .median()
            )
        null_low, null_high = np.percentile(null_scores, [5, 95])

        def level_of(score):
            if np.isnan(score):
                return "Unknown"
            if score < null_low:
                return "Low"
            if score > null_high:
                return "High"
            return "Medium"

        return dict(
            lifetime_score=lifetime_score,
            lifetime_level=level_of(lifetime_score),
            current_score=current_score,
            current_level=level_of(current_score),
            null_low=null_low,
            null_high=null_high,
            rolling_series=rolling,
        )


    # ------------------------------------------------------------------
    def check_stability(
        self, window: int = 12, n_bootstrap: int = 100, drop_frac: float = 0.15
    ) -> Dict[str, Any]:
        """
        Subsample transitions (dropping `drop_frac` of them, preserving
        order) and recompute the lifetime Variability score each time.
        A tight distribution here means the level is not an artifact of a
        handful of specific periods.
        """
        if self.transitions_ is None:
            raise RuntimeError("Call .fit() first.")

        labels_full = (self.transitions_["label"] == "High").astype(int)
        n = len(labels_full)
        n_keep = max(int(round(n * (1 - drop_frac))), window)
        min_periods = max(3, window // 3)
        rng = np.random.default_rng(self.random_state)

        results = []
        for _ in range(n_bootstrap):
            keep_idx = np.sort(rng.choice(n, n_keep, replace=False))
            sub = labels_full.iloc[keep_idx].reset_index(drop=True)
            results.append(sub.rolling(window, min_periods=min_periods).mean().median())

        results = np.array(results)
        return dict(
            mean=float(np.nanmean(results)),
            std=float(np.nanstd(results)),
            ci_95=(float(np.nanpercentile(results, 2.5)), float(np.nanpercentile(results, 97.5))),
            values=results,
        )

    # ------------------------------------------------------------------
    def feature_contributions(self, period_to: str) -> pd.Series:
        """
        For a given transition (identified by its `period_to` label, as it
        appears in `transitions_.index`), decompose how much each feature
        contributed to the joint distance. Only meaningful in multi-feature
        mode. Returns a Series indexed by value_cols; larger = contributed
        more to that month being flagged.
        """
        if self._Sigma_inv is None:
            raise RuntimeError("feature_contributions needs >1 value_cols (Mahalanobis mode).")
        if period_to not in self.transitions_.index:
            raise KeyError(f"{period_to!r} not found in transitions_.index")
        if period_to not in self._z_diffs_.index:
            raise KeyError(
                f"{period_to!r} has no cached z-diff (it may have been skipped by "
                f"min_obs_per_period during fit)."
            )
        d = self._z_diffs_.loc[period_to].values.astype(float)
        # Per-feature contribution to the squared Mahalanobis distance:
        # d^T Sigma_inv d = sum_i d_i * (Sigma_inv @ d)_i - decompose term-by-term.
        contrib = d * (self._Sigma_inv @ d)
        return pd.Series(contrib, index=self.value_cols).sort_values(ascending=False)
