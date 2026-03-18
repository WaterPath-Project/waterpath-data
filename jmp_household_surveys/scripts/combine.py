import pandas as pd

urban = pd.read_csv("../data/sanitation_urban.csv", delimiter=";", encoding='utf-8')

rural = pd.read_csv("../data/sanitation_rural.csv", delimiter=";", encoding='utf-8')

combined = urban.merge(rural, on=["region"], suffixes=("_urb", "_rur")).reset_index(drop=True)

combined.rename(columns={'region': 'alpha3'}, inplace=True)

combined.drop(columns=['warning_urb','warning_rur'], inplace=True, errors='ignore')

# Fill NaN cells with 0.
# - containerBased is never reported in survey data → 0 is correct.
# - sewageTreated is missing for some countries → 0 (no treatment data) is a
#   safe model default and avoids empty cells in the output.
# None of the 12 technology fraction columns have NaN, so sum == 1 is unaffected.
combined = combined.fillna(0)

combined.to_csv("../data/sanitation_combined.csv", index=False)