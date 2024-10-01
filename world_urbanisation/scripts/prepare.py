import xlwings as xw
import pandas as pd
import requests
import urllib3
import ssl


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


urb = get_legacy_session().get('https://population.un.org/wup/Download/Files/WUP2018-F01-Total_Urban_Rural.xls')
urb_data = pd.read_excel(urb.content, sheet_name='Data', usecols='B,D,G,H',skiprows=17, names=['name', 'iso', 'totalPopulation', 'fractionUrban'], converters={'totalPopulation': int, 'fractionUrban': float})

codes = get_legacy_session().get('https://population.un.org/wup/Download/Files/WUP2018-F00-Locations.xlsx')
code_data = pd.read_excel(codes.content, sheet_name='Location', usecols='B,D,E',skiprows=17, engine='openpyxl', names=['name', 'iso', 'alpha3'], na_values=[''])
code_data = code_data.drop(code_data[code_data['alpha3'].str.isspace() == True].index)

data = pd.merge(code_data, urb_data, how="left", on=["name", "iso"])
data['fractionUrban'] = data['fractionUrban']*0.01
data['totalPopulation'] = data['totalPopulation']*1000
f = open("../data/world-urbanisation.csv", "w", encoding='utf-8')
data.to_csv(f, index=False, lineterminator='\n')
f.close() 