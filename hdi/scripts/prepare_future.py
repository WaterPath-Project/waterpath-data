import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import sys
import os

SCRIPTS_DIR = sys.path[0]

# Load UNSD country codes (semicolon-delimited)
unsd = pd.read_csv(
    os.path.join(SCRIPTS_DIR, '../../unsd_countries/data/unsd_countries.csv'),
    sep=';', encoding='utf-8'
)

# Name mapping: SSP "Region" column value → UNSD "Country or Area" exact name.
# The UNSD file uses U+2019 (right single quotation mark) in some names while
# the SSP file uses U+0027 (straight apostrophe); normalization handles the rest.
name_mapping = {
    'Bolivia': 'Bolivia (Plurinational State of)',
    'Hong Kong': 'China, Hong Kong Special Administrative Region',
    'Iran': 'Iran (Islamic Republic of)',
    'Laos': "Lao People's Democratic Republic",
    'Moldova': 'Republic of Moldova',
    'Netherlands': 'Netherlands (Kingdom of the)',
    'South Korea': 'Republic of Korea',
    'Syria': 'Syrian Arab Republic',
    'Tanzania': 'United Republic of Tanzania',
    'Turkey': 'T\u00fcrkiye',
    'United Kingdom': 'United Kingdom of Great Britain and Northern Ireland',
    'United States': 'United States of America',
    'Venezuela': 'Venezuela (Bolivarian Republic of)',
    # SSP uses U+0027 (straight apostrophe); UNSD uses U+2019 (curly)
    "C\u00f4te d'Ivoire": 'C\u00f4te d\u2019Ivoire',
}

# Read the SSP Excel file
hdi_future = pd.read_excel(os.path.join(SCRIPTS_DIR, "../data/original/SSP-Extensions_Human_Development_Index_v1.0.xlsx"), sheet_name="data")

# Filter rows where Variable is "Human Development Index"
hdi_future = hdi_future[hdi_future['Variable'] == 'Human Development Index']

# Keep only specified columns
hdi_future = hdi_future[['Region', 'Scenario', '2025', '2030', '2050', '2075']]

# Apply name mapping to align SSP region names with UNSD country names
hdi_future['Region_Mapped'] = hdi_future['Region'].replace(name_mapping)

# Infer 2100 values using linear regression on 2025/2030/2050/2075
years = np.array([2025, 2030, 2050, 2075]).reshape(-1, 1)
target_year = np.array([[2100]])

hdi_2100 = []
for idx, row in hdi_future.iterrows():
    values = np.array([row['2025'], row['2030'], row['2050'], row['2075']]).reshape(-1, 1)
    model = LinearRegression()
    model.fit(years, values)
    predicted = model.predict(target_year)[0][0]
    hdi_2100.append(predicted)

hdi_future['2100'] = hdi_2100

# Remove the 2075 column
hdi_future = hdi_future.drop(columns=['2075'])

# Round HDI values to 3 decimal places
year_cols = ['2025', '2030', '2050', '2100']
for year_col in year_cols:
    hdi_future[year_col] = hdi_future[year_col].round(3)

# Build a deduplicated UNSD lookup (one row per country)
unsd_lookup = (
    unsd[['Country or Area', 'ISO-alpha3 Code', 'Region Name', 'Sub-region Name']]
    .drop_duplicates(subset='Country or Area')
)

# Merge matched SSP countries with UNSD to get alpha3 and region metadata
hdi_future = hdi_future.merge(
    unsd_lookup,
    left_on='Region_Mapped', right_on='Country or Area',
    how='left'
)

unmatched = hdi_future[hdi_future['ISO-alpha3 Code'].isna()]
if not unmatched.empty:
    print("Warning: SSP regions with no UNSD match:", unmatched['Region'].tolist())

hdi_future = hdi_future.rename(columns={'ISO-alpha3 Code': 'alpha3'})
hdi_future = hdi_future.drop(columns=['Country or Area', 'Region', 'Region_Mapped'])

# ── Regional fallback ─────────────────────────────────────────────────────────
# Compute mean HDI per (Scenario, Region Name) from the matched SSP countries.
# Countries not present in the SSP data will inherit their UNSD region's average.

regional_avg = (
    hdi_future.dropna(subset=['alpha3'])
    .groupby(['Scenario', 'Region Name'])[year_cols]
    .mean()
    .reset_index()
)

# All unique UNSD countries (with a valid alpha3 code)
all_unsd = (
    unsd_lookup[unsd_lookup['ISO-alpha3 Code'].notna()]
    .drop_duplicates(subset='ISO-alpha3 Code')
)

# Countries not yet covered by the SSP data
covered_alpha3 = set(hdi_future['alpha3'].dropna())
missing = all_unsd[~all_unsd['ISO-alpha3 Code'].isin(covered_alpha3)]

# Build fallback rows: one per (missing country, scenario)
scenarios = hdi_future['Scenario'].unique()
fallback_rows = []
for _, country_row in missing.iterrows():
    region = country_row['Region Name']
    alpha3 = country_row['ISO-alpha3 Code']
    for scenario in scenarios:
        match = regional_avg[
            (regional_avg['Scenario'] == scenario) &
            (regional_avg['Region Name'] == region)
        ]
        if match.empty:
            continue
        row = {'alpha3': alpha3, 'Scenario': scenario, 'Region Name': region, 'Sub-region Name': country_row['Sub-region Name']}
        for y in year_cols:
            row[y] = round(float(match.iloc[0][y]), 3)
        fallback_rows.append(row)

fallback_df = pd.DataFrame(fallback_rows) if fallback_rows else pd.DataFrame(columns=['alpha3', 'Scenario', 'Region Name', 'Sub-region Name'] + year_cols)

# Combine direct matches with fallback entries
combined = pd.concat([hdi_future, fallback_df], ignore_index=True)

# Keep only the columns needed for output
combined = combined[['alpha3', 'Scenario'] + year_cols]

# Rename columns to lowercase
combined.columns = combined.columns.str.lower()

# Save to file
out_path = os.path.join(SCRIPTS_DIR, '..', 'data', 'hdi_future.csv')
f = open(out_path, "w", encoding='utf-8')
combined.to_csv(f, index=False, lineterminator='\n')
f.close()

print(f"Saved {len(combined)} rows ({len(combined) // len(scenarios)} countries × {len(scenarios)} scenarios) to hdi_future.csv")
