import pandas as pd
import numpy as np

# Load HDIProjections and treat step as year (step 10 = 2010, etc.)
proj = pd.read_csv('hdi/data/HDIProjections(Tabelle1).csv')
proj[['country', 'step']] = proj['obs'].str.rsplit(' - ', n=1, expand=True)
proj['step'] = proj['step'].astype(int)
proj['year'] = proj['step'] + 2000

# Load SSP-Extensions (source for hdi_future.csv) - has same year columns
ssp_xl = pd.read_excel('hdi/data/original/SSP-Extensions_Human_Development_Index_v1.0.xlsx', sheet_name='data')
ssp = ssp_xl[ssp_xl['Variable'] == 'Human Development Index'].copy()

# Melt SSP to long form
year_cols = [str(y) for y in range(2010, 2076, 5)]
ssp_long = ssp.melt(id_vars=['Region', 'Scenario'], value_vars=year_cols, var_name='year', value_name='hdi_ssp')
ssp_long['year'] = ssp_long['year'].astype(int)

# Melt HDIProjections to long form
id_cols = ['country', 'step', 'year']
val_cols = ['HDI_SSP1', 'HDI_SSP2', 'HDI_SSP3', 'HDI_SSP4', 'HDI_SSP5']
proj_long = proj.melt(id_vars=id_cols, value_vars=val_cols, var_name='scenario', value_name='hdi_proj')
proj_long['scenario'] = proj_long['scenario'].str.replace('HDI_', '')

# Merge on country name + year + scenario
merged = proj_long.merge(
    ssp_long,
    left_on=['country', 'year', 'scenario'],
    right_on=['Region', 'year', 'Scenario'],
    how='inner'
)
n_countries = merged['country'].nunique()
print(f'Matched rows: {len(merged)} ({n_countries} countries)')

# Compute ratio: HDIProjections / SSP-Extensions (old scale / new scale)
merged['ratio'] = merged['hdi_proj'] / merged['hdi_ssp']

print()
print('=== Ratio (Cuaresma&Lutz / SSP-Extensions) by year ===')
print(merged.groupby('year')['ratio'].agg(['mean', 'median', 'std']).round(4).to_string())

print()
print('=== Overall ratio stats ===')
print(merged['ratio'].describe().round(4))

print()
print('=== Ratio by scenario (median) ===')
print(merged.groupby('scenario')['ratio'].median().round(4))

print()
print('=== Ratio by country (median, sorted) ===')
per_country = merged.groupby('country')['ratio'].median().sort_values()
print(per_country.round(4).to_string())

# Also: compare hdi.csv (2022) vs hdr-historical 2022
hdi_curr = pd.read_csv('hdi/data/hdi.csv')
hdr = pd.read_excel('hdi/data/original/hdr-historical-data.xlsx', sheet_name='Data')
hdi_hist = hdr[hdr['indicatorCode'] == 'hdi']
hdr_2022 = hdi_hist[hdi_hist['year'] == 2022].set_index('countryIsoCode')['actualValue']
hdi_idx = hdi_curr.set_index('alpha3')['hdi']
common = hdi_idx.index.intersection(hdr_2022.index)
diff = (hdi_idx[common] - hdr_2022[common]).abs()
print()
print('=== hdi.csv vs hdr-historical 2022 (are they the same scale?) ===')
print(f'Mean absolute diff: {diff.mean():.4f}')
print(f'Correlation: {hdi_idx[common].corr(hdr_2022[common]):.6f}')
ratio_curr = hdi_idx[common] / hdr_2022[common]
print(f'Mean ratio hdi.csv/hdr-historical: {ratio_curr.mean():.4f}')
print(f'Median ratio: {ratio_curr.median():.4f}')

# Compute what hdi.csv would look like on the Cuaresma&Lutz scale
# using the overall median ratio from the SSP comparison
overall_median_ratio = merged['ratio'].median()
print()
print(f'=== Proposed scale factor (median Cuaresma/SSP-Extensions ratio): {overall_median_ratio:.4f} ===')
print('Sample scaled hdi.csv values (ARG, AUS, NOR, BGD):')
for iso in ['ARG', 'AUS', 'NOR', 'BGD']:
    if iso in hdi_idx:
        print(f'  {iso}: {hdi_idx[iso]:.3f} -> {hdi_idx[iso]*overall_median_ratio:.3f}')
