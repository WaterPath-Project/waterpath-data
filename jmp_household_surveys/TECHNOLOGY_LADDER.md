# Technology Ladder — Method Documentation

This document describes the method used to build the sanitation technology
ladder, the associated transition matrices, and how they are used to project
future sanitation technology mixes under different SSP/HDI scenarios.

---

## 1. Concept

The **technology ladder** is produced through empirical relationships: given a
country's Human Development Index (HDI), what is the expected share of
population using each sanitation technology type, separately for urban and
rural contexts?

The underlying assumption is that HDI is a reliable proxy for the bundle of
factors that drive sanitation transitions — income, urbanisation, education,
governance — and that the cross-country pattern observed across development
levels is a reasonable approximation for trajectories over time.

---

## 2. Data sources

| Dataset | File | Notes |
|---|---|---|
| JMP household survey data | `jmp_household_surveys/data/jmp_sanitation_surveys.csv` | 398,854 raw rows; 17 sanitation classifications per survey × context |
| HDI historical values | `hdi/data/original/hdr-historical-data.xlsx` | UNDP HDR 1990–2023; 204 countries |
| HDI future projections | `hdi/data/hdi_future.csv` | SSP1–SSP5; 2025, 2030, 2050, 2100; 247 countries |

---

## 3. Harmonisation of JMP classifications

The JMP data uses 17 classification IDs. These are collapsed into 12
technology buckets that correspond to the model inputs in `transform.py`:

| Classification ID | JMP label | Bucket |
|---|---|---|
| 1 | Flush/pour flush — piped sewer | `flushSewer` |
| 2 | Flush/pour flush — septic tank | `flushSeptic` |
| 3 | Flush/pour flush — pit | `flushPit` |
| 4 | Flush/pour flush — unknown destination | `flushUnknown` |
| 5 | Flush/pour flush — elsewhere / open | `flushOpen` |
| 6 | Ventilated Improved Pit (VIP) | `pitSlab` |
| 7 | Pit latrine with slab | `pitSlab` |
| 8 | Traditional latrine | `pitSlab` |
| 9 | Pit latrine without slab / open pit | `pitNoSlab` |
| 10 | Hanging / hanging latrine | `hangingToilet` |
| 11 | Bucket latrine | `bucketLatrine` |
| 12 | Other unspecified | `other` |
| 13 | Composting toilet | `compostingToilet` |
| 14 | Other improved | `pitSlab` |
| 15 | No facility / bush / field | `openDefecation` |
| 16 | Other unimproved | `other` |
| 17 | DK / missing | `other` |

---

## 4. Survey filtering and context logic

Only **complete surveys** are used — those where the 17 sanitation technologies sum
to 1.0 (within 3 decimal points) for a given country × source ×
context combination. Incomplete surveys are discarded.

For each survey source, the context is assigned as follows:

- **Urban + Rural both present** → both are kept as-is.
- **Only National present** (no urban/rural breakdown) → the national value
  is applied to both Urban and Rural contexts.
- **Urban-only** (no Rural and no National) → kept for the Urban context
  only.  These surveys still contribute to the urban technology ladder, even
  though no matching Rural observation is available.

In the JMP dataset, 7,811 sources have all three contexts; 29 sources (all
from Botswana) have urban data only and are included under the Urban context.

---

## 5. Historical dataset

`analyze.py` produces `sanitation_hdi_history.csv`:

- **3,350 rows** — one per (country × context × survey source), deduplicated
  at the (country × context × year) level when multiple surveys exist in the
  same year.
- **205 countries** covering 1980–2021.
- Each row is joined to the UNDP historical HDI value for that country–year.
  244 rows (mostly pre-1990 surveys) fall outside the HDI historical record
  and have no HDI value.
- Columns: `alpha3`, `country`, `context`, `year`, `source`, `hdi`, then the
  12 technology fraction columns.

---

## 6. Technology ladder construction

`transition_matrix.py` builds the ladder from `sanitation_hdi_history.csv`.

### Binning

HDI values are assigned to 0.025-wide half-open bins `[left, left + 0.025)`
labelled by their left edge:

```
hdi_bin = floor(hdi / 0.025) × 0.025
```

Bins with at least one observation span HDI 0.225–0.950 (28 bins). The three
lowest bins (0.225, 0.275, 0.325) each contain only 1–2 observations and
should be treated cautiously. Dense coverage begins at ~0.350 (7+
observations per bin), and the high-HDI range (0.875–0.950) is well
represented with 80–142 observations per bin.

### Mean fractions

Within each bin, the 12 technology fractions are averaged across all
observations. Because only complete surveys are included, the fractions within
each bin sum to 1.0.

### Output: `technology_ladder.csv`

Columns: `hdi_bin`, `context` (Urban / Rural), the 12 technology fraction
columns, `n_observations`.

### Observed trend (Urban context)

| HDI range | Dominant technologies |
|---|---|
| < 0.45 | `pitNoSlab`, `openDefecation`, `pitSlab` |
| 0.45–0.55 | `pitSlab` rising, `openDefecation` declining |
| 0.55–0.65 | `flushSewer` overtakes `pitNoSlab`; `openDefecation` near zero |
| 0.65–0.80 | `flushSewer` dominant (50–65 %), `pitSlab` residual |
| > 0.80 | `flushSewer` > 70 %; `openDefecation` and `pitNoSlab` effectively zero |

The rural context follows the same trajectory but is uniformly shifted left
(slower adoption of flush sewer) and shows a larger persistent `pitSlab`
share throughout the medium-HDI range.

---

## 7. Transition matrix

`transition_matrix.py` previously also produced `transition_matrix_overall.csv`
(an average annual flow matrix across all survey pairs). This file is not
consumed by any downstream script and has been moved to `data/archive/`.

---

## 8. Projecting future sanitation mixes

### Overview

`project_future.py` projects urban and rural sanitation technology mixes for
each country × SSP scenario × future year using an **SSP-constrained
technology ladder** method. This combines two information sources:

- **SSP national aggregates**: five SSP Excel files
  (`original_projections/SSP1-SSP5.xlsx`) provide projected national-level
  fractions for four sanitation groups by decade 2010–2100.
- **Technology ladder**: the empirical urban/rural split and within-group
  technology distribution from `technology_ladder.csv`.

### SSP aggregate groups

Each SSP Excel file contains four sanitation sheets (values in %; sum to 100%
per country × year):

| Sheet | Technologies included |
|---|---|
| `unop` | `pitNoSlab`, `bucketLatrine`, `hangingToilet`, `flushOpen`, `flushUnknown`, `other`, `openDefecation` |
| `latr` | `flushPit`, `pitSlab`, `compostingToilet` |
| `sept` | `flushSeptic` |
| `sewr` | `flushSewer` |

The `popurb` sheet provides urban population fraction (0–1) per country ×
decade, which is used to compute national aggregates from the urban/rural split.

### Projection algorithm

For each country × scenario × year (not 2025):

1. **Read SSP group fractions** `f_g` for g ∈ {unop, latr, sept, sewr} from the
   SSP Excel sheet (divide by 100). Year 2025 is linearly interpolated as the
   midpoint of SSP 2020 and 2030.

2. **Read urban population fraction** `p_urb` from SSP `popurb` sheet (already
   0–1). For 2025: midpoint interpolation.

3. **Target HDI** via delta-anchor:
   ```
   target_hdi = current_hdi + (hdi_future[year] - hdi_future[2025])
   ```
   `current_hdi` = most recent measured value from `hdr-historical-data.xlsx`.
   This preserves the SSP-relative HDI dynamics without being distorted by the
   absolute-level discrepancy between measured and projected 2025 HDI values.

4. **Evaluate technology ladder** at `target_hdi` for Urban and Rural contexts
   via piecewise-linear interpolation.

5. **Natural national aggregate** predicted by the ladder:
   ```
   f_g_nat = p_urb × Σ(ladder_t, Urban) + p_rur × Σ(ladder_t, Rural)
            for t ∈ group g
   ```

6. **Group scaling factor**: `k_g = f_g_ssp / f_g_nat` (capped at 10× to
   prevent extreme distortion in data-sparse corners of the parameter space).

7. **Scale**: `raw_t_ctx = ladder_t_ctx × k_g` for t in group g.

8. **Renormalise** within each context to sum = 1.

For **year 2025**: output the `sanitation_combined.csv` values directly.

**Fallback — countries not in SSP data** (approximately 49 countries, mostly
small islands and territories): delta-ladder approach — shift from
`actual_current` by the ladder change at `target_hdi`, clamp to [0,1],
renormalise.

**Fallback — no current baseline** (countries absent from
`sanitation_combined.csv`): absolute ladder lookup at `target_hdi`.

### Inputs

| Input | Content |
|---|---|
| `original_projections/SSP1-SSP5.xlsx` | National sanitation group fractions (%) and urban fraction by country × decade |
| `hdi/data/hdi_future.csv` | SSP HDI projections per country × scenario at 2025, 2030, 2050, 2100 |
| `hdi/data/original/hdr-historical-data.xlsx` | Most recent measured HDI per country (delta anchor) |
| `jmp_household_surveys/data/technology_ladder.csv` | Empirical tech fractions per HDI bin × context |
| `jmp_household_surveys/data/sanitation_combined.csv` | Current-state baseline (2025 values) |

### Rounding

All technology fraction outputs are rounded to **3 decimal places** (0.001)
using the **largest-remainder (Hamilton) method**: values are first floored to
0.001, the fractional remainders are ranked, and 0.001 is added one-by-one to
the entries with the largest remainders until the total reaches exactly 1.000.
This guarantees every row sums to exactly 1.000 regardless of floating-point
accumulation.

### Treatment and fixed parameters

Treatment parameters (`coverBury`, `fecalSludgeTreated`, `isWatertight`,
`hasLeach`) are held constant at their current values from
`sanitation_combined.csv`.

`sewageTreated` — the fraction of wastewater receiving any treatment level
(Primary + Secondary + Tertiary + Quaternary) — is set from
`treatment_fractions/data/treatment_future.csv` per country × year × scenario
(both urban and rural receive the same national-level value; countries absent
from that file fall back to `treatment_fractions/data/treatment.csv`). The
baseline `sanitation_combined.csv` likewise uses `treatment.csv` for this
column rather than the JMP survey data.

The remaining fixed parameters (`onsiteDumpedland`, `emptyFrequency`,
`pitAdditive`, `urine`, `twinPits`) are model assumptions independent of HDI
and are likewise preserved unchanged.

### Output

| File | Content |
|---|---|
| `sanitation_combined_future.csv` | 4,940 rows (247 countries × 5 SSPs × 4 years); same columns as `sanitation_combined.csv` plus leading `scenario` and `year` |

---

## 9. Assumptions and limitations

| Assumption | Impact |
|---|---|
| SSP national aggregates are taken as hard constraints | If the SSP group fractions are inconsistent with country-specific context, the within-group split may be distorted |
| Technology ladder provides the urban/rural shape | Country-specific urban–rural divergence not captured |
| Countries follow the cross-sectional HDI–sanitation relationship over time | May overstate convergence; country-specific path dependence is ignored |
| Treatment parameters are constant at current values | Likely underestimates treatment capacity in high-HDI futures |
| HDI is a sufficient summary statistic for sanitation drivers | Omits policy, geography, and infrastructure inherited stock |
| Low-HDI bins (0.225–0.325) have 1–2 observations | Projections for countries at very low HDI may be unreliable |
| Linear interpolation between bins | Smooth but may not reflect abrupt structural transitions |
| 49 countries not in SSP data use delta-ladder fallback | For small islands/territories, SSP constraint not applied |
