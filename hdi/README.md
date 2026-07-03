# Human Development Index

## Sources

**Historical values (`data/hdi.csv`)**  
This file records HDI single-year values drawn from the UNDP Human Development Report for 2022. It covers 193 countries. 

**Future projections (`data/hdi_future.csv`)**  
Projection values are based on the [SSP-Extensions](https://ssp-extensions.apps.ece.iiasa.ac.at/) dataset (Cuaresma & Lutz), which provides SSP1–SSP5 projections at five-year intervals from 2025 to 2100.

The original IIASA projections were systemically lower than the UNDP baseline (and reported official projections) by 10-11%. Without correction, many countries would show an apparent HDI drop between 2022 (observed) and 2025 (projected), which is not realistic.

## Scaling correction applied to projections

To remove this discontinuity, a **per-country offset** is applied in `scripts/prepare_future.py`:

```
offset = hdi_observed_2022 − mean(hdi_projected_2025 across all 5 scenarios)
```

The same offset is added to **all scenarios and all future years** for that country. This means:

- The mean 2025 projection is aligned t with the 2022 observed value.
- The **relative spread between scenarios** is unchanged, e.g. SSP1 remains higher than SSP3 by exactly the same amount as before.
- The **growth trajectory** within each scenario is unchanged.

Countries not present in `hdi.csv` (e.g. overseas territories) receive no offset and retain the original SSP-Extensions values.

## Scripts

| Script | Function |
|---|---|
| `scripts/prepare.py` | Downloads latest UNDP HDI data → `data/hdi.csv` |
| `scripts/prepare_future.py` | Reads SSP-Extensions Excel, applies offset correction → `data/hdi_future.csv` |
