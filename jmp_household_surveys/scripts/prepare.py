import pandas as pd
import urllib.request, json 
import requests
import sys
import json
import csv

countries = pd.read_csv('https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/refs/heads/master/all/all.csv', encoding='utf-8')

for i, row in countries.iterrows():
    url = 'https://washdata.org/data/country/'+row['alpha-3']+'/household/download'
    ineq_url = 'https://washdata.org/data/country/'+row['alpha-3']+'/inequalities/download'
    
    headers=requests.head(ineq_url, allow_redirects=True).headers
    downloadable = 'attachment' in headers.get('Content-Disposition', '')
    ineq_headers=requests.head(ineq_url, allow_redirects=True).headers
    ineq_downloadable = 'attachment' in headers.get('Content-Disposition', '')
    if downloadable:
        r = requests.get(url, allow_redirects=True)  
        file_url = r.url
        with open(sys.path[0]+'/../data/original/'+row['alpha-3']+'.xlsx', 'wb') as f:
            f.write(r.content)
            f.close()
    if ineq_downloadable:
        r = requests.get(ineq_url, allow_redirects=True)  
        file_url = r.url
        with open(sys.path[0]+'/../data/original_inequalities/'+row['alpha-3']+'-inequalities.xlsm', 'wb') as f:
            f.write(r.content)
            f.close()

with open(sys.path[0]+'/./classification_configuration.json', 'r') as conf:
    classifications = json.load(conf)
    rows_list = [];

    for i, row in countries.iterrows():
        try:
            initSheet = pd.read_excel(open(sys.path[0]+'/../data/original/'+row['alpha-3']+'.xlsx', 'rb'), sheet_name='Sanitation Data', usecols='A') 

            surveys = [x for x in initSheet.iloc[3:, 0] if str(x) != 'nan' ]

            sheet = pd.read_excel(open(sys.path[0]+'/../data/original/'+row['alpha-3']+'.xlsx', 'rb'), sheet_name='Sanitation Data', usecols=list(range(1, (len(surveys)*6)))) 

            for k in [3,4,5]:
                cols = sheet.iloc[[x['row'] for x in classifications], k::6].infer_objects(copy=False).fillna(0)
                for idx, column in enumerate(cols):
                    for classification in classifications:
                        if cols[column][classification['row']] != 0:
                            percent_value =  '%.3f'%(cols[column][classification['row']]*0.01)
                        else: 
                            percent_value = 0
                        if k == 3:
                            context = 'Urban'
                        elif k == 4:
                            context = 'Rural'
                        else:
                            context = 'National'
                        rows_list.append([row["name"], row["alpha-2"], row["alpha-3"], int(row["country-code"]), context, classification['id'], classification['label'], percent_value, surveys[idx]] )
        except:
            print('Excel file could not be parsed.')

with open(sys.path[0]+'/./data/jmpSanFac.csv', 'w', newline='') as file:
    writer = csv.writer(file)
    field = ["country", "alpha.2", "alpha.3", "numeric", "context", "classific_id", "classification", "percentage", "source"]
    writer.writerows(sorted(rows_list, key=lambda row: row[4], reverse=True))