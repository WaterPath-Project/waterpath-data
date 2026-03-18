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

## 7. Transition matrices

`transition_matrix.py` also produces two transition matrix files.

### Method

For each consecutive survey pair per (country, context) with a gap ≤ 15
years, the annual rate of change for each technology fraction is computed.
Technologies whose share falls are "donors"; those that gain are "recipients".
Each donor's annual loss is distributed to recipients proportionally to their
gains, yielding a 12 × 12 flow matrix entry for that pair. Entries are then
averaged across all pairs in a subset.

This produces annual %-point flows, not transition probabilities. The diagonal
is zero by construction.

## 8. Technology phase-out thresholds

`transition_matrix.py` computes `technology_thresholds.csv`: for each
technology × context combination, the HDI level at which the technology's
share in the ladder first crosses a key fraction threshold.

**Phase-out thresholds** (fraction declining through 10%, 5%, 2%, 1%)
characterise when a sanitation type becomes marginal:

| Technology | Urban <5% HDI | Rural <5% HDI |
|---|---|---|
| `openDefecation` | ≈ 0.64 | ≈ 0.68 |
| `pitNoSlab` | ≈ 0.57 | ≈ 0.62 |
| `flushPit` | ≈ 0.61 | ≈ 0.72 |
| `other` | ≈ 0.30 | ≈ 0.36 |

**Emergence thresholds** (fraction rising through 10%, 25%, 50%) characterise
when a technology becomes dominant:

| Technology | Urban >10% HDI | Urban >50% HDI |
|---|---|---|
| `flushSewer` | ≈ 0.29 | ≈ 0.67 |

Thresholds are computed via linear interpolation on the ladder and are stored
per direction (phase_out / emergence), threshold fraction, context, and
technology.  Rows where no crossing occurs within the ladder range are omitted.

---

## 9. Technology elimination (calendar year)

`project_future.py` produces `technology_elimination.csv`: for each
(country × scenario × technology × context × threshold), the estimated
calendar year at which the projected HDI trajectory will cross the threshold
HDI from `technology_thresholds.csv`.

The HDI trajectory used is the **delta-anchored** version (see section 10 below),
interpolated linearly between the projected years 2025, 2030, 2050, 2100.
Countries whose HDI never reaches the threshold level within 2025–2100 are
omitted.

Selected results under SSP2 (median year across countries):
- Urban `openDefecation` < 5% : 2053
- SSP1 (highest development): 2045  
- SSP5 (high fossil growth, fast urbanisation): 2043

---

## 10. Projecting future sanitation mixes

### Overview and motivation

`project_future.py` derives future technology mixes using a **delta
projection** rather than a direct absolute lookup. The reason is that
`hdi_future.csv` is built partly from regional averages for countries not
covered natively by the SSP extension dataset; the resulting 2025 HDI values
can differ substantially from the most recent measured HDI (by up to ±0.36 for
some countries). Using absolute ladder values from the SSP 2025 level would
therefore project from the wrong current baseline.

### Delta-projection method

For each country × scenario × year:

1. **Anchor**: `current_hdi` = most recent measured HDI from
   `hdr-historical-data.xlsx` (one value per country, independent of scenario).
2. **Delta**: `Δhdi = hdi_future[year] − hdi_future[2025]`  
   This captures the SSP-scenario dynamics (how much HDI changes under each
   narrative) without being affected by the absolute-level discrepancy.
3. **Target**: `target_hdi = current_hdi + Δhdi`
4. **Projected fraction** = `actual_current + (ladder(target_hdi) − ladder(current_hdi))`  
   where `actual_current` is the current tech fraction from
   `sanitation_combined.csv` and `ladder(hdi)` is the piecewise-linearly
   interpolated ladder value.
5. Each fraction is **clamped** to [0, 1], and the vector is
   **renormalised** to sum to 1.

For **2025 specifically**: Δhdi = 0, and the output equals the
`sanitation_combined.csv` values directly.

For **countries not in `sanitation_combined.csv`** (22 of the 247 in
`hdi_future.csv`): an absolute ladder lookup at `hdi_future[year]` is used
instead (no current baseline available).

### Inputs

| Input | Content |
|---|---|
| `hdi/data/hdi_future.csv` | Projected HDI per country × scenario at 2025, 2030, 2050, 2100 |
| `hdi/data/original/hdr-historical-data.xlsx` | Most recent measured HDI per country (anchor) |
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

The technology ladder captures **what** facility people use. It does not
capture **how well** the resulting waste is treated, which depends on
infrastructure investment independent of HDI. The columns
`coverBury`, `sewageTreated`, `fecalSludgeTreated`, `isWatertight`, and
`hasLeach` are therefore held constant at their current (2020s) values from
`sanitation_combined.csv`.

The remaining fixed parameters (`onsiteDumpedland`, `emptyFrequency`,
`pitAdditive`, `urine`, `twinPits`) are model assumptions independent of HDI
and are likewise preserved unchanged.

### Outputs

| File | Content |
|---|---|
| `sanitation_combined_future.csv` | 4,940 rows (247 countries × 5 SSPs × 4 years); same columns as `sanitation_combined.csv` plus leading `scenario` and `year` |
| `technology_elimination.csv` | Calendar year each country × scenario × technology × context crosses each phase-out threshold |

---

## 9. Assumptions and limitations

| Assumption | Impact |
|---|---|
| Countries follow the cross-sectional HDI–sanitation relationship over time | May overstate convergence; country-specific path dependence is ignored |
| Treatment parameters are constant at current values | Likely underestimates treatment capacity in high-HDI futures |
| HDI is a sufficient summary statistic for sanitation drivers | Omits urbanisation rate, policy, geography, infrastructure inherited stock |
| Low-HDI bins (0.225–0.325) have 1–2 observations | Projections for countries at very low HDI may be unreliable |
| Linear interpolation between bins | Smooth but may not reflect abrupt structural transitions |
