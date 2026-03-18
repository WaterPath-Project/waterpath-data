"""
analyze.py — Build a longitudinal sanitation × HDI dataset from JMP survey data.

Output: ../data/sanitation_hdi_history.csv
Columns: alpha3, country, context, year, source, hdi,
         flushSewer, flushSeptic, flushPit, flushUnknown, flushOpen,
         pitSlab, pitNoSlab, hangingToilet, bucketLatrine,
         compostingToilet, openDefecation, other
"""

import os
import sys
import pandas as pd
import numpy as np

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 1. Load raw JMP survey data ────────────────────────────────────────────────
jmp = pd.read_csv(os.path.join(SCRIPTS_DIR, '../data/jmp_sanitation_surveys.csv'))
jmp.rename(columns={'alpha.3': 'alpha3'}, inplace=True)

# Extract survey year from source string (format: ISO3_YYYY_SURVEYID)
jmp['year'] = jmp['source'].str.split('_').str[1].astype(int)

# ── 2. Harmonisation mapping (classific_id → technology bucket) ───────────────
# Mirrors the mapping in transform.py
HARMON = {
    1:  'flushSewer',
    2:  'flushSeptic',
    3:  'flushPit',
    4:  'flushUnknown',
    5:  'flushOpen',
    6:  'pitSlab',       # VIP
    7:  'pitSlab',       # pit with slab
    8:  'pitSlab',       # traditional latrine
    9:  'pitNoSlab',
    10: 'hangingToilet',
    11: 'bucketLatrine',
    12: 'other',
    13: 'compostingToilet',
    14: 'pitSlab',       # other improved
    15: 'openDefecation',
    16: 'other',
    17: 'other',
}
TECH_COLS = [
    'flushSewer', 'flushSeptic', 'flushPit', 'flushUnknown', 'flushOpen',
    'pitSlab', 'pitNoSlab', 'hangingToilet', 'bucketLatrine',
    'compostingToilet', 'openDefecation', 'other',
]

jmp['san'] = jmp['classific_id'].map(HARMON)

# ── 3. Aggregate to san-bucket level and filter complete surveys (sum ≈ 1) ────
agg = (
    jmp.groupby(['alpha3', 'country', 'source', 'context', 'year', 'san'], as_index=False)
    ['percentage'].sum()
)

totals = agg.groupby(['alpha3', 'source', 'context'])['percentage'].sum().reset_index()
totals.rename(columns={'percentage': 'total'}, inplace=True)
complete = totals[totals['total'].round(3) == 1.0][['alpha3', 'source', 'context']]

agg = agg.merge(complete, on=['alpha3', 'source', 'context'])

# ── 4. Pivot to wide format (one row per alpha3 × source × context) ───────────
wide = (
    agg.groupby(['alpha3', 'country', 'source', 'context', 'year'])
    .apply(lambda g: pd.Series(dict(zip(g['san'], g['percentage']))), include_groups=False)
    .reset_index()
)
for col in TECH_COLS:
    if col not in wide.columns:
        wide[col] = np.nan
wide = wide[['alpha3', 'country', 'source', 'context', 'year'] + TECH_COLS]

# ── 5. Handle Urban / Rural / National context logic ──────────────────────────
# For each (alpha3, source):
#   - If both Urban AND Rural are complete → keep them as-is
#   - If only National is complete (no Urban/Rural) → duplicate as both Urban and Rural
#   - Otherwise → skip

contexts_available = (
    wide.groupby(['alpha3', 'source'])['context']
    .apply(set)
    .reset_index()
    .rename(columns={'context': 'contexts'})
)

def classify_source(ctx_set):
    has_urban  = 'Urban'    in ctx_set
    has_rural  = 'Rural'    in ctx_set
    has_nat    = 'National' in ctx_set
    if has_urban and has_rural:
        return 'use_urban_rural'
    if has_nat and not has_urban and not has_rural:
        return 'use_national'
    if has_urban and not has_rural and not has_nat:
        return 'use_urban_only'
    return 'skip'

contexts_available['strategy'] = contexts_available['contexts'].apply(classify_source)

# Urban+Rural: keep only Urban and Rural rows
ur_keys = contexts_available[contexts_available['strategy'] == 'use_urban_rural'][['alpha3', 'source']]
ur_data = wide.merge(ur_keys, on=['alpha3', 'source'])
ur_data = ur_data[ur_data['context'].isin(['Urban', 'Rural'])]

# National-only: replicate as both Urban and Rural
nat_keys = contexts_available[contexts_available['strategy'] == 'use_national'][['alpha3', 'source']]
nat_data = wide.merge(nat_keys, on=['alpha3', 'source'])
nat_data = nat_data[nat_data['context'] == 'National']
nat_urban = nat_data.copy(); nat_urban['context'] = 'Urban'
nat_rural = nat_data.copy(); nat_rural['context'] = 'Rural'
nat_data = pd.concat([nat_urban, nat_rural], ignore_index=True)

# Urban-only: include for Urban context only (informs the Urban technology ladder)
urb_only_keys = contexts_available[contexts_available['strategy'] == 'use_urban_only'][['alpha3', 'source']]
urb_only_data = wide.merge(urb_only_keys, on=['alpha3', 'source'])
urb_only_data = urb_only_data[urb_only_data['context'] == 'Urban']

result = pd.concat([ur_data, nat_data, urb_only_data], ignore_index=True)
result.sort_values(['alpha3', 'context', 'year', 'source'], inplace=True)
result.reset_index(drop=True, inplace=True)

# ── 6. Merge with historical HDI ──────────────────────────────────────────────
hdi_hist = pd.read_excel(
    os.path.join(SCRIPTS_DIR, '../../hdi/data/original/hdr-historical-data.xlsx'),
    sheet_name='Data'
)
hdi_hist = hdi_hist[['countryIsoCode', 'year', 'value']].rename(
    columns={'countryIsoCode': 'alpha3', 'value': 'hdi'}
)

result = result.merge(hdi_hist, on=['alpha3', 'year'], how='left')

# Reorder columns: HDI right after year
cols = ['alpha3', 'country', 'context', 'year', 'source', 'hdi'] + TECH_COLS
result = result[cols]

# ── 7. Report and save ────────────────────────────────────────────────────────
n_countries = result['alpha3'].nunique()
n_rows = len(result)
n_with_hdi = result['hdi'].notna().sum()
print(f"Rows: {n_rows} | Countries: {n_countries} | Rows with HDI: {n_with_hdi} / {n_rows}")

out_path = os.path.join(SCRIPTS_DIR, '../data/sanitation_hdi_history.csv')
with open(out_path, 'w', encoding='utf-8') as f:
    result.to_csv(f, index=False, lineterminator='\n')
print(f"Saved → {out_path}")
