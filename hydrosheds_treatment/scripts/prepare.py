import pandas as pd
import urllib.request
import zipfile
    
url = 'https://figshare.com/ndownloader/files/31910714'
filehandle, _ = urllib.request.urlretrieve(url)
zip_file_object = zipfile.ZipFile(filehandle, 'r')
first_file = zip_file_object.namelist()[0]

file = zip_file_object.open(first_file)
wwtps = pd.read_csv(file, encoding='unicode_escape')

wwtps = wwtps[['CNTRY_ISO', 'LON_WWTP', 'LAT_WWTP', 'POP_SERVED', 'LEVEL']]
wwtps['LEVEL'] = wwtps['LEVEL'].map({'Primary': 'primary', 'Secondary': 'secondary', 'Advanced': 'tertiary'})

wwtps = wwtps.rename(columns={"CNTRY_ISO": "alpha3", "LAT_WWTP": "lat", "LON_WWTP": "lon", "POP_SERVED": "capacity", "LEVEL": "treatment_type"}, errors="raise")
wwtps.to_csv('../data/wwtp.csv', index=False, lineterminator='\n')
