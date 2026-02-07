import pandas as pd
import os, glob
import math
import urllib.request
import zipfile


def roundPop(x):
    if not math.isnan(x):
        return round(x)
    else:
        return 0

fullfilename = os.path.join("../data/original", "ghc.zip")

if not os.path.isfile(fullfilename):
    urllib.request.urlretrieve("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL//GHS_DUC_GLOBE_R2023A/V2-0/GHS_DUC_MT_GLOBE_R2023A_V2_0.zip", fullfilename)

if not os.path.isfile("../data/GHS_DUC_GLOBE_R2023A_V2_0.xlsx"):
    with zipfile.ZipFile(fullfilename, 'r') as zip_ref:
        zip_ref.extractall("../data")

years = [ 2025 ]

for filename in os.listdir("../data"):
    for year in years:
        if "_"+str(year)+"_" in filename:
            level = filename.split("level",1)[1].replace('.csv', '')
            
            df = pd.read_csv('../data/'+filename, lineterminator='\n')
            newdf = df.iloc[:, [0, 1, 2, 8]]
            newdf.rename(columns={ newdf.columns[0]: "gid", newdf.columns[1]: "alpha3", newdf.columns[2]: "totalPopulation", newdf.columns[3]: "fractionUrban" }, inplace = True)
            newdf['totalPopulation'] = newdf['totalPopulation'].apply(lambda x: roundPop(x))
            newdf['fractionUrban'] = newdf['fractionUrban'].astype(float).round(3)
            newdf.to_csv('../data/world_urbanisation_level'+level+'.csv', index=False)              

for filename in glob.glob("../data/GHS*"):
    os.remove(filename) 
os.remove(fullfilename) 