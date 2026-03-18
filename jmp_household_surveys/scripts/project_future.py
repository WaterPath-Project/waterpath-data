"""
project_future.py — Project sanitation technology mixes for SSP scenarios.

Projection method (delta-based)
---------------------------------
Absolute ladder lookup (HDI → fraction) is only reliable when the future
HDI value is close to the range where actual surveys were conducted for that
country.  Because hdi_future.csv was built partly from regional averages, the
2025 value can differ substantially from the most recent measured HDI.

Instead we use a *delta* approach anchored to the known current state:

  1. current_hdi  = most recent measured HDI per country
                    (from hdr-historical-data.xlsx)
  2. delta_hdi    = hdi_future[target_year] − hdi_future[2025]
                    (the SSP-scenario change from 2025 to target year;
                     this preserves the relative dynamics across scenarios
                     while avoiding the absolute-level discrepancy)
  3. target_hdi   = current_hdi + delta_hdi
  4. projected fraction = actual_current
                        + ( ladder(target_hdi) − ladder(current_hdi) )
  5. Clamp each fraction to [0, 1], then renormalise to sum = 1.

For 2025 the delta is zero, so the output equals the actual
sanitation_combined.csv values directly — no projection is applied.

For countries not in sanitation_combined.csv the absolute ladder value at
hdi_future[2025] is used (no delta baseline available).

Treatment parameters (coverBury, sewageTreated, fecalSludgeTreated,
isWatertight, hasLeach) and fixed model parameters (onsiteDumpedland,
emptyFrequency, pitAdditive, urine, twinPits) are carried forward unchanged
from sanitation_combined.csv — they are not driven by the HDI ladder.

Rounding
---------
Technology fractions are rounded to 3 significant decimal places (0.001) using
the largest-remainder (Hamilton) method so that every row sums to exactly 1.000.

Outputs (written to ../data/)
-------------------------------
  sanitation_combined_future.csv   — projected mix, 247 countries × 5 SSPs × 4 years
  technology_elimination.csv       — estimated calendar year a country/scenario
                                     crosses each technology phase-out threshold
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

# Parameters copied from current sanitation_combined.csv (not ladder-driven)
FIXED_SCALAR_PARAMS = ['onsiteDumpedland', 'emptyFrequency', 'pitAdditive', 'urine', 'twinPits']
TREATMENT_PARAMS    = ['coverBury', 'fecalSludgeTreated', 'sewageTreated', 'isWatertight', 'hasLeach']
PASSTHROUGH_PARAMS  = FIXED_SCALAR_PARAMS + TREATMENT_PARAMS + ['containerBased']

PROJ_YEARS = [2025, 2030, 2050, 2100]


# ── Rounding helper ────────────────────────────────────────────────────────────
def round_fracs_3dp_sum1(values):
    """
    Round an array of fractions to 3 decimal places while preserving sum = 1.
    Uses the largest-remainder (Hamilton) method:
      1. Normalise so the input sums to exactly 1 (handles tiny over/under-sums
         that arise from 3-dp CSV sources or floating-point accumulation).
      2. Floor each value to 3 dp.
      3. Count the integer number of 0.001 units still needed to reach 1.000.
      4. Add one 0.001 unit to the entries with the largest fractional remainders.
    """
    values = np.array(values, dtype=float)
    total = values.sum()
    if total > 0:
        values = values / total   # normalise away any tiny over/under-sum
    floored = np.floor(np.round(values * 1000, 8)) / 1000   # avoid float jitter
    n_add = int(round((1.0 - floored.sum()) * 1000))
    remainders = values - floored
    if n_add > 0:
        indices = np.argsort(remainders)[::-1][:n_add]
        floored[indices] += 0.001
    elif n_add < 0:
        # Input summed to slightly > 1 even after normalisation (rare fp edge case).
        # Subtract 0.001 from the entries with the smallest remainders.
        indices = np.argsort(remainders)[:abs(n_add)]
        floored[indices] = np.maximum(0.0, floored[indices] - 0.001)
    return np.round(floored, 3)


# ── Load inputs ────────────────────────────────────────────────────────────────
ladder = pd.read_csv(os.path.join(SCRIPTS_DIR, '../data/technology_ladder.csv'))

hdi_future = pd.read_csv(os.path.join(SCRIPTS_DIR, '../../hdi/data/hdi_future.csv'))

current = pd.read_csv(os.path.join(SCRIPTS_DIR, '../data/sanitation_combined.csv'))

# Most recent measured HDI per country
hdi_hist = pd.read_excel(
    os.path.join(SCRIPTS_DIR, '../../hdi/data/original/hdr-historical-data.xlsx'),
    sheet_name='Data',
)
hdi_hist = hdi_hist[['countryIsoCode', 'year', 'value']].rename(
    columns={'countryIsoCode': 'alpha3', 'value': 'hdi_hist'}
)
# Keep only the most recent year per country
hdi_hist = hdi_hist.sort_values('year').groupby('alpha3').last().reset_index()
hdi_hist = hdi_hist[['alpha3', 'hdi_hist']]


# ── Build interpolation tables: {(context, tech): (hdi_nodes, fraction_nodes)} ─
interp_tables = {}
for ctx in ('Urban', 'Rural'):
    sub = ladder[ladder['context'] == ctx].sort_values('hdi_bin')
    hdi_nodes = sub['hdi_bin'].to_numpy(dtype=float)
    for tech in TECH_COLS:
        interp_tables[(ctx, tech)] = (hdi_nodes, sub[tech].to_numpy(dtype=float))


def ladder_fractions(hdi_val, context):
    """Return an np.array of tech fractions (same order as TECH_COLS) for a given HDI."""
    return np.array([
        float(np.interp(hdi_val, *interp_tables[(context, tech)]))
        for tech in TECH_COLS
    ])


# ── Build lookup: current tech fractions from sanitation_combined.csv ──────────
# current_fracs[alpha3][ctx] = np.array (same order as TECH_COLS)
current_fracs = {}
for _, row in current.iterrows():
    a3 = row['alpha3']
    current_fracs[a3] = {}
    for ctx, suffix in (('Urban', '_urb'), ('Rural', '_rur')):
        arr = np.array([
            row.get(f'{tech}{suffix}', np.nan) for tech in TECH_COLS
        ], dtype=float)
        current_fracs[a3][ctx] = arr


# ── Delta computation from hdi_future ─────────────────────────────────────────
# hdi_future columns: alpha3, scenario, 2025, 2030, 2050, 2100
str_years = [str(y) for y in PROJ_YEARS]
hdi_future_indexed = hdi_future.set_index(['alpha3', 'scenario'])

# Merge historical HDI into hdi_future for easy access
hdi_future = hdi_future.merge(hdi_hist, on='alpha3', how='left')


# ── Project tech fractions for each (country, scenario, year) ─────────────────
records = []
for _, row in hdi_future.iterrows():
    alpha3    = row['alpha3']
    scenario  = row['scenario']
    hdi_2025  = row['2025']          # SSP baseline at 2025 (may differ from hist)
    cur_hdi   = row.get('hdi_hist', np.nan)   # most recent measured HDI

    has_current_data = alpha3 in current_fracs and not np.isnan(cur_hdi)

    for yr in PROJ_YEARS:
        hdi_yr = row[str(yr)]
        delta  = hdi_yr - hdi_2025     # SSP-scenario change from 2025

        rec = {'alpha3': alpha3, 'scenario': scenario, 'year': yr}

        for ctx, suffix in (('Urban', '_urb'), ('Rural', '_rur')):
            if yr == 2025 and has_current_data:
                # Use actual current values directly — no projection for 2025
                fracs_arr = current_fracs[alpha3][ctx].copy()
            elif has_current_data:
                # Delta projection anchored to historical HDI
                target_hdi = cur_hdi + delta
                fracs_current = ladder_fractions(cur_hdi, ctx)
                fracs_target  = ladder_fractions(target_hdi, ctx)
                actual_current = current_fracs[alpha3][ctx]
                fracs_arr = actual_current + (fracs_target - fracs_current)
                # Clamp to [0, 1]
                fracs_arr = np.clip(fracs_arr, 0.0, 1.0)
                # Renormalise
                total = fracs_arr.sum()
                if total > 0:
                    fracs_arr = fracs_arr / total
            else:
                # No current-data baseline: absolute ladder lookup
                fracs_arr = ladder_fractions(hdi_yr, ctx)
                # Normalise (ladder should sum to ~1 but floating-point safe)
                total = fracs_arr.sum()
                if total > 0:
                    fracs_arr = fracs_arr / total

            # Round to 3 dp with sum-to-1 guarantee
            fracs_arr = round_fracs_3dp_sum1(fracs_arr)

            for tech, frac in zip(TECH_COLS, fracs_arr):
                rec[f'{tech}{suffix}'] = frac

        records.append(rec)

wide = pd.DataFrame(records)

# ── Merge passthrough parameters from current sanitation_combined.csv ─────────
passthrough_cols_urb = [f'{p}_urb' for p in PASSTHROUGH_PARAMS]
passthrough_cols_rur = [f'{p}_rur' for p in PASSTHROUGH_PARAMS]
all_passthrough = [c for c in passthrough_cols_urb + passthrough_cols_rur if c in current.columns]

passthrough = current[['alpha3'] + all_passthrough].copy()
wide = wide.merge(passthrough, on='alpha3', how='left')

# ── Fill NaN passthrough params for countries without current data ────────────
# 22 countries are in hdi_future.csv but not in sanitation_combined.csv; the
# left-join above leaves their passthrough columns as NaN.  Apply the same
# model defaults that transform.py hardcodes for every country.
SCALAR_DEFAULTS = {'onsiteDumpedland': 0.1, 'emptyFrequency': 3.0}
for param, default in SCALAR_DEFAULTS.items():
    for sfx in ('_urb', '_rur'):
        col = param + sfx
        if col in wide.columns:
            wide[col] = wide[col].fillna(default)
# All remaining NaN (treatment params, containerBased, etc.) → 0
wide = wide.fillna(0)

# ── Order columns to match sanitation_combined.csv layout ─────────────────────
def build_context_cols(suffix):
    tech_order = [
        'bucketLatrine', 'compostingToilet', 'flushOpen', 'flushPit',
        'flushSeptic', 'flushSewer', 'flushUnknown', 'hangingToilet',
        'openDefecation', 'other', 'pitNoSlab', 'pitSlab', 'containerBased',
        'onsiteDumpedland', 'emptyFrequency', 'pitAdditive', 'urine',
        'twinPits', 'coverBury', 'fecalSludgeTreated', 'sewageTreated',
        'isWatertight', 'hasLeach',
    ]
    return [f'{t}{suffix}' for t in tech_order if f'{t}{suffix}' in wide.columns]

col_order = ['scenario', 'year', 'alpha3'] + build_context_cols('_urb') + build_context_cols('_rur')
wide = wide[col_order]

wide.sort_values(['scenario', 'year', 'alpha3'], inplace=True)
wide.reset_index(drop=True, inplace=True)

# ── Verify rounding ───────────────────────────────────────────────────────────
tech_urb = [f'{t}_urb' for t in TECH_COLS]
tech_rur = [f'{t}_rur' for t in TECH_COLS]
urb_sums = wide[tech_urb].sum(axis=1).round(3)
rur_sums = wide[tech_rur].sum(axis=1).round(3)
bad_urb = (urb_sums != 1.0).sum()
bad_rur = (rur_sums != 1.0).sum()
if bad_urb or bad_rur:
    print(f"WARNING: {bad_urb} Urban rows and {bad_rur} Rural rows do not sum to 1.000")
else:
    print("Rounding check passed: all rows sum to 1.000")

# ── Save sanitation_combined_future.csv ───────────────────────────────────────
out_path = os.path.join(SCRIPTS_DIR, '../data/sanitation_combined_future.csv')
with open(out_path, 'w', encoding='utf-8') as f:
    wide.to_csv(f, index=False, lineterminator='\n')

print(f"Rows     : {len(wide)}")
print(f"Countries: {wide['alpha3'].nunique()}")
print(f"Scenarios: {sorted(wide['scenario'].unique())}")
print(f"Years    : {sorted(wide['year'].unique())}")
print(f"Columns  : {len(wide.columns)}")
print(f"Saved  → {out_path}")
print()
print("Sample (AFG, SSP2):")
sample = wide[(wide['alpha3'] == 'AFG') & (wide['scenario'] == 'SSP2')]
show_cols = ['scenario', 'year', 'alpha3',
             'flushSewer_urb', 'pitSlab_urb', 'openDefecation_urb',
             'flushSewer_rur', 'pitSlab_rur', 'openDefecation_rur']
print(sample[show_cols].to_string(index=False))


# ── Technology elimination analysis ──────────────────────────────────────────
# For each (country, scenario, technology, context) estimate the calendar year
# in which the technology fraction will cross each phase-out threshold.
# Uses the technology_thresholds.csv produced by transition_matrix.py.
thresh_path = os.path.join(SCRIPTS_DIR, '../data/technology_thresholds.csv')
if not os.path.exists(thresh_path):
    print("\nSkipping technology elimination: technology_thresholds.csv not found.")
else:
    print("\nBuilding technology elimination table …")
    thresholds = pd.read_csv(thresh_path)
    phase_outs = thresholds[thresholds['direction'] == 'phase_out'].copy()

    # Build per-country-per-scenario HDI trajectory:
    # years=[2025, 2030, 2050, 2100], hdi values from hdi_future
    # Use the delta-anchored trajectory: target_hdi = current_hdi + delta
    hdi_traj = hdi_future.copy()

    def year_of_crossing(years, hdi_vals, threshold_hdi, increasing=True):
        """
        Find the first year at which hdi_vals crosses threshold_hdi.
        increasing=True  → we are looking for HDI rising to threshold_hdi
        increasing=False → HDI falling to threshold_hdi
        Returns np.nan if the threshold is never crossed within the range.
        """
        for i in range(len(years) - 1):
            h0, h1 = hdi_vals[i], hdi_vals[i + 1]
            y0, y1 = years[i],    years[i + 1]
            if increasing and h0 <= threshold_hdi < h1:
                t = (threshold_hdi - h0) / (h1 - h0)
                return round(y0 + t * (y1 - y0))
            if not increasing and h0 >= threshold_hdi > h1:
                t = (threshold_hdi - h0) / (h1 - h0)
                return round(y0 + t * (y1 - y0))
        return np.nan

    elim_rows = []
    for _, hdi_row in hdi_traj.iterrows():
        alpha3   = hdi_row['alpha3']
        scenario = hdi_row['scenario']
        cur_hdi  = hdi_row.get('hdi_hist', np.nan)
        hdi_2025 = hdi_row['2025']

        if np.isnan(cur_hdi):
            cur_hdi = hdi_2025   # fallback to SSP 2025 for anchoring

        # Build delta-anchored trajectory
        traj_years = PROJ_YEARS
        traj_hdis  = [
            cur_hdi + (hdi_row[str(yr)] - hdi_2025)
            for yr in PROJ_YEARS
        ]

        for _, th_row in phase_outs.iterrows():
            ctx          = th_row['context']
            technology   = th_row['technology']
            threshold    = th_row['threshold']
            threshold_hdi = th_row['hdi_crossing']

            if np.isnan(threshold_hdi):
                continue

            yr = year_of_crossing(traj_years, traj_hdis, threshold_hdi, increasing=True)
            elim_rows.append({
                'alpha3':        alpha3,
                'scenario':      scenario,
                'context':       ctx,
                'technology':    technology,
                'threshold_pct': threshold,
                'threshold_hdi': threshold_hdi,
                'year_of_elimination': yr,
            })

    elim_df = pd.DataFrame(elim_rows)
    elim_df = elim_df.dropna(subset=['year_of_elimination'])
    elim_df['year_of_elimination'] = elim_df['year_of_elimination'].astype(int)
    elim_df.sort_values(
        ['alpha3', 'scenario', 'context', 'technology', 'threshold_pct'],
        inplace=True,
    )

    elim_path = os.path.join(SCRIPTS_DIR, '../data/technology_elimination.csv')
    elim_df.to_csv(elim_path, index=False, lineterminator='\n')
    print(f"  {len(elim_df)} elimination events for {elim_df['alpha3'].nunique()} countries")
    print(f"  Saved → {elim_path}")

    # Summary: openDefecation 5% phase-out by SSP scenario
    if not elim_df.empty:
        od_urb = elim_df[
            (elim_df['technology']  == 'openDefecation') &
            (elim_df['context']     == 'Urban') &
            (elim_df['threshold_pct'] == 0.05)
        ]
        if not od_urb.empty:
            print("\n  openDefecation Urban <5% (median year by scenario):")
            print(od_urb.groupby('scenario')['year_of_elimination'].median().to_string())
