import pandas as pd
import numpy as np
import requests
import urllib3
import sys
import ssl
from sklearn.linear_model import LinearRegression


class CustomHttpAdapter (requests.adapters.HTTPAdapter):

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)


def get_legacy_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  
    session = requests.session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session


# Download urbanization data
urb = get_legacy_session().get('https://population.un.org/wup/assets/Download/Countries%20and%20Aggregates/WUP2025-F01-Degree-of-Urbanization_Pop_by_category.xlsx')

# Save to temporary file
with open('temp_urb_future.xlsx', 'wb') as f:
    f.write(urb.content)

# Process data for each year: 2030, 2050
years = {
    2030: 'CM',
    2050: 'DG'
}

future_data_list = []

for year, col in years.items():
    # Read Cities and Towns sheet
    cities_towns = pd.read_excel('temp_urb_future.xlsx', sheet_name='Cities and Towns', 
                                  usecols=f'B,D,E,{col}', header=0)
    cities_towns.columns = ['name', 'LocTypeName', 'iso', 'citiesAndTowns']
    # Filter for country-level data - numeric codes < 900 are countries
    cities_towns = cities_towns[cities_towns['LocTypeName'] < 900]
    cities_towns = cities_towns.drop(columns=['LocTypeName'])

    # Read Total sheet
    total = pd.read_excel('temp_urb_future.xlsx', sheet_name='Total', 
                         usecols=f'B,D,E,{col}', header=0)
    total.columns = ['name', 'LocTypeName', 'iso', 'total']
    # Filter for country-level data - numeric codes < 900 are countries
    total = total[total['LocTypeName'] < 900]
    total = total.drop(columns=['LocTypeName'])

    # Merge and calculate
    urb_data = pd.merge(cities_towns, total, on=['name', 'iso'], how='inner')
    urb_data['totalPopulation'] = urb_data['total'] * 1000
    urb_data['fractionUrban'] = urb_data['citiesAndTowns'] / urb_data['total']
    urb_data = urb_data.drop(columns=['citiesAndTowns', 'total'])
    urb_data = urb_data.rename(columns={'iso': 'alpha3'})
    urb_data['year'] = year
    
    future_data_list.append(urb_data)

# Download age groups data
age_groups = get_legacy_session().get('https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/EXCEL_FILES/2_Population/WPP2024_POP_F02_1_POPULATION_5-YEAR_AGE_GROUPS_BOTH_SEXES.xlsx')

# Save to temporary file
with open('temp_age_future.xlsx', 'wb') as f:
    f.write(age_groups.content)

# Read age data for 2030 and 2050 from Projections sheet
age_data_list = []
for year in [2030, 2050]:
    age_data = pd.read_excel('temp_age_future.xlsx', sheet_name='Medium variant', 
                             usecols='C,E,F,K,L', skiprows=17, 
                             names=['name', 'iso', 'alpha3', 'year', 'fractionUnderFive'], 
                             na_values=[''])
    age_data = age_data[age_data['alpha3'].notna()]
    age_data = age_data[age_data['year'] == year]
    age_data = age_data.drop(columns=['name', 'iso'])
    age_data_list.append(age_data)

# Combine all future data
all_future_data = pd.concat(future_data_list, ignore_index=True)

# Merge with age data
all_age_data = pd.concat(age_data_list, ignore_index=True)
data = pd.merge(all_future_data, all_age_data, on=['alpha3', 'year'], how='left')

# Calculate fractionUnderFive
data['totalPopulation'] = data['totalPopulation'].replace(0, 1)
data['fractionUnderFive'] = data['fractionUnderFive'] * 1000 / data['totalPopulation']

# Now calculate 2100 projections using linear regression
# Get historical + future data points for each country
data_2025 = pd.read_csv(sys.path[0] + "/../data/world-population.csv")
data_2025['year'] = 2025

# Combine with future data for regression
regression_data = pd.concat([
    data_2025[['name', 'alpha3', 'year', 'totalPopulation', 'fractionUrban', 'fractionUnderFive']],
    data[['name', 'alpha3', 'year', 'totalPopulation', 'fractionUrban', 'fractionUnderFive']]
], ignore_index=True)

# Calculate 2100 for each country using regression
data_2100_list = []

for alpha3 in data['alpha3'].unique():
    country_data = regression_data[regression_data['alpha3'] == alpha3].copy()
    
    if len(country_data) >= 2:  # Need at least 2 points for regression
        country_data = country_data.sort_values('year')
        
        # Get the name
        country_name = country_data['name'].iloc[0]
        
        # Regression for totalPopulation
        X = country_data[['year']].values
        y_pop = country_data['totalPopulation'].values
        model_pop = LinearRegression()
        model_pop.fit(X, y_pop)
        pop_2100 = max(0, model_pop.predict([[2100]])[0])  # Don't allow negative population
        
        # Regression for fractionUrban (constrain between 0 and 1)
        y_urb = country_data['fractionUrban'].values
        model_urb = LinearRegression()
        model_urb.fit(X, y_urb)
        urb_2100 = np.clip(model_urb.predict([[2100]])[0], 0, 1)
        
        # Regression for fractionUnderFive (constrain between 0 and 1)
        y_u5 = country_data['fractionUnderFive'].values
        model_u5 = LinearRegression()
        model_u5.fit(X, y_u5)
        u5_2100 = np.clip(model_u5.predict([[2100]])[0], 0, 1)
        
        data_2100_list.append({
            'name': country_name,
            'alpha3': alpha3,
            'year': 2100,
            'totalPopulation': pop_2100,
            'fractionUrban': urb_2100,
            'fractionUnderFive': u5_2100
        })

data_2100 = pd.DataFrame(data_2100_list)

# Combine 2030, 2050, and 2100
final_data = pd.concat([data, data_2100], ignore_index=True)

# Sort by alpha3 and year
final_data = final_data.sort_values(['alpha3', 'year'])

# Round the values
final_data['totalPopulation'] = final_data['totalPopulation'].round().astype('Int64')
final_data['fractionUrban'] = final_data['fractionUrban'].astype(float).round(3)
final_data['fractionUnderFive'] = final_data['fractionUnderFive'].astype(float).round(3)

# Write to CSV
f = open(sys.path[0] + "/../data/world-population-future.csv", "w", encoding='utf-8')
final_data.to_csv(f, index=False, lineterminator='\n')
f.close()

# Clean up temporary files
import os
import time
for temp_file in ['temp_urb_future.xlsx', 'temp_age_future.xlsx']:
    if os.path.exists(temp_file):
        try:
            time.sleep(0.5)  # Brief delay to ensure file is not locked
            os.remove(temp_file)
        except PermissionError:
            pass  # Ignore if file is still locked

print(f"Generated {len(final_data)} rows of future population data")
