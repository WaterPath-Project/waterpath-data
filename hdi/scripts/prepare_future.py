import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import sys

# Load ISO country codes
countries = pd.read_csv('https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/refs/heads/master/all/all.csv', encoding='utf-8')

# Name mapping for countries that don't match exactly
name_mapping = {
    'Bolivia': 'Bolivia, Plurinational State of',
    'Democratic Republic of the Congo': 'Congo, Democratic Republic of the',
    'Iran': 'Iran, Islamic Republic of',
    'Laos': "Lao People's Democratic Republic",
    'Moldova': 'Moldova, Republic of',
    'Netherlands': 'Netherlands, Kingdom of the',
    'South Korea': 'Korea, Republic of',
    'Syria': 'Syrian Arab Republic',
    'Tanzania': 'Tanzania, United Republic of',
    'Turkey': 'Türkiye',
    'United Kingdom': 'United Kingdom of Great Britain and Northern Ireland',
    'United States': 'United States of America',
    'Venezuela': 'Venezuela, Bolivarian Republic of',
    'Vietnam': 'Viet Nam',
    'Russia': 'Russian Federation',
    'Brunei': 'Brunei Darussalam',
    'North Korea': "Korea (Democratic People's Republic of)",
    'Palestine': 'Palestine, State of',
    'Micronesia': 'Micronesia (Federated States of)',
}

# Read the remote Excel file
hdi_future = pd.read_excel("../data/original/SSP-Extensions_Human_Development_Index_v1.0.xlsx", sheet_name="data")

# Filter rows where Variable is "Human Development Index"
hdi_future = hdi_future[hdi_future['Variable'] == 'Human Development Index']

# Keep only specified columns
hdi_future = hdi_future[['Region', 'Scenario', '2025', '2030', '2050', '2075']]

# Apply name mapping
hdi_future['Region_Mapped'] = hdi_future['Region'].replace(name_mapping)

# Infer 2100 values using linear regression
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
for year_col in ['2025', '2030', '2050', '2100']:
    hdi_future[year_col] = hdi_future[year_col].round(3)

# Merge with countries to get alpha-3 codes
hdi_future = hdi_future.merge(countries[['name', 'alpha-3']], left_on='Region_Mapped', right_on='name', how='left')

# Drop the redundant columns including Region
hdi_future = hdi_future.drop(columns=['name', 'Region_Mapped', 'Region'])
hdi_future = hdi_future.rename(columns={'alpha-3': 'alpha3'})

# Reorder columns
hdi_future = hdi_future[['alpha3', 'Scenario', '2025', '2030', '2050', '2100']]

# Rename columns to lowercase
hdi_future.columns = hdi_future.columns.str.lower()

# Save to file
f = open(sys.path[0]+"/../data/hdi_future.csv", "w", encoding='utf-8')
hdi_future.to_csv(f, index=False, lineterminator='\n')
f.close()
