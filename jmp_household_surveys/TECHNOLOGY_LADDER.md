# Sanitation technology ladder: Method documentation

Below, a method is described, used in WaterPath Toolkit to build the sanitation technology
ladder, the associated transition matrices, and how they are used to project
future sanitation technology mixes under different SSP/HDI scenarios.

---

## 1. Concept

The **technology ladder** is produced through historical observations: given a country's Human Development Index (HDI), what is the expected share of
each sanitation technology, separately for urban and
rural contexts?

In this context, HDI is used as a proxy for multiple
factors that drive sanitation transitions (eg. income, urbanisation, education, governance). Using this proxy, we can detect cross-country patterns for sanitation technology trajectories over time.

---

## 2. Data sources

### Inputs
| Dataset | File | Content |
|---|---|---|
| JMP household survey data | `jmp_household_surveys/data/jmp_sanitation_surveys.csv` | 398,854 raw rows; 17 sanitation classifications per survey × context |
| HDI historical values | `hdi/data/original/hdr-historical-data.xlsx` | UNDP HDR 1990–2023, 204 countries |
| HDI future projections | `hdi/data/hdi_future.csv` | SSP1–SSP5; 2025, 2030, 2050, 2100, 247 countries |
| ISIMIP SSP projections | `original_projections/SSP1-SSP5.xlsx` | National sanitation group fractions (%) and urban population share by country × decade |

### Output

| File | Content |
|---|---|
| `jmp_household_surveys/data/technology_ladder.csv` | Sanitation technology ladder | Technology fractions per HDI bin × context |
| `jmp_household_surveys/data/sanitation_combined.csv` | Current-state baseline (2025 values) |
| `sanitation_combined_future.csv` | 4,940 rows (247 countries × 5 SSPs × 4 years); same columns as `sanitation_combined.csv` plus leading `scenario` and `year` |
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

## 4. Survey filtering

Only **complete surveys** are used, those where the 17 sanitation technologies sum
to 1.0 (within 3 decimal points) for a given country × source ×
context combination. Incomplete surveys are discarded.

For each survey source, the context is assigned as follows:

- **Urban + Rural both present** → both are kept as-is.
- **Only National present** (no urban/rural breakdown) → the national value
  is applied to both Urban and Rural contexts.
- **Urban-only** (no Rural and no National) → kept for the Urban context
  only.  These surveys still contribute to the urban technology ladder, even
  though no matching Rural observation is available.

In the JMP dataset: 7,811 sources have all three contexts, 29 sources (all
from Botswana) have urban data only and are included under the Urban context.

---

## 5. Historical dataset composition

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

## 6. Technology ladder generation

`transition_matrix.py` builds the ladder from `sanitation_hdi_history.csv`.

### Binning

HDI values are assigned to 0.025-wide bins `[left, left + 0.025)`
labelled by their left edge:

```
hdi_bin = floor(hdi / 0.025) × 0.025
```

Bins with at least one observation span HDI 0.225–0.950 (28 bins). The three
lowest bins (0.225, 0.275, 0.325) each contain only 1–2 observations. Denser coverage begins at ~0.350 (7+
observations per bin), and the high-HDI range (0.875–0.950) is well
recorded with 80–142 observations per bin.

### Mean fractions

Within each bin, the 12 technology fractions are averaged across all
observations. Because only complete surveys are included, the fractions within
each bin sum to 1.0.

> **Note on method (longitudinal ladder).** The ladder is built from
> consecutive survey pairs where HDI *increased*, tracking how sanitation
> changes as countries actually develop. This avoids the misleading assumption that e.g. sewers and slabs would disappear
> if HDI fell. 

### Output: `technology_ladder.csv`

Columns: `hdi_bin`, `context` (Urban / Rural), the 12 technology fraction
columns, `n_observations`.

### Observed trend example (Urban context)

| HDI range | Dominant technologies |
|---|---|
| < 0.45 | `pitNoSlab`, `openDefecation`, `pitSlab` |
| 0.45–0.55 | `pitSlab` rising, `openDefecation` declining |
| 0.55–0.65 | `flushSewer` overtakes `pitNoSlab`, `openDefecation` near zero |
| 0.65–0.80 | `flushSewer` dominant (50–65 %), `pitSlab` residual |
| > 0.80 | `flushSewer` > 70 %, `openDefecation` and `pitNoSlab` effectively zero |

The rural context follows the same trajectory but shows slower adoption of flushSewer and a larger persistent `pitSlab` share throughout the medium-HDI range.

---

## 7. Projecting future sanitation mixes

### Overview

`project_future.py` produces `sanitation_combined_future.csv`, which holds urban and
rural technology fractions for each country, SSP scenario, and future year
(2025, 2030, 2050, 2100).

The method combines two sources that each answer a different question:

- **SSP Excel files** (`original_projections/SSP1–SSP5.xlsx`) tell us *how
  much* of each broad sanitation category a country is expected to use at the
  national level (e.g. "by 2050, 40 % of the population will use sewer
  systems"). These national totals act as hard targets that the projection must
  hit.
- **The technology ladder** (`technology_ladder.csv`) tells us *how* that
  national total is distributed between urban and rural populations, and which
  specific technologies appear within each broad category. For example, the
  "latrine" group is split by the ladder into flush-to-pit, pit-with-slab, and
  composting toilet in proportions that match what countries at that HDI level
  typically show.

The SSP files group the 12 individual technologies into four coarser
categories:

| Group | Technologies covered |
|---|---|
| `unop`: unimproved | `pitNoSlab`, `bucketLatrine`, `hangingToilet`, `flushOpen`, `flushUnknown`, `other`, `openDefecation` |
| `latr`: latrines | `flushPit`, `pitSlab`, `compostingToilet` |
| `sept`: septic | `flushSeptic` |
| `sewr`: sewer | `flushSewer` |

### Step-by-step: how future values are generated

**Step 1. Determine the target HDI.**
Rather than using the SSP HDI projection directly, the algorithm computes how
much HDI is expected to *change* between 2025 and the target year, then adds
that change onto the country's most recently *measured* HDI value.

**Step 2. Get the ladder shape for that HDI.**
The technology ladder is queried twice (once for the Urban context and once
for Rural) at the target HDI value, interpolating
between the 0.025-wide bins. Because the ladder was built separately for each
context (see section 6), urban and rural populations follow different
technology mixes at the same HDI level: urban areas show faster adoption of
flush-sewer, while rural areas retain a larger share of pit latrines throughout the
medium-HDI range.

**Step 3. Scale each group to match the SSP national total.**
The ladder's raw fractions for urban and rural are combined using the
scenario-specific urban population share to produce a predicted national
average for each group (e.g. predicted national sewer share = urban fraction ×
urban ladder value + rural fraction × rural ladder value). That predicted
total is compared to the SSP target for the same group, and a single scaling
factor is computed per group. The same scaling factor is applied to *both* the
urban and rural ladder values for that group, so the relative difference
between urban and rural is preserved, but both are pushed up or down together
to hit the national target.

**Step 4. Renormalise.**
After scaling, the urban fractions no longer sum to exactly 1, and neither do
the rural fractions (because different groups may have been scaled by different
factors). Each context is renormalised independently so that its 12 technology
fractions sum to 1.

For a small number of countries the JMP source
files do not report a `containerBased` value, leaving the 12 TECH_COLS summing
to less than 1. `combine.py` computes `containerBased` as the residual
`1 − sum(TECH_COLS)` for these countries.

### Unimproved-share ratchet (non-regression constraint)

Since, installed sewers, septic tanks and slabs do not disappear when HDI dips, and
abandoned open defecation rarely resurfaces. After all years for a country ×
scenario are projected, we make the following decision:

- The combined population share of all seven `unop` technologies
  (`pitNoSlab`, `bucketLatrine`, `hangingToilet`, `flushOpen`, `flushUnknown`,
  `other`, `openDefecation`) may only decrease from one projected year to the
  next.
- If the unimproved share drops, the unop
  technologies are scaled down to match the new unop percentage and any remaining points are redistributed
  among the five improved technologies (`flushPit`, `pitSlab`,
  `compostingToilet`, `flushSeptic`, `flushSewer`), then renormalised to sum 1.

### Fallbacks

About 49 countries (mostly small islands and territories) are absent from the
SSP Excel files. For these, the method falls back to the ladder values across the HDI bins, then clamped to [0, 1] and renormalised.

### Treatment and fixed parameters

Treatment-related parameters (`coverBury`, `fecalSludgeTreated`,
`isWatertight`, `hasLeach`) are held constant at their current values
throughout all scenarios and years.

`sewageTreated` (the share of wastewater receiving any treatment) is taken
separately from `treatment_fractions/data/treatment_future.csv` per country,
year, and scenario. Because no urban/rural breakdown is available for
treatment, urban and rural rows receive the same national value. Countries
absent from that file fall back to the static `treatment.csv` baseline.

The remaining parameters (`onsiteDumpedland`, `emptyFrequency`,
`pitAdditive`, `urine`, `twinPits`) represent model assumptions that do not
vary with HDI and are mostly not reported in JMP.

---

## 8. Assumptions and limitations

| Assumption | Impact |
|---|---|
| SSP national aggregates are taken as hard constraints | If JMP values are not in accord with these aggregates, data anomalies may appear |
| Ladder captures the upwards technology trajectory. The unimproved technology share can only decrease over time |
| Treatment parameters are constant at current values | Treatment data are complemented by treatment_fractions source |
| Low-HDI bins (0.225–0.325) have 1–2 observations | Projections for countries at very low HDI may be unreliable |
| 49 countries not in SSP data use ladder fallbacks | Applies mostly to small islands/territories |
