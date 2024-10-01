import pygadm
import pandas as pd
import urllib.request, json 

data = pd.read_csv('https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/refs/heads/master/all/all.csv', encoding='utf-8')

gdf = pygadm.Names()

merged = pd.merge(gdf, data, left_on='GID_0', right_on='alpha-3').drop(['name','alpha-3','region-code','sub-region-code','intermediate-region-code'], axis=1).rename(columns={"alpha-2": "ALPHA_2", "region": "REGION", "sub-region": "SUB_REGION", "intermediate-region": "INTERMEDIATE_REGION", "country-code": "COUNTRY_CODE"}).set_index('iso_3166-2')

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