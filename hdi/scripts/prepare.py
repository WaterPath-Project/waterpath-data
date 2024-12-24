import xlwings as xw
import pandas as pd
import requests
import urllib3
import sys
import ssl
from functools import reduce



countries = pd.read_csv('https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/refs/heads/master/all/all.csv', encoding='utf-8')

hdi_data = pd.read_csv("https://ourworldindata.org/grapher/human-development-index.csv", names=['name', 'alpha3', 'year', 'hdi'], skiprows=1)
hdi_data = hdi_data[hdi_data['year'] == 2022]
hdi_data = hdi_data[hdi_data['alpha3'].notna()]
hdi_data = hdi_data[hdi_data['alpha3'] != 'OWID_WRL']
hdi_data = hdi_data.drop(columns=['name','year'])

f = open(sys.path[0]+"/../data/hdi.csv", "w", encoding='utf-8')
hdi_data.to_csv(f, index=False, lineterminator='\n')
f.close() 