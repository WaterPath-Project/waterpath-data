import pygadm
import pandas as pd
import urllib.request, json 

data = pd.read_csv('../../unsd_countries/data/unsd_countries.csv', encoding='utf-8', sep=';')

gdf = pygadm.Names()

merged = pd.merge(gdf, data, left_on='GID_0', right_on='ISO-alpha3 Code').drop(['NAME_0', 'ISO-alpha3 Code', 'Global Code', 'Global Name', 'Region Code', 'Sub-region Code', 'Intermediate Region Code', 'Least Developed Countries (LDC)', 'Land Locked Developing Countries (LLDC)', 'Small Island Developing States (SIDS)'], axis=1).rename(columns={'Country or Area': 'NAME_0', 'ISO-alpha2 Code': 'ALPHA_2', 'M49 Code': 'COUNTRY_CODE', 'Region Name': 'REGION', 'Sub-region Name': 'SUB_REGION', 'Intermediate Region Name': 'INTERMEDIATE_REGION'}).set_index('iso_3166-2')

for i, row in merged.iterrows():
    sub = pygadm.Names(admin=row['GID_0'], content_level=5)
    
    maxLevel = sub.columns[1][-1]
    merged.at[i, 'MAX_LEVEL'] = int(maxLevel)
    
    merged.at[i, 'ADMIN_LABELS'] = ''
    levels = []
    
    for x in range(1, int(maxLevel)+1):  
        with urllib.request.urlopen("https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_"+row['GID_0']+'_'+str(x)+'.json') as url:
            content = url.read().decode("utf-8")
            geo = json.loads(content)
            type_list = list(map(lambda f: f['properties']['ENGTYPE_'+str(x)], geo['features'])) 
            
            df = pd.DataFrame(type_list, columns=['ENGTYPE_'+str(x)])
            levels.append('/'.join(df['ENGTYPE_'+str(x)].drop_duplicates().to_list()))
    merged.at[i, 'ADMIN_LABELS'] = levels

f = open("../data/countries.json", "w", encoding='utf-8')
f.write(merged.to_json(indent=2, orient='records', force_ascii=False))
f.close() 