"""
transition_matrix.py â€” Compute annual sanitation technology transition matrices
from the longitudinal sanitation_hdi_history.csv produced by analyze.py.

Method
------
For each consecutive survey pair per (country, context) we compute the annual
rate of change for each technology fraction.  Over any transition:
  * technologies whose share decreases â†’ "donors"
  * technologies whose share increases â†’ "recipients"

We attribute each donor's annual loss proportionally across all recipients,
producing a [tech Ã— tech] flow matrix for that transition.  Flows are then
averaged across all transitions.

HDI classification uses the standard UNDP fixed tiers:
  Very High : HDI â‰¥ 0.800
  High      : 0.700 â‰¤ HDI < 0.800
  Medium    : 0.550 â‰¤ HDI < 0.700
  Low       : HDI < 0.550

Transition matrices are produced per (starting HDI tier â†’ ending HDI tier),
so the outer index captures whether a country was staying in its tier,
climbing, or declining while the sanitation change occurred.

A technology ladder table (mean tech fraction by HDI bin Ã— context) captures
the overall trend of technology mix as development level changes.  HDI values
are assigned to 0.025-wide bins using half-open intervals [left, left+0.025),
labelled by their left edge.  This is equivalent to flooring to the nearest
0.025 and is the standard way to produce uniform histogram bins; the resulting
labels are used directly as x-nodes for piecewise-linear interpolation in the
projection step.

A technology threshold table records the HDI levels at which each technology
crosses key fraction thresholds (e.g. when openDefecation drops below 5%, 1%)
and conversely when modern technologies emerge above 25%, 50%.

Outputs (written to ../data/)
-------------------------------
  transition_matrix_overall.csv        â€” average annual flow matrix (all data)
  transition_matrix_hdi_tiers.csv      â€” stacked; one block per
                                         (from_hdi_tier â†’ to_hdi_tier) pair
  technology_ladder.csv                â€” mean tech fraction by HDI bin Ã— context
  technology_thresholds.csv            â€” HDI level at which each technology
                                         crosses key fraction thresholds
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

# â”€â”€ UNDP fixed HDI tiers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HDI_TIERS = [
    ('Low',       0.000, 0.550),
    ('Medium',    0.550, 0.700),
    ('High',      0.700, 0.800),
    ('Very High', 0.800, 1.001),
]
TIER_ORDER = ['Low', 'Medium', 'High', 'Very High']

def hdi_tier(hdi_val):
    if pd.isna(hdi_val):
        return None
    for label, lo, hi in HDI_TIERS:
        if lo <= hdi_val < hi:
            return label
    return None


# â”€â”€ Load longitudinal dataset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
in_path = os.path.join(SCRIPTS_DIR, '../data/sanitation_hdi_history.csv')
df = pd.read_csv(in_path)

# â”€â”€ Identify consecutive survey pairs per (country, context) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# Assign HDI tiers to both ends of each transition
pairs['tier_start'] = pairs['hdi'].apply(hdi_tier)
pairs['tier_end']   = pairs['hdi_next'].apply(hdi_tier)


# â”€â”€ Core: build a [tech Ã— tech] flow matrix from a set of pairs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€ 1. Overall matrix â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Building overall transition matrix â€¦")
overall_matrix = build_flow_matrix(pairs)
overall_matrix.index.name = 'from_tech'

out_overall = os.path.join(SCRIPTS_DIR, '../data/transition_matrix_overall.csv')
overall_matrix.to_csv(out_overall)
print(f"  Saved â†’ {out_overall}")


# â”€â”€ 2. Matrix per (starting HDI tier â†’ ending HDI tier) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Building HDI-tier transition matrices â€¦")

tier_blocks = []
for tier_from in TIER_ORDER:
    for tier_to in TIER_ORDER:
        sub = pairs[
            (pairs['tier_start'] == tier_from) &
            (pairs['tier_end']   == tier_to)
        ]
        n = len(sub)
        if n < 5:          # too few observations â€” skip
            continue
        direction  = (
            'same tier'  if tier_from == tier_to else
            'improving'  if TIER_ORDER.index(tier_to) > TIER_ORDER.index(tier_from) else
            'declining'
        )
        mat = build_flow_matrix(sub)
        mat.index.name = 'from_tech'
        mat = mat.reset_index()
        mat.insert(0, 'n_pairs',        n)
        mat.insert(0, 'direction',      direction)
        mat.insert(0, 'hdi_tier_end',   tier_to)
        mat.insert(0, 'hdi_tier_start', tier_from)
        tier_blocks.append(mat)
        print(f"  {tier_from:10s} â†’ {tier_to:10s}  ({n:4d} pairs, {direction})")

tier_df = pd.concat(tier_blocks, ignore_index=True)
out_tiers = os.path.join(SCRIPTS_DIR, '../data/transition_matrix_hdi_tiers.csv')
tier_df.to_csv(out_tiers, index=False)
print(f"  Saved â†’ {out_tiers}")


# â”€â”€ 3. Technology ladder (mean fraction per HDI bin Ã— context) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Building technology ladder â€¦")

# Assign each observation to a 0.025-wide bin labelled by its left edge.
# HDI value h falls in bin floor(h / 0.025) Ã— 0.025 âˆˆ [bin, bin+0.025).
# This produces uniform, unambiguous intervals and the left-edge label is used
# directly as the x-node in piecewise-linear interpolation downstream.
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
print(f"  Saved â†’ {out_ladder}")


# â”€â”€ 4. Technology thresholds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# For each technology, find the HDI level at which it crosses key
# fraction thresholds.  Uses linear interpolation on the ladder.
# "phase-out" thresholds: fraction falls below 10%, 5%, 2%, 1%
# "emergence" thresholds: fraction rises above 10%, 25%, 50%
print("Building technology thresholds â€¦")

def find_crossing_hdi(hdi_nodes, fractions, threshold, direction='below'):
    """
    Return the HDI value at which `fractions` first crosses `threshold`.
    direction='below'  â†’ fraction descends through threshold (phase-out)
    direction='above'  â†’ fraction ascends through threshold (emergence)
    Returns NaN if no crossing is found.
    """
    hdi_nodes = np.array(hdi_nodes)
    fractions = np.array(fractions)
    for i in range(len(fractions) - 1):
        f0, f1 = fractions[i], fractions[i + 1]
        h0, h1 = hdi_nodes[i], hdi_nodes[i + 1]
        if direction == 'below' and f0 >= threshold > f1:
            # linear interpolation
            t = (threshold - f0) / (f1 - f0)
            return round(h0 + t * (h1 - h0), 3)
        if direction == 'above' and f0 <= threshold < f1:
            t = (threshold - f0) / (f1 - f0)
            return round(h0 + t * (h1 - h0), 3)
    return np.nan

threshold_rows = []
for ctx in ('Urban', 'Rural'):
    sub = ladder[ladder['context'] == ctx].sort_values('hdi_bin')
    hdi_nodes = sub['hdi_bin'].to_numpy(dtype=float)
    for tech in TECH_COLS:
        fracs = sub[tech].to_numpy(dtype=float)
        # Phase-out thresholds (fraction declining through threshold)
        for thresh in [0.10, 0.05, 0.02, 0.01]:
            hdi_cross = find_crossing_hdi(hdi_nodes, fracs, thresh, 'below')
            threshold_rows.append({
                'context': ctx, 'technology': tech,
                'direction': 'phase_out',
                'threshold': thresh,
                'hdi_crossing': hdi_cross,
            })
        # Emergence thresholds (fraction rising through threshold)
        for thresh in [0.10, 0.25, 0.50]:
            hdi_cross = find_crossing_hdi(hdi_nodes, fracs, thresh, 'above')
            threshold_rows.append({
                'context': ctx, 'technology': tech,
                'direction': 'emergence',
                'threshold': thresh,
                'hdi_crossing': hdi_cross,
            })

thresholds_df = pd.DataFrame(threshold_rows)
# Drop rows where the crossing never happens
thresholds_df = thresholds_df.dropna(subset=['hdi_crossing'])
thresholds_df.sort_values(['context', 'direction', 'threshold', 'technology'], inplace=True)

out_thresh = os.path.join(SCRIPTS_DIR, '../data/technology_thresholds.csv')
thresholds_df.to_csv(out_thresh, index=False)
print(f"  Saved â†’ {out_thresh}")


# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print(f"\nConsecutive pairs used : {len(pairs)}")
print(f"  â€” with both HDI tiers: {pairs.dropna(subset=['tier_start','tier_end']).shape[0]}")
print(f"Countries              : {pairs['alpha3'].nunique()}")

print(f"\nTop 10 overall flows (annual %-points):")
flat = overall_matrix.stack().reset_index()
flat.columns = ['from_tech', 'to_tech', 'flow']
flat = flat[flat['from_tech'] != flat['to_tech']].sort_values('flow', ascending=False)
print(flat.head(10).to_string(index=False))

print(f"\nHDI tier breakdown (n pairs per transition type):")
summary = tier_df.groupby(['hdi_tier_start', 'hdi_tier_end', 'direction'])['n_pairs'].first().reset_index()
print(summary.to_string(index=False))

print(f"\nKey phase-out thresholds (Urban):")
urban_thresh = thresholds_df[
    (thresholds_df['context'] == 'Urban') &
    (thresholds_df['direction'] == 'phase_out') &
    (thresholds_df['threshold'] == 0.05)
].sort_values('hdi_crossing')[['technology', 'threshold', 'hdi_crossing']]
print(urban_thresh.to_string(index=False))

print(f"\nflushSewer emergence (Urban):")
sewer_emerg = thresholds_df[
    (thresholds_df['context'] == 'Urban') &
    (thresholds_df['technology'] == 'flushSewer') &
    (thresholds_df['direction'] == 'emergence')
][['technology', 'threshold', 'hdi_crossing']]
print(sewer_emerg.to_string(index=False))

