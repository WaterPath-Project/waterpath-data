"""
project_future.py -- Project sanitation technology mixes for SSP scenarios.

SSP-constrained technology ladder method
-----------------------------------------
The five SSP Excel files (SSP1-SSP5) provide projected national-average
percentages for four aggregate sanitation categories per country x decade
(2010-2100):

  unop  -- unimproved + open defecation
            tech cols: pitNoSlab, bucketLatrine, hangingToilet,
                       flushOpen, flushUnknown, other, openDefecation
  latr  -- latrines
            tech cols: flushPit, pitSlab, compostingToilet
  sept  -- septic tanks
            tech col : flushSeptic
  sewr  -- sewer systems
            tech col : flushSewer

These national projections act as constraints while the technology ladder
(from transition_matrix.py) provides the urban/rural split and within-group
technology distribution.

Projection algorithm (for each country x scenario x year != 2025)
-------------------------------------------------------------------
  1.  National aggregate fractions f_g (g in {unop, latr, sept, sewr})
      read from the SSP Excel sheet (values are % of total population).
      Year 2025 is linearly interpolated between SSP 2020 and 2030.

  2.  Urban population fraction p_urb from SSP 'popurb' sheet
      (scenario-consistent; values are already in 0-1 range).

  3.  Target HDI via delta-anchor:
        target_hdi = current_hdi + delta_hdi
        delta_hdi  = hdi_future[year] - hdi_future[2025]
      current_hdi = most recent measured value from hdr-historical-data.xlsx.
      This anchors the projection to the known current state while the SSP
      scenario captures the relative HDI change.

  4.  Technology ladder fractions at target_hdi for Urban and Rural contexts
      via piecewise-linear interpolation on the 0.025-wide HDI bins.

  5.  Natural national aggregate predicted by the ladder:
        f_g_nat = p_urb * sum(ladder_t_urb) + p_rur * sum(ladder_t_rur)
                                               (t in group g)

  6.  Group scaling factor: k_g = f_g_ssp / f_g_nat  (capped at 10x)

  7.  Scaled raw fracs: raw_t_ctx = ladder_t_ctx * k_g  (t in group g)

  8.  Renormalise within each context to sum = 1.

For 2025: output sanitation_combined.csv values directly.

Fallback (countries not in SSP data):
  Delta-ladder approach without SSP constraint.

Outputs
--------
  sanitation_combined_future.csv
    4 940 rows (247 countries x 5 SSPs x 4 years), same columns as
    sanitation_combined.csv plus leading 'scenario' and 'year' columns.
    Technology fractions rounded to 3 d.p. (sum = 1.000 per row).
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

# SSP aggregate group -> constituent technology columns
GROUPS = {
    'unop': ['pitNoSlab', 'bucketLatrine', 'hangingToilet',
             'flushOpen', 'flushUnknown', 'other', 'openDefecation'],
    'latr': ['flushPit', 'pitSlab', 'compostingToilet'],
    'sept': ['flushSeptic'],
    'sewr': ['flushSewer'],
}

FIXED_SCALAR_PARAMS = ['onsiteDumpedland', 'emptyFrequency', 'pitAdditive', 'urine', 'twinPits']
# sewageTreated is excluded from passthrough; it is populated per-year/scenario
# from treatment_fractions/data/treatment_future.csv after the main loop.
TREATMENT_PARAMS    = ['coverBury', 'fecalSludgeTreated', 'isWatertight', 'hasLeach']
PASSTHROUGH_PARAMS  = FIXED_SCALAR_PARAMS + TREATMENT_PARAMS + ['containerBased']

PROJ_YEARS = [2025, 2030, 2050, 2100]
SSP_YEARS  = [2010, 2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100]
SSP_NAMES  = ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5']

# M49 numeric code overrides (countries absent from UNSD standard table)
M49_OVERRIDES = {158: 'TWN', 736: 'SDN'}


# -- Rounding helper ----------------------------------------------------------
def round_fracs_3dp_sum1(values):
    """Round to 3 dp, preserving sum = 1.000 via largest-remainder method."""
    values = np.array(values, dtype=float)
    total = values.sum()
    if total > 0:
        values = values / total
    floored = np.floor(np.round(values * 1000, 8)) / 1000
    n_add = int(round((1.0 - floored.sum()) * 1000))
    remainders = values - floored
    if n_add > 0:
        floored[np.argsort(remainders)[::-1][:n_add]] += 0.001
    elif n_add < 0:
        idx = np.argsort(remainders)[:abs(n_add)]
        floored[idx] = np.maximum(0.0, floored[idx] - 0.001)
    return np.round(floored, 3)


# -- Load UNSD country code mapping (M49 numeric -> ISO alpha-3) -------------
unsd = pd.read_csv(
    os.path.join(SCRIPTS_DIR, '../../unsd_countries/data/unsd_countries.csv'), sep=';')
m49_to_alpha3 = unsd.set_index('M49 Code')['ISO-alpha3 Code'].to_dict()
m49_to_alpha3.update(M49_OVERRIDES)


def parse_ssp_sheet(xl, sheet, as_fraction=True):
    """Parse an SSP Excel sheet (unop/latr/sept/sewr/popurb) to a DataFrame
    indexed by alpha3 with year integers as columns.
    as_fraction=True  -> divide values by 100 (sanitation sheets are in %).
    as_fraction=False -> keep raw values (popurb is already 0-1).
    """
    d = xl.parse(sheet)
    d.columns = d.iloc[2].tolist()
    d = d.iloc[3:].copy().reset_index(drop=True)
    d.columns = ['iso_num', 'country', 'region'] + SSP_YEARS
    for yr in SSP_YEARS:
        d[yr] = pd.to_numeric(d[yr], errors='coerce')
    if as_fraction:
        for yr in SSP_YEARS:
            d[yr] = d[yr] / 100.0
    d['alpha3'] = d['iso_num'].map(m49_to_alpha3)
    return d.dropna(subset=['alpha3']).set_index('alpha3')[SSP_YEARS]


# -- Load all SSP Excel files -------------------------------------------------
print("Loading SSP Excel files ...")
ssp_sheets = {}   # {scenario: {group: DataFrame(alpha3 x year, fractions 0-1)}}
p_urb_ssp  = {}   # {scenario: DataFrame(alpha3 x year, fractions 0-1)}

for ssp in SSP_NAMES:
    xl = pd.ExcelFile(
        os.path.join(SCRIPTS_DIR, f'../data/original_projections/{ssp}.xlsx'))
    ssp_sheets[ssp] = {
        sh: parse_ssp_sheet(xl, sh, as_fraction=True)
        for sh in GROUPS.keys()
    }
    p_urb_ssp[ssp] = parse_ssp_sheet(xl, 'popurb', as_fraction=False)
    print(f"  {ssp}: {len(ssp_sheets[ssp]['sewr'])} countries")


def ssp_val(df, alpha3, year):
    """Get SSP value for alpha3 at year; interpolates 2020<->2030 for 2025."""
    if alpha3 not in df.index:
        return None
    row = df.loc[alpha3]
    if year == 2025:
        v20, v30 = row.get(2020), row.get(2030)
        if pd.isna(v20) or pd.isna(v30):
            return None
        return 0.5 * (float(v20) + float(v30))
    val = row.get(year)
    return float(val) if not pd.isna(val) else None


# -- Load technology ladder ---------------------------------------------------
ladder = pd.read_csv(os.path.join(SCRIPTS_DIR, '../data/technology_ladder.csv'))
interp_tables = {}
for ctx in ('Urban', 'Rural'):
    sub = ladder[ladder['context'] == ctx].sort_values('hdi_bin')
    hdi_nodes = sub['hdi_bin'].to_numpy(dtype=float)
    for tech in TECH_COLS:
        interp_tables[(ctx, tech)] = (hdi_nodes, sub[tech].to_numpy(dtype=float))


def ladder_fracs(context, hdi_val):
    """Return {tech: fraction} from ladder interpolation."""
    return {t: float(np.interp(hdi_val, *interp_tables[(context, t)]))
            for t in TECH_COLS}


# -- Load HDI data and current sanitation baseline ----------------------------
hdi_future = pd.read_csv(os.path.join(SCRIPTS_DIR, '../../hdi/data/hdi_future.csv'))

hdi_hist = pd.read_excel(
    os.path.join(SCRIPTS_DIR, '../../hdi/data/original/hdr-historical-data.xlsx'),
    sheet_name='Data',
)[['countryIsoCode', 'year', 'value']].rename(
    columns={'countryIsoCode': 'alpha3', 'value': 'hdi_hist'}
)
hdi_hist = (hdi_hist.sort_values('year')
            .groupby('alpha3').last().reset_index()[['alpha3', 'hdi_hist']])
hdi_future = hdi_future.merge(hdi_hist, on='alpha3', how='left')

current = pd.read_csv(os.path.join(SCRIPTS_DIR, '../data/sanitation_combined.csv'))
current_fracs = {}
for _, row in current.iterrows():
    a3 = row['alpha3']
    current_fracs[a3] = {
        ctx: np.array([row.get(f'{t}{sfx}', np.nan) for t in TECH_COLS], dtype=float)
        for ctx, sfx in (('Urban', '_urb'), ('Rural', '_rur'))
    }


# -- Core: SSP-constrained projection ----------------------------------------
def project_ssp_constrained(target_hdi, f_ssp, p_urb):
    """
    Project urban and rural tech fracs given:
      target_hdi : HDI at which to evaluate the ladder (for shape)
      f_ssp      : {group: national fraction 0-1}   (SSP constraint)
      p_urb      : urban population fraction
    Returns (urb_dict, rur_dict): each {tech: fraction}, summing ~1 before
    normalisation.
    """
    p_rur = 1.0 - p_urb
    ld_u = ladder_fracs('Urban', target_hdi)
    ld_r = ladder_fracs('Rural', target_hdi)
    raw_u, raw_r = {}, {}

    for g, techs in GROUPS.items():
        A_u   = sum(ld_u[t] for t in techs)
        A_r   = sum(ld_r[t] for t in techs)
        f_nat = p_urb * A_u + p_rur * A_r
        # Scale ladder group to match SSP national fraction; cap at 10x
        k = min(f_ssp[g] / f_nat, 10.0) if f_nat > 1e-6 else 0.0
        for t in techs:
            raw_u[t] = ld_u[t] * k
            raw_r[t] = ld_r[t] * k

    s_u = sum(raw_u.values())
    s_r = sum(raw_r.values())
    u_d = {t: v / s_u for t, v in raw_u.items()} if s_u > 0 else ld_u
    r_d = {t: v / s_r for t, v in raw_r.items()} if s_r > 0 else ld_r
    return u_d, r_d


def project_delta_ladder(current_arr, cur_hdi, target_hdi, context):
    """Delta-ladder fallback: shift current fracs by ladder change."""
    f_cur = np.array(list(ladder_fracs(context, cur_hdi).values()))
    f_tgt = np.array(list(ladder_fracs(context, target_hdi).values()))
    result = np.clip(current_arr + (f_tgt - f_cur), 0.0, 1.0)
    s = result.sum()
    return result / s if s > 0 else f_tgt


# -- Main projection loop -----------------------------------------------------
print("Projecting ...")
records = []

for _, hdi_row in hdi_future.iterrows():
    alpha3   = hdi_row['alpha3']
    scenario = hdi_row['scenario']
    hdi_2025 = float(hdi_row['2025'])
    cur_hdi  = float(hdi_row['hdi_hist']) if not pd.isna(hdi_row['hdi_hist']) else np.nan
    has_current = (alpha3 in current_fracs) and not np.isnan(cur_hdi)
    in_ssp_data = (alpha3 in ssp_sheets[scenario]['sewr'].index)

    for yr in PROJ_YEARS:
        rec   = {'alpha3': alpha3, 'scenario': scenario, 'year': yr}
        delta = float(hdi_row[str(yr)]) - hdi_2025

        # 2025: use current values directly (no projection needed)
        if yr == 2025 and has_current:
            for ctx, sfx in (('Urban', '_urb'), ('Rural', '_rur')):
                arr = round_fracs_3dp_sum1(current_fracs[alpha3][ctx])
                for t, v in zip(TECH_COLS, arr):
                    rec[f'{t}{sfx}'] = v
            records.append(rec)
            continue

        # Target HDI: delta-anchored if hist available, else absolute SSP value
        target_hdi = (cur_hdi + delta) if not np.isnan(cur_hdi) else float(hdi_row[str(yr)])

        # Try SSP-constrained approach
        use_ssp = False
        if in_ssp_data:
            f_ssp = {g: ssp_val(ssp_sheets[scenario][g], alpha3, yr) for g in GROUPS}
            p_urb = ssp_val(p_urb_ssp[scenario], alpha3, yr)
            if all(v is not None for v in f_ssp.values()) and p_urb is not None:
                use_ssp = True

        if use_ssp:
            p_urb = float(np.clip(p_urb, 0.01, 0.99))
            u_d, r_d = project_ssp_constrained(target_hdi, f_ssp, p_urb)
        elif has_current:
            # Delta-ladder fallback
            u_arr = project_delta_ladder(current_fracs[alpha3]['Urban'], cur_hdi, target_hdi, 'Urban')
            r_arr = project_delta_ladder(current_fracs[alpha3]['Rural'], cur_hdi, target_hdi, 'Rural')
            u_d = dict(zip(TECH_COLS, u_arr))
            r_d = dict(zip(TECH_COLS, r_arr))
        else:
            # Absolute ladder lookup (no current baseline)
            u_d = ladder_fracs('Urban', target_hdi)
            r_d = ladder_fracs('Rural', target_hdi)

        u_arr = round_fracs_3dp_sum1([u_d[t] for t in TECH_COLS])
        r_arr = round_fracs_3dp_sum1([r_d[t] for t in TECH_COLS])
        for t, v in zip(TECH_COLS, u_arr):
            rec[f'{t}_urb'] = v
        for t, v in zip(TECH_COLS, r_arr):
            rec[f'{t}_rur'] = v
        records.append(rec)

wide = pd.DataFrame(records)

# -- Merge passthrough parameters ---------------------------------------------
all_pt = [f'{p}{s}' for p in PASSTHROUGH_PARAMS for s in ('_urb', '_rur')
          if f'{p}_urb' in current.columns]
all_pt = [c for c in all_pt if c in current.columns]
wide   = wide.merge(current[['alpha3'] + all_pt], on='alpha3', how='left')

# Fill defaults for countries not in sanitation_combined.csv
for p, v in {'onsiteDumpedland': 0.1, 'emptyFrequency': 3.0}.items():
    for s in ('_urb', '_rur'):
        c = p + s
        if c in wide.columns:
            wide[c] = wide[c].fillna(v)
wide = wide.fillna(0)

# -- Set sewageTreated from treatment_future.csv (per alpha3 x year x scenario) --
# sewageTreated = sum of Primary + Secondary + Tertiary + Quaternary treatment
# fractions, capped at 1.0. No urban/rural split is available so both contexts
# receive the national-level value.  Countries absent from treatment_future.csv
# fall back to the treatment.csv baseline sum.
TREAT_COLS = [
    'FractionPrimarytreatment', 'FractionSecondarytreatment',
    'FractionTertiarytreatment', 'FractionQuarternarytreatment',
]
treat_base = pd.read_csv(os.path.join(SCRIPTS_DIR, '../../treatment_fractions/data/treatment.csv'))
treat_base['sewageTreated'] = treat_base[TREAT_COLS].sum(axis=1).clip(upper=1.0).round(3)
treat_base_lookup = treat_base.set_index('alpha3')['sewageTreated']

treat_fut = pd.read_csv(os.path.join(SCRIPTS_DIR, '../../treatment_fractions/data/treatment_future.csv'))
treat_fut['sewageTreated'] = treat_fut[TREAT_COLS].sum(axis=1).clip(upper=1.0).round(3)
treat_fut = treat_fut[['year', 'ssp', 'alpha3', 'sewageTreated']].rename(columns={'ssp': 'scenario'})
treat_fut_lookup = treat_fut.set_index(['alpha3', 'year', 'scenario'])['sewageTreated']

wide = wide.merge(
    treat_fut[['alpha3', 'year', 'scenario', 'sewageTreated']],
    on=['alpha3', 'year', 'scenario'], how='left'
)
# Fallback chain: treatment_future.csv → treatment.csv → JMP value in sanitation_combined.csv → 0
jmp_sewage_lookup = current.set_index('alpha3')['sewageTreated_urb']
missing = wide['sewageTreated'].isna()
wide.loc[missing, 'sewageTreated'] = (
    wide.loc[missing, 'alpha3'].map(treat_base_lookup)
    .combine_first(wide.loc[missing, 'alpha3'].map(jmp_sewage_lookup))
    .fillna(0.0)
)
wide['sewageTreated_urb'] = wide['sewageTreated'].round(3)
wide['sewageTreated_rur'] = wide['sewageTreated'].round(3)
wide.drop(columns='sewageTreated', inplace=True)

# -- Column ordering to match sanitation_combined.csv layout -----------------
def ctx_cols(suffix):
    order = ['bucketLatrine', 'compostingToilet', 'flushOpen', 'flushPit',
             'flushSeptic', 'flushSewer', 'flushUnknown', 'hangingToilet',
             'openDefecation', 'other', 'pitNoSlab', 'pitSlab', 'containerBased',
             'onsiteDumpedland', 'emptyFrequency', 'pitAdditive', 'urine',
             'twinPits', 'coverBury', 'fecalSludgeTreated', 'sewageTreated',
             'isWatertight', 'hasLeach']
    return [f'{t}{suffix}' for t in order if f'{t}{suffix}' in wide.columns]

wide = wide[['scenario', 'year', 'alpha3'] + ctx_cols('_urb') + ctx_cols('_rur')]
wide.sort_values(['scenario', 'year', 'alpha3'], inplace=True)
wide.reset_index(drop=True, inplace=True)

# -- Verify rounding ----------------------------------------------------------
t_u = [f'{t}_urb' for t in TECH_COLS]
t_r = [f'{t}_rur' for t in TECH_COLS]
bad_u = (wide[t_u].sum(axis=1).round(3) != 1.0).sum()
bad_r = (wide[t_r].sum(axis=1).round(3) != 1.0).sum()
if bad_u or bad_r:
    print(f"WARNING: {bad_u} Urban and {bad_r} Rural rows do not sum to 1.000")
else:
    print("Rounding check passed: all rows sum to 1.000")

# -- Save ---------------------------------------------------------------------
out_path = os.path.join(SCRIPTS_DIR, '../data/sanitation_combined_future.csv')
with open(out_path, 'w', encoding='utf-8') as f:
    wide.to_csv(f, index=False, lineterminator='\n')

print(f"Rows     : {len(wide)}")
print(f"Countries: {wide['alpha3'].nunique()}")
print(f"Scenarios: {sorted(wide['scenario'].unique())}")
print(f"Years    : {sorted(wide['year'].unique())}")
print(f"Columns  : {len(wide.columns)}")
print(f"Saved -> {out_path}")

# -- Sample output ------------------------------------------------------------
print()
print("Sample (AFG, SSP2):")
sample = wide[(wide['alpha3'] == 'AFG') & (wide['scenario'] == 'SSP2')]
show = ['scenario', 'year', 'alpha3',
        'flushSewer_urb', 'pitSlab_urb', 'openDefecation_urb',
        'flushSewer_rur', 'pitSlab_rur', 'openDefecation_rur']
print(sample[show].to_string(index=False))

# -- Verification: check SSP national-aggregate match for sample countries ---
print()
print("SSP constraint accuracy (SSP2, 2050, pop-weighted national vs SSP target):")
for a3 in ['AFG', 'NGA', 'BRA']:
    if a3 not in ssp_sheets['SSP2']['sewr'].index:
        continue
    row = wide[(wide.alpha3 == a3) & (wide.scenario == 'SSP2') & (wide.year == 2050)]
    if row.empty:
        continue
    p_urb = ssp_val(p_urb_ssp['SSP2'], a3, 2050)
    if p_urb is None:
        continue
    p_rur = 1.0 - float(p_urb)
    for g, techs in GROUPS.items():
        u_sum = sum(float(row[f'{t}_urb'].iloc[0]) for t in techs)
        r_sum = sum(float(row[f'{t}_rur'].iloc[0]) for t in techs)
        nat   = float(p_urb) * u_sum + p_rur * r_sum
        ssp_target = ssp_val(ssp_sheets['SSP2'][g], a3, 2050)
        print(f"  {a3} {g:4s}: ssp={ssp_target:.3f}  "
              f"urb={u_sum:.3f}  rur={r_sum:.3f}  national={nat:.3f}  "
              f"diff={nat - ssp_target:+.3f}")
