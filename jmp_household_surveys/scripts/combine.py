import pandas as pd

urban = pd.read_csv("../data/sanitation_urban.csv", delimiter=";", encoding='utf-8')

rural = pd.read_csv("../data/sanitation_rural.csv", delimiter=";", encoding='utf-8')

combined = urban.merge(rural, on=["region"], suffixes=("_urb", "_rur")).reset_index(drop=True)

combined.rename(columns={'region': 'alpha3'}, inplace=True)

combined.drop(columns=['warning_urb','warning_rur'], inplace=True, errors='ignore')

# Fill NaN cells with 0.
combined = combined.fillna(0)

# Fix containerBased: for a small number of countries the 12 TECH_COLS do not
# sum to 1 because containerBased was not reported (NaN → 0 above).  The gap
# is by definition the containerBased fraction; compute it as the residual so
# every row satisfies sum(TECH_COLS + containerBased) = 1.
_TECH_COLS = [
    'flushSewer', 'flushSeptic', 'flushPit', 'flushUnknown', 'flushOpen',
    'pitSlab', 'pitNoSlab', 'hangingToilet', 'bucketLatrine',
    'compostingToilet', 'openDefecation', 'other',
]
for _sfx in ('_urb', '_rur'):
    _tech_sum = combined[[f'{t}{_sfx}' for t in _TECH_COLS]].sum(axis=1)
    _residual = (1.0 - _tech_sum).clip(lower=0.0).round(3)
    _cb = f'containerBased{_sfx}'
    if _cb in combined.columns:
        # Only overwrite where containerBased is 0 but the gap is real (>0.001)
        _mask = (combined[_cb] < 1e-6) & (_residual > 0.001)
        combined.loc[_mask, _cb] = _residual[_mask]

# Set sewageTreated from treatment_fractions/data/treatment.csv.
# Both urban and rural receive the same national-level value (no urban/rural
# split available in the treatment data).
# sewageTreated = Primary + Secondary + Tertiary + Quaternary, capped at 1.
# For the small number of countries absent from treatment.csv but with a
# non-zero JMP-based value, the existing JMP value is preserved as fallback.
TREAT_COLS = [
    'FractionPrimarytreatment', 'FractionSecondarytreatment',
    'FractionTertiarytreatment', 'FractionQuaternarytreatment',
]
treatment = pd.read_csv('../../treatment_fractions/data/treatment.csv')
treatment['sewageTreated'] = treatment[TREAT_COLS].sum(axis=1).clip(upper=1.0).round(3)
treat_lookup = treatment.set_index('alpha3')['sewageTreated']

# Primary: treatment.csv; fallback: keep existing JMP value (already 0-filled above)
combined['sewageTreated_urb'] = combined['alpha3'].map(treat_lookup).combine_first(combined['sewageTreated_urb']).round(3)
combined['sewageTreated_rur'] = combined['sewageTreated_urb']

combined.to_csv("../data/sanitation_combined.csv", index=False, float_format='%.3f')