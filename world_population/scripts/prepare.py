import xlwings as xw
import pandas as pd
import requests
import urllib3
import sys
import ssl
from functools import reduce


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


urb = get_legacy_session().get('https://population.un.org/wup/assets/Download/WUP2018-F01-Total_Urban_Rural.xls')
urb_data = pd.read_excel(urb.content, sheet_name='Data', usecols='B,D,G,H',skiprows=17, names=['name', 'iso', 'totalPopulation', 'fractionUrban'], converters={'totalPopulation': int, 'fractionUrban': float})

age_groups = get_legacy_session().get('https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/EXCEL_FILES/2_Population/WPP2024_POP_F02_1_POPULATION_5-YEAR_AGE_GROUPS_BOTH_SEXES.xlsx')
age_data = pd.read_excel(age_groups.content, sheet_name='Estimates', usecols='C,E,F,K,L',skiprows=17, names=['name', 'iso', 'alpha3', 'year', 'fractionUnderFive'], na_values=[''])
age_data = age_data[age_data['alpha3'].notna()]
age_data = age_data[age_data['year'] == 2018]
age_data = age_data.drop(columns=['alpha3','year'])

codes = get_legacy_session().get('https://population.un.org/wup/assets/Download/WUP2018-F00-LOCATIONS.xlsx')
code_data = pd.read_excel(codes.content, sheet_name='Location', usecols='B,D,E',skiprows=17, engine='openpyxl', names=['name', 'iso', 'alpha3'], na_values=[''])
code_data = code_data.drop(code_data[code_data['alpha3'].str.isspace() == True].index)

data = pd.merge(code_data, urb_data, how="left", on=["name", "iso"])
data = pd.merge(data, age_data, how="left", on=["name", "iso"])

data['fractionUrban'] = data['fractionUrban']*0.01 
data['totalPopulation'] = data['totalPopulation']*1000
data['totalPopulation'] = data['totalPopulation'].replace(0,1)
data['fractionUnderFive'] = data['fractionUnderFive']*1000/data['totalPopulation']
f = open(sys.path[0]+"/../data/world-population.csv", "w", encoding='utf-8')
data.to_csv(f, index=False, lineterminator='\n')
f.close() 