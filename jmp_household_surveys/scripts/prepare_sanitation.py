import pandas as pd
from enum import Enum
import numpy as np

class Context(Enum):
    National = 1
    Rural = 2
    Urban = 3

def jmp_sanitation():
    df_jmp = pd.read_csv('jmp_household_surveys/data/jmpSanFac.csv', encoding='latin-1', header=None)
    df_jmp.columns = ['region','alpha-2','alpha-3','numeric','context','classific_id','classification', 'fraction','source']
    # read complete and most recent survey per country
    df_surveys = pd.read_csv('jmp_household_surveys/data/surveys.csv')
    # get only most recent complete sources
    df_jmp = df_jmp[df_jmp['source'].isin(df_surveys['source'])]
    # keep only Rural and Urban
    df_jmp = df_jmp[df_jmp['context'].isin([Context.Rural.name, Context.Urban.name])] 
    
    harmon = pd.DataFrame({'classific_id': np.arange(1,18),'sanitation_type': [
             'flushSewer',
             'flushSeptic',
             'flushPit',
             'flushUnknown',
             'flushOpen',
             'pitSlab',
             'pitSlab',
             'pitSlab',
             'pitNoSlab',
             'hangingToilet',
             'bucketLatrine',
             'other',
             'compostingToilet',
             'pitSlab',
             'openDefecation',
             'other',
             'other']})
    # reclassify the sanitation categories 
    df_jmp = df_jmp.merge(harmon, on='classific_id')
    
    df_jmp_sanitation = df_jmp.groupby(['alpha-3','context','source','sanitation_type'])['fraction'].sum().reset_index()
    # normalize fractions
    df_jmp_totals = df_jmp.groupby(['alpha-3','context','source'])['fraction'].sum().reset_index()
    df_jmp_totals = df_jmp_totals.rename(columns={'fraction':'total'})
    df_jmp_sanitation = df_jmp_sanitation.merge(df_jmp_totals, on=['alpha-3','source','context'])
    df_jmp_sanitation['frac_norm'] = np.round(df_jmp_sanitation['fraction'] / df_jmp_sanitation['total'], 4) 
    
    # moves sanitation types to columns and list fractions per country
    df_jmp_country_sanitation = df_jmp_sanitation.pivot_table('frac_norm',['alpha-3','context'],'sanitation_type')
    
    #TODO: merge jmp treatment
    
    df_jmp_country_sanitation['onsiteDumpedLand'] = 0.1
    df_jmp_country_sanitation['emptyFrequency'] = 3
    df_jmp_country_sanitation['pitAdditive'] = 0
    df_jmp_country_sanitation['urine'] = 0
    df_jmp_country_sanitation['twinPits'] = 0
    
    return df_jmp_country_sanitation

df_jmp_san = jmp_sanitation()
df_jmp_san.to_csv('jmp_household_surveys/data/jmp_san_country.csv')