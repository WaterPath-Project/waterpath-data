# Human Development Index

## Sources

**Historical values (`data/hdi.csv`)**  
Single-year snapshot (2022) from [Our World in Data](https://ourworldindata.org/grapher/human-development-index), which mirrors the UNDP Human Development Report. Covers 193 countries. Values follow the current UNDP methodology.

**Future projections (`data/hdi_future.csv`)**  
Based on the [SSP-Extensions](https://ssp-extensions.apps.ece.iiasa.ac.at/) dataset (Cuaresma & Lutz), which provides SSP1–SSP5 projections at five-year intervals from 2025 to 2100.

The underlying SSP model was calibrated on an older HDI methodology and produces values that are systematically lower than the current UNDP scale — by roughly 10–11 % for near-term years, narrowing toward 2075 as values converge near the upper bound. Without correction, many countries would show an apparent HDI drop between 2022 (observed) and 2025 (projected), which is an artefact, not a real trend.

## Scaling correction applied to projections

To remove this discontinuity, a **per-country additive offset** is applied in `scripts/prepare_future.py`:

```
offset = hdi_observed_2022 − mean(hdi_projected_2025 across all 5 scenarios)
```

The same offset is added to **all scenarios and all future years** for that country. This means:

- The mean 2025 projection is brought into exact alignment with the 2022 observed value.
- The **relative spread between scenarios** is unchanged — SSP1 remains higher than SSP3 by exactly the same amount as before.
- The **growth trajectory** within each scenario is unchanged — only the absolute level is shifted.
- The offset is derived from a single authoritative anchor (UNDP 2022) rather than an arbitrary scale factor.

Countries not present in `hdi.csv` (e.g. overseas territories) receive no offset and retain the original SSP-Extensions values.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/prepare.py` | Downloads latest UNDP HDI data → `data/hdi.csv` |
| `scripts/prepare_future.py` | Reads SSP-Extensions Excel, applies offset correction → `data/hdi_future.csv` |
