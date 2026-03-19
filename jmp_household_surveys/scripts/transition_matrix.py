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

A technology ladder table (mean tech fraction by HDI bin x context) captures
the overall trend of technology mix as development level changes.  HDI values
are assigned to 0.025-wide bins using half-open intervals [left, left+0.025),
labelled by their left edge.  This is equivalent to flooring to the nearest
0.025 and is the standard way to produce uniform histogram bins; the resulting
labels are used directly as x-nodes for piecewise-linear interpolation in the
projection step.

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


# -- Technology ladder (mean fraction per HDI bin x context) -----------------
print("Building technology ladder ...")

# Assign each observation to a 0.025-wide bin labelled by its left edge.
# HDI value h falls in bin floor(h / 0.025) x 0.025, i.e. [bin, bin+0.025).
BIN_WIDTH = 0.025
ladder_rows = df[df['hdi'].notna()].copy()
ladder_rows['hdi_bin'] = (ladder_rows['hdi'] / BIN_WIDTH).apply(np.floor) * BIN_WIDTH
ladder_rows['hdi_bin'] = ladder_rows['hdi_bin'].round(3)

ladder = (
    ladder_rows.groupby(['hdi_bin', 'context'])[TECH_COLS]
    .mean()
    .reset_index()
)

obs = (
    ladder_rows.groupby(['hdi_bin', 'context'])
    .size()
    .reset_index(name='n_observations')
)
ladder = ladder.merge(obs, on=['hdi_bin', 'context'])
ladder.sort_values(['context', 'hdi_bin'], inplace=True)

out_ladder = os.path.join(SCRIPTS_DIR, '../data/technology_ladder.csv')
ladder.to_csv(out_ladder, index=False)
print(f"  Saved -> {out_ladder}")


# -- Summary ------------------------------------------------------------------
print(f"\nConsecutive pairs used : {len(pairs)}")
print(f"Countries              : {pairs['alpha3'].nunique()}")

print(f"\nTop 10 technology transitions (annual %-points, from ladder):")
ladder_flows = build_flow_matrix(pairs)
flat = ladder_flows.stack().reset_index()
flat.columns = ['from_tech', 'to_tech', 'flow']
flat = flat[flat['from_tech'] != flat['to_tech']].sort_values('flow', ascending=False)
print(flat.head(10).to_string(index=False))
