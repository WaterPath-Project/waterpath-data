import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import sys

# Load ISO country codes
countries = pd.read_csv('https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/refs/heads/master/all/all.csv', encoding='utf-8')

# Name mapping for countries that don't match exactly
name_mapping = {
    'Bolivia': 'Bolivia, Plurinational State of',
    'British Virgin Islands': 'Virgin Islands (British)',
    'Democratic Republic of the Congo': 'Congo, Democratic Republic of the',
    'Iran': 'Iran, Islamic Republic of',
    'Laos': "Lao People's Democratic Republic",
    'Moldova': 'Moldova, Republic of',
    'Netherlands': 'Netherlands, Kingdom of the',
    'North Korea': "Korea (Democratic People's Republic of)",
    'Palestine': 'Palestine, State of',
    'South Korea': 'Korea, Republic of',
    'Syria': 'Syrian Arab Republic',
    'Taiwan': 'Taiwan, Province of China',
    'Tanzania': 'Tanzania, United Republic of',
    'Turkey': 'Türkiye',
    'United Kingdom': 'United Kingdom of Great Britain and Northern Ireland',
    'United States': 'United States of America',
    'United States Virgin Islands': 'Virgin Islands (U.S.)',
    'Venezuela': 'Venezuela, Bolivarian Republic of',
    'Vietnam': 'Viet Nam',
    'Russia': 'Russian Federation',
    'Brunei': 'Brunei Darussalam',
    'Micronesia': 'Micronesia (Federated States of)',
}

# Read the remote Excel file
urban_future = pd.read_excel("../data/original/SSP-Extensions_Urbanization_v1.0.xlsx", sheet_name="data")

# Filter rows where Variable is "Population|Urban [Share]"
urban_future = urban_future[urban_future['Variable'] == 'Population|Urban [Share]']

# Keep only specified columns
urban_future = urban_future[['Region', 'Scenario', '2025', '2030', '2050', '2100']]

# Only keep rows that have data in all year columns (not NaN)
urban_future = urban_future.dropna(subset=['2025', '2030', '2050', '2100'])

# Apply name mapping
urban_future['Region_Mapped'] = urban_future['Region'].replace(name_mapping)

# Merge with countries to get alpha-3 codes
urban_future = urban_future.merge(countries[['name', 'alpha-3']], left_on='Region_Mapped', right_on='name', how='left')

# Drop rows without alpha3 codes (regional aggregations)
urban_future = urban_future.dropna(subset=['alpha-3'])

# Drop the redundant columns including Region and Region_Mapped
urban_future = urban_future.drop(columns=['name', 'Region_Mapped', 'Region'])
urban_future = urban_future.rename(columns={'alpha-3': 'alpha3'})

# Transform data to long format with fractionUrban column
# Each row will have: alpha3, scenario, year, fractionUrban
urban_long = []
for _, row in urban_future.iterrows():
    for year in ['2025', '2030', '2050', '2100']:
        urban_long.append({
            'alpha3': row['alpha3'],
            'scenario': row['Scenario'],
            'year': int(year),
            'fractionUrban': round(row[year] / 100, 3)  # Convert from percentage to fraction and round to 3 decimals
        })

urban_future_final = pd.DataFrame(urban_long)

# Save to file
f = open(sys.path[0]+"/../data/world_urbanisation_level0_future.csv", "w", encoding='utf-8')
urban_future_final.to_csv(f, index=False, lineterminator='\n')
f.close()
