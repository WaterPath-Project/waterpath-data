import pandas as pd
import numpy as np

# read sanitation fractions
df_jmp = pd.read_csv('jmp_household_surveys/data/jmpSanFac.csv', encoding='latin-1', header=None)
# set column names
df_jmp.columns = ['region','alpha-2','alpha-3','numeric','context','classific_id','classification', 'fraction','source']
# extract years from source
df_jmp['year'] = df_jmp['source'].str.split(pat = '_').apply(lambda x: int(x[1]) if x[1].isdigit() else np.nan)

# keep only rural and urban
target_context = ['Urban','Rural']
df_jmp = df_jmp[df_jmp['context'].isin(target_context)]

# sum fractions 
df_frac_total = df_jmp.groupby(['alpha-3','source','context'])['fraction'].sum().reset_index()
df_frac_total['is_complete'] = df_frac_total['fraction'].between(0.9,1.1)

# check completeness. equals 3 means all national, urban and rural data is complete.
df_source_complete = df_frac_total.groupby('source')['is_complete'].apply(lambda x: sum(x) == len(target_context)).reset_index()
#df_source_complete = df_source_complete.query("is_complete")
df_source_complete['year'] = df_source_complete['source'].str.split(pat = '_').apply(lambda x: int(x[1]) if x[1].isdigit() else np.nan)
df_source_complete['alpha-3'] = df_source_complete['source'].str.split(pat = '_').apply(lambda x: x[0])

# filter complete sources and sort by descending year. take first occurrence for each country 
df_country_sources = df_source_complete.query("is_complete").sort_values(by=['year'],ascending=False).groupby('alpha-3').first()
# save to csv
df_country_sources.to_csv('jmp_household_surveys/data/surveys.csv')

