import xlwings as xw
import pandas as pd
import requests
import urllib3
import sys
import ssl
from functools import reduce
from io import BytesIO


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


urb = get_legacy_session().get('https://population.un.org/wup/assets/Download/Countries%20and%20Aggregates/WUP2025-F01-Degree-of-Urbanization_Pop_by_category.xlsx')

# Save to temporary file
with open('temp_urb.xlsx', 'wb') as f:
    f.write(urb.content)

# Read Cities and Towns sheet - get columns B (Location), E (ISO3_Code), CH (2025)
cities_towns = pd.read_excel('temp_urb.xlsx', sheet_name='Cities and Towns', usecols='B,D,E,CH', header=0)
cities_towns.columns = ['name', 'LocTypeName', 'iso', 'citiesAndTowns']
# Filter for country-level data - numeric codes < 900 are countries
cities_towns = cities_towns[cities_towns['LocTypeName'] < 900]
cities_towns = cities_towns.drop(columns=['LocTypeName'])

# Read Total sheet - get columns B (Location), E (ISO3_Code), CH (2025)
total = pd.read_excel('temp_urb.xlsx', sheet_name='Total', usecols='B,D,E,CH', header=0)
total.columns = ['name', 'LocTypeName', 'iso', 'total']
# Filter for country-level data - numeric codes < 900 are countries
total = total[total['LocTypeName'] < 900]
total = total.drop(columns=['LocTypeName'])

# Merge the two dataframes and calculate values
urb_data = pd.merge(cities_towns, total, on=['name', 'iso'], how='inner')
urb_data['totalPopulation'] = urb_data['total'] * 1000
urb_data['fractionUrban'] = urb_data['citiesAndTowns'] / urb_data['total']
urb_data = urb_data.drop(columns=['citiesAndTowns', 'total'])

# Rename 'iso' to 'alpha3' since the ISO3_Code column contains alpha-3 codes
urb_data = urb_data.rename(columns={'iso': 'alpha3'})

age_groups = get_legacy_session().get('https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/EXCEL_FILES/2_Population/WPP2024_POP_F02_1_POPULATION_5-YEAR_AGE_GROUPS_BOTH_SEXES.xlsx')

# Save to temporary file
with open('temp_age.xlsx', 'wb') as f:
    f.write(age_groups.content)

age_data = pd.read_excel('temp_age.xlsx', sheet_name='Estimates', usecols='C,E,F,K,L',skiprows=17, names=['name', 'iso', 'alpha3', 'year', 'fractionUnderFive'], na_values=[''])
age_data = age_data[age_data['alpha3'].notna()]
age_data = age_data[age_data['year'] == 2023]
age_data = age_data.drop(columns=['year', 'name', 'iso'])

# Merge urb_data with age_data on alpha3
data = pd.merge(urb_data, age_data, how="left", on=["alpha3"])

data['totalPopulation'] = data['totalPopulation'].replace(0,1)
data['fractionUnderFive'] = data['fractionUnderFive']*1000/data['totalPopulation']
data['totalPopulation'] = data['totalPopulation'].round().astype('Int64')
data['fractionUrban'] = data['fractionUrban'].astype(float).round(3)
data['fractionUnderFive'] = data['fractionUnderFive'].astype(float).round(3)
f = open(sys.path[0]+"/../data/world-population.csv", "w", encoding='utf-8')
data.to_csv(f, index=False, lineterminator='\n')
f.close()

# Clean up temporary files
import os
import time
for temp_file in ['temp_urb.xlsx', 'temp_age.xlsx']:
    if os.path.exists(temp_file):
        try:
            time.sleep(0.5)  # Brief delay to ensure file is not locked
            os.remove(temp_file)
        except PermissionError:
            pass  # Ignore if file is still locked 