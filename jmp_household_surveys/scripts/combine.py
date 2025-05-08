import pandas as pd

urban = pd.read_csv("../data/sanitation_urban.csv", delimiter=";", encoding='utf-8')

rural = pd.read_csv("../data/sanitation_rural.csv", delimiter=";", encoding='utf-8')

combined = urban.merge(rural, on=["region"], suffixes=("_urb", "_rur")).reset_index(drop=True)

combined.rename(columns={'region': 'alpha3'}, inplace=True)

combined.drop(columns=['warning_urb','warning_rur'], inplace=True, errors='ignore')

combined.to_csv("../data/sanitation_combined.csv", sep=';', index=False)