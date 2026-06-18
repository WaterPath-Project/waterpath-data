"""
transition_matrix.py -- Compute annual sanitation technology transition matrices
and the technology ladder from the longitudinal sanitation_hdi_history.csv
produced by analyze.py.

Method
------
For each consecutive survey pair per (country, context) we compute the annual
rate of change for each technology fraction.  Over any transition:
  * technologies whose share decreases -- "donors"
  * technologies whose share increases -- "recipients"

We attribute each donor's annual loss proportionally across all recipients,
producing a [tech x tech] flow matrix for that transition.  Flows are then
averaged across all transitions.

A technology ladder table (tech fraction by HDI bin x context) captures the
overall trend of technology mix as development level changes.  It is built
LONGITUDINALLY -- from within-country transitions -- rather than as a
cross-sectional average of country snapshots, so that it represents the ascent
trajectory countries actually follow as they develop and does not imply that a
country whose HDI falls reverts to the mix of poorer countries (see the ladder
section below).  HDI values are assigned to 0.025-wide bins using half-open
intervals [left, left+0.025), labelled by their left edge.  This is equivalent
to flooring to the nearest 0.025 and is the standard way to produce uniform
histogram bins; the resulting labels are used directly as x-nodes for
piecewise-linear interpolation in the projection step.

Outputs (written to ../data/)
-------------------------------
  technology_ladder.csv           -- mean tech fraction by HDI bin x context

(transition_matrix_overall.csv was previously produced here but is not consumed
by any downstream script.  It has been moved to ../data/archive/.)
"""

import os
import numpy as np
import pandas as pd

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

TECH_COLS = [
    'flushSewer', 'flushSeptic', 'flushPit', 'flushUnknown', 'flushOpen',
    'pitSlab', 'pitNoSlab', 'hangingToilet', 'bucketLatrine',
    'compostingToilet', 'openDefecation', 'other',
]

# -- Load longitudinal dataset ------------------------------------------------
in_path = os.path.join(SCRIPTS_DIR, '../data/sanitation_hdi_history.csv')
df = pd.read_csv(in_path)

# -- Identify consecutive survey pairs per (country, context) ----------------
# When multiple surveys exist in the same year, take the mean across them first
df_yr = (
    df.groupby(['alpha3', 'context', 'year'])[TECH_COLS + ['hdi']]
    .mean()
    .reset_index()
)
df_yr.sort_values(['alpha3', 'context', 'year'], inplace=True)

# Shift to build (t, t+1) pairs
g = df_yr.groupby(['alpha3', 'context'])
shifted = df_yr.copy()
shifted['year_next'] = g['year'].shift(-1)
shifted['hdi_next']  = g['hdi'].shift(-1)
for col in TECH_COLS:
    shifted[f'{col}_next'] = g[col].shift(-1)

pairs = shifted.dropna(subset=['year_next']).copy()
pairs['dt'] = pairs['year_next'] - pairs['year']
pairs = pairs[(pairs['dt'] > 0) & (pairs['dt'] <= 15)]


# -- Core: build a [tech x tech] flow matrix from a set of pairs -------------
def build_flow_matrix(pairs_subset):
    """
    For each pair: compute annual gains/losses per technology bucket,
    then distribute each donor's loss to recipients proportional to their gain.
    Returns a DataFrame with from_tech as index, to_tech as columns.
    """
    all_flows = {(f, t): [] for f in TECH_COLS for t in TECH_COLS}

    for _, row in pairs_subset.iterrows():
        dt = row['dt']
        gains, losses = {}, {}
        for col in TECH_COLS:
            delta = (row[f'{col}_next'] - row[col]) / dt
            if delta > 1e-6:
                gains[col] = delta
            elif delta < -1e-6:
                losses[col] = -delta

        total_gain = sum(gains.values())
        total_loss = sum(losses.values())
        if total_gain < 1e-8 or total_loss < 1e-8:
            continue

        for donor, loss in losses.items():
            for recipient, gain in gains.items():
                all_flows[(donor, recipient)].append(loss * (gain / total_gain))

    matrix = pd.DataFrame(0.0, index=TECH_COLS, columns=TECH_COLS)
    for (f, t), vals in all_flows.items():
        if vals:
            matrix.loc[f, t] = float(np.mean(vals))
    return matrix


# -- Technology ladder (longitudinal) ----------------------------------------
# The ladder is built from WITHIN-COUNTRY transitions rather than a
# cross-sectional average of snapshots.  Cross-sectional means assume that the
# pattern observed across different countries at a given HDI is a reasonable
# trajectory for a single country over time -- and, read in reverse, that a
# country whose HDI falls would revert to the mix typical of poorer countries
# (e.g. open defecation resurfacing).  That symmetry is not supported by the
# data: the pooled sample is dominated by countries *rising* through each HDI
# level, and sanitation infrastructure/behaviour is sticky.
#
# Instead we:
#   1.  Take consecutive within-country survey pairs (already in `pairs`) and
#       keep only *upward* HDI movements (development trajectories).
#   2.  Per HDI bin x context, estimate the empirical slope of each technology
#       fraction w.r.t. HDI as  slope_t = sum(d_frac_t) / sum(d_hdi)  -- a
#       weighted ratio that is robust to tiny HDI changes (a pair with a small
#       d_hdi contributes little to both numerator and denominator).
#   3.  Anchor each context at its highest, densest cross-sectional bin (the
#       high-HDI range has 80-142 observations per bin and is stable) and
#       integrate the slopes downward to recover absolute levels, clipping to
#       [0, 1] and renormalising each bin to sum to 1.
#
# The resulting ladder encodes the *ascent* trajectory that countries actually
# follow as they develop, which is what the projection step extrapolates.
print("Building technology ladder (longitudinal) ...")

# Assign each observation to a 0.025-wide bin labelled by its left edge.
# HDI value h falls in bin floor(h / 0.025) x 0.025, i.e. [bin, bin+0.025).
BIN_WIDTH = 0.025
MIN_DHDI = 0.005  # ignore pairs with negligible HDI movement

# Cross-sectional means and per-bin observation counts -- used only as anchors
# and for the n_observations column (kept for transparency / continuity).
xsec_rows = df[df['hdi'].notna()].copy()
xsec_rows['hdi_bin'] = (xsec_rows['hdi'] / BIN_WIDTH).apply(np.floor) * BIN_WIDTH
xsec_rows['hdi_bin'] = xsec_rows['hdi_bin'].round(3)
xsec_mean = (
    xsec_rows.groupby(['hdi_bin', 'context'])[TECH_COLS].mean().reset_index()
)
xsec_obs = (
    xsec_rows.groupby(['hdi_bin', 'context']).size()
    .reset_index(name='n_observations')
)
xsec = xsec_mean.merge(xsec_obs, on=['hdi_bin', 'context'])

# Per-bin longitudinal slopes from upward within-country transitions.
lp = pairs.dropna(subset=['hdi', 'hdi_next']).copy()
lp['dhdi'] = lp['hdi_next'] - lp['hdi']
lp = lp[lp['dhdi'] > MIN_DHDI]
lp['mid_hdi'] = 0.5 * (lp['hdi'] + lp['hdi_next'])
lp['hdi_bin'] = (lp['mid_hdi'] / BIN_WIDTH).apply(np.floor) * BIN_WIDTH
lp['hdi_bin'] = lp['hdi_bin'].round(3)
for col in TECH_COLS:
    lp[f'{col}_d'] = lp[f'{col}_next'] - lp[col]

slope_records = []
for (b, ctx), grp in lp.groupby(['hdi_bin', 'context']):
    denom = grp['dhdi'].sum()
    if denom <= 0:
        continue
    rec = {'hdi_bin': b, 'context': ctx}
    for col in TECH_COLS:
        rec[col] = grp[f'{col}_d'].sum() / denom
    slope_records.append(rec)
slopes = pd.DataFrame(slope_records)

# Integrate slopes downward from the high-HDI cross-sectional anchor.
ladder_out = []
for ctx in ('Urban', 'Rural'):
    xs = xsec[xsec['context'] == ctx].sort_values('hdi_bin').reset_index(drop=True)
    if xs.empty:
        continue
    bins = xs['hdi_bin'].tolist()
    sl = (slopes[slopes['context'] == ctx]
          .set_index('hdi_bin')[TECH_COLS] if not slopes.empty else pd.DataFrame())

    levels = {}
    top = bins[-1]
    levels[top] = xs.set_index('hdi_bin').loc[top, TECH_COLS].to_numpy(dtype=float)

    for i in range(len(bins) - 2, -1, -1):
        b, b_next = bins[i], bins[i + 1]
        # Slope for the step b_next -> b: mean of the two adjacent bins'
        # slopes where available, else fall back to whichever exists, else 0.
        svals = [sl.loc[bb].to_numpy(dtype=float)
                 for bb in (b, b_next) if bb in sl.index]
        step_slope = (np.mean(svals, axis=0) if svals
                      else np.zeros(len(TECH_COLS)))
        dh = b_next - b
        lvl = np.clip(levels[b_next] - step_slope * dh, 0.0, 1.0)
        s = lvl.sum()
        levels[b] = lvl / s if s > 0 else levels[b_next].copy()

    # Renormalise the anchor too, for consistency.
    a = levels[top]
    sa = a.sum()
    levels[top] = a / sa if sa > 0 else a

    n_obs = xs.set_index('hdi_bin')['n_observations']
    for b in bins:
        rec = {'hdi_bin': b, 'context': ctx}
        rec.update(dict(zip(TECH_COLS, levels[b])))
        rec['n_observations'] = int(n_obs.loc[b])
        ladder_out.append(rec)

ladder = pd.DataFrame(ladder_out, columns=['hdi_bin', 'context', *TECH_COLS, 'n_observations'])
ladder.sort_values(['context', 'hdi_bin'], inplace=True)

out_ladder = os.path.join(SCRIPTS_DIR, '../data/technology_ladder.csv')
ladder.to_csv(out_ladder, index=False)
print(f"  Saved -> {out_ladder}")
print(f"  Longitudinal pairs (upward, d_hdi > {MIN_DHDI}): {len(lp)}")


# -- Summary ------------------------------------------------------------------
print(f"\nConsecutive pairs used : {len(pairs)}")
print(f"Countries              : {pairs['alpha3'].nunique()}")

print(f"\nTop 10 technology transitions (annual %-points, from ladder):")
ladder_flows = build_flow_matrix(pairs)
flat = ladder_flows.stack().reset_index()
flat.columns = ['from_tech', 'to_tech', 'flow']
flat = flat[flat['from_tech'] != flat['to_tech']].sort_values('flow', ascending=False)
print(flat.head(10).to_string(index=False))
