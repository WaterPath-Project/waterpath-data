import pandas as pd

urban = pd.read_csv("../data/sanitation_urban.csv", delimiter=";", encoding='utf-8')

rural = pd.read_csv("../data/sanitation_rural.csv", delimiter=";", encoding='utf-8')

combined = urban.merge(rural, on=["region"], suffixes=("_urb", "_rur")).reset_index(drop=True)

combined.rename(columns={'region': 'alpha3'}, inplace=True)

combined.drop(columns=['warning_urb','warning_rur'], inplace=True, errors='ignore')

# Fill NaN cells with 0.
# - containerBased is never reported in survey data → 0 is correct.
# None of the 12 technology fraction columns have NaN, so sum == 1 is unaffected.
combined = combined.fillna(0)

# Set sewageTreated from treatment_fractions/data/treatment.csv.
# Both urban and rural receive the same national-level value (no urban/rural
# split available in the treatment data).
# sewageTreated = Primary + Secondary + Tertiary + Quaternary, capped at 1.
# For the small number of countries absent from treatment.csv but with a
# non-zero JMP-based value, the existing JMP value is preserved as fallback.
TREAT_COLS = [
    'FractionPrimarytreatment', 'FractionSecondarytreatment',
    'FractionTertiarytreatment', 'FractionQuarternarytreatment',
]
treatment = pd.read_csv('../../treatment_fractions/data/treatment.csv')
treatment['sewageTreated'] = treatment[TREAT_COLS].sum(axis=1).clip(upper=1.0).round(3)
treat_lookup = treatment.set_index('alpha3')['sewageTreated']

# Primary: treatment.csv; fallback: keep existing JMP value (already 0-filled above)
combined['sewageTreated_urb'] = combined['alpha3'].map(treat_lookup).combine_first(combined['sewageTreated_urb']).round(3)
combined['sewageTreated_rur'] = combined['sewageTreated_urb']

combined.to_csv("../data/sanitation_combined.csv", index=False)