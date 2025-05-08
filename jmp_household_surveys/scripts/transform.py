import pandas as pd
import re
import numpy as np

# Set context (National, Urban, Rural)
context = "National"

if context == 'National':
    context_treatment = 'total'
else: 
    context_treatment = context.lower()

# Load data
sat = pd.read_csv("../data/jmp_sanitation_surveys.csv")

sat = sat[sat['context'] == context]

# Derive 'year' from 'source'
sat['year'] = sat['source'].str[4:8].apply(lambda x: int(x))

# Extract 'source_ID' after " - "
sat['source_ID'] = sat['source'].apply(lambda x: x.split('_')[2])

# Rename column 'alpha.3' to 'iso3'
sat.rename(columns={'alpha.3': 'iso3'}, inplace=True)

# Harmonization mapping
harmon = pd.DataFrame({
    'classific_id': range(1, 18),
    'san': ["flushSewer", "flushSeptic", "flushPit", "flushUnknown", "flushOpen",
            "pitSlab", "pitSlab", "pitSlab", "pitNoSlab", "hangingToilet", "bucketLatrine",
            "other", "compostingToilet", "pitSlab", "openDefecation", "other", "other"]
})

# Merge with harmonized classifications
sat = sat.merge(harmon, on='classific_id')
# print(sat.head())

# Create 'uniqueID'
sat['uniqueID'] = sat['iso3'] + "." + sat['source_ID']

# Aggregate percentages
sums = sat.groupby(['iso3', 'context', 'source_ID', 'uniqueID', 'year'], as_index=False)['percentage'].sum()

# sums.to_csv("../data/sums.csv", sep='\t')
# Filter to rows where percentage == 1
complete = sums[sums['percentage'] == 1]

# Filter sat to only those in complete
sat2 = sat[sat['uniqueID'].isin(complete['uniqueID'])]


# Get most recent year per iso3
recent = sat2.groupby('iso3')['year'].max().reset_index()

st = recent.merge(sat2, on=['iso3', 'year'])

# Aggregate again
sat = st.groupby(['iso3', 'country', 'context', 'year', 'source', 'san'], as_index=False)['percentage'].sum()


sums = sat.groupby(['iso3', 'context', 'source'])['percentage'].sum().reset_index()

trt = pd.read_csv("../data/jmp_treatment.csv")
sat_filtered = sat.copy()

ag = sat_filtered[sat_filtered['context'] == context]
tr = trt[trt['Residence Type'] == context_treatment]

# Aggregation and wide-format conversion
d = ag.groupby(['san', 'iso3'])['percentage'].mean().reset_index()
w = d.pivot(index='iso3', columns='san', values='percentage').reset_index()

# Treatment coverage reshaping
tr.rename(columns={'ISO3': 'iso3'}, inplace=True)
x = tr.pivot(index='iso3', columns='Service Level', values='Coverage').reset_index()

# Sanitize and normalize treatment metrics
cb = x[['iso3', 'Disposed insitu']].copy()
cb['Disposed insitu'] = cb['Disposed insitu'].astype(float).div(100)
sl = x[['iso3', 'Sewage treated']].copy()
sl['Sewage treated'] = sl['Sewage treated'].astype(float).div(100)
et = x[['iso3', 'Faecal sludge treated']].copy()
et['Faecal sludge treated'] = et['Faecal sludge treated'].astype(float).div(100)

t = cb.merge(sl, on='iso3', how='outer').merge(et, on='iso3', how='outer')
t.columns = ['iso3', 'coverBury', 'sewageTreated', 'fecalSludgeTreated']

# Merge sanitation and treatment
out = pd.merge(w, t, on='iso3', how='outer')
out.rename(columns={'iso3': 'region'}, inplace=True)

# Ensure all expected columns exist
expected_cols = ['flushSewer','flushSeptic','flushPit','flushOpen','flushUnknown',
                 'pitSlab','pitNoSlab','bucketLatrine','hangingToilet','openDefecation',
                 'containerBased','compostingToilet','compostingTwinSlab','compostingTwinNoSlab','other']
for col in expected_cols:
    if col not in out.columns:
        out[col] = np.nan


# Select relevant final columns
cols = ['region'] + expected_cols + ['coverBury','sewageTreated','fecalSludgeTreated']
out = out[cols]

# Add calculated fields
out['isWatertight'] = out['fecalSludgeTreated']
out['hasLeach'] = out['fecalSludgeTreated']
out['onsiteDumpedLand'] = 0.1
out['emptyFrequency'] = 3
out['pitAdditive'] = 0
out['urine'] = 0
out['twinPits'] = 0

# Remove unnecessary columns
out.drop(columns=['population','excreted','compostingTwinSlab','compostingTwinNoSlab'], inplace=True, errors='ignore')

# Quality control check
tech_cols = ['flushSewer','flushSeptic','flushPit','flushOpen','flushUnknown','pitSlab','pitNoSlab',
             'compostingToilet','bucketLatrine','containerBased','hangingToilet','openDefecation','other']
check1 = out[tech_cols].sum(axis=1, skipna=True)
out['warning'] = ""
out.loc[(check1 > 1.1) | ((check1 < 0.9) & (check1 != 0)), 'warning'] = "Does not add up to 100%"

out = out[out['flushSewer'] >= 0]

out.to_csv("../data/sanitation_"+context.lower()+".csv", sep=';', index=False)