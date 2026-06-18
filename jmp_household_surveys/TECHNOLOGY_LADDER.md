# Technology Ladder: Method Documentation

Below, a method is described, used to build the sanitation technology
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

> **Note on method (longitudinal ladder).** Averaging cross-sectional
> observations implicitly assumes the relationship is *symmetric* — that a
> country whose HDI falls would revert to the mix typical of poorer countries
> (open defecation resurfacing, sewer networks vanishing). That is not
> supported by the data: the pooled sample is dominated by countries *rising*
> through each HDI level, and sanitation infrastructure and behaviour are
> sticky. The ladder is therefore built **longitudinally**:
>
> 1. Take consecutive within-country survey pairs and keep only *upward* HDI
>    movements (`ΔHDI > 0.005`) — i.e. development trajectories.
> 2. Per HDI bin × context, estimate the empirical slope of each technology
>    fraction with respect to HDI as
>    $\text{slope}_t = \sum \Delta f_t \big/ \sum \Delta\text{HDI}$,
>    a weighted ratio robust to tiny HDI changes.
> 3. Anchor each context at its highest, densest cross-sectional bin (HDI
>    0.875–0.950, 80–142 observations) and integrate the slopes downward to
>    recover absolute levels, clipping to [0, 1] and renormalising each bin to
>    sum to 1.
>
> The resulting ladder encodes the *ascent* trajectory countries actually
> follow as they develop, rather than a static cross-section, and is not used
> to predict reversion under HDI decline (see the monotone ratchet in §8).

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

`project_future.py` produces `sanitation_combined_future.csv` — urban and
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
| `unop` — unimproved | `pitNoSlab`, `bucketLatrine`, `hangingToilet`, `flushOpen`, `flushUnknown`, `other`, `openDefecation` |
| `latr` — latrines | `flushPit`, `pitSlab`, `compostingToilet` |
| `sept` — septic | `flushSeptic` |
| `sewr` — sewer | `flushSewer` |

### Step-by-step: how a future row is built

**Step 1 — Determine the target HDI.**
Rather than using the SSP HDI projection directly, the algorithm computes how
much HDI is expected to *change* between 2025 and the target year, then adds
that change onto the country's most recently *measured* HDI value. This
delta-anchoring avoids distortions from any gap between the observed 2025
baseline and what the SSP scenario assumed.

**Step 2 — Get the ladder shape for that HDI.**
The technology ladder is queried twice — once for the Urban context and once
for Rural — at the target HDI value, interpolating
between the 0.025-wide bins. Because the ladder was built separately for each
context (see section 6), urban and rural populations follow different
technology mixes at the same HDI level: urban areas show faster adoption of
flush-sewer; rural areas retain a larger share of pit latrines throughout the
medium-HDI range.

**Step 3 — Scale each group to match the SSP national total.**
The ladder's raw fractions for urban and rural are combined using the
scenario-specific urban population share to produce a predicted national
average for each group (e.g. predicted national sewer share = urban fraction ×
urban ladder value + rural fraction × rural ladder value). That predicted
total is compared to the SSP target for the same group, and a single scaling
factor is computed per group. The same scaling factor is applied to *both* the
urban and rural ladder values for that group — so the relative difference
between urban and rural is preserved, but both are pushed up or down together
to hit the national target. The scaling factor is capped at 10× to guard
against extreme distortion when the denominator is very small.

**Step 4 — Renormalise.**
After scaling, the urban fractions no longer sum to exactly 1, and neither do
the rural fractions (because different groups may have been scaled by different
factors). Each context is renormalised independently so that its 12 technology
fractions sum to 1. This final step is what decouples urban and rural: the
same group-level scaling applies to both, but the renormalisation pulls each
context back to its own baseline shape.

**Year 2025** is a special case: current measured values from
`sanitation_combined.csv` are passed through unchanged, with no projection
applied. Where a country has no measured baseline for a context (an all-zero
row), that context is projected like any other year so it does not emit zeros
or act as a degenerate ratchet floor.

**containerBased accounting.** For a small number of countries the JMP source
files do not report a `containerBased` value, leaving the 12 TECH_COLS summing
to less than 1. `combine.py` computes `containerBased` as the residual
`1 − sum(TECH_COLS)` for these countries, so that every row in
`sanitation_combined.csv` satisfies `sum(TECH_COLS + containerBased) = 1`.
In the future file, TECH_COLS are always normalised to sum 1 (they represent
the conditional distribution among modelled technologies); `containerBased` is
passed through unchanged as a fixed parameter. The two files therefore use
different denominators for countries with non-zero `containerBased`, which is
expected and documented here.

### Unimproved-share ratchet (non-regression constraint)

Because the ladder encodes the cross-country *ascent* trajectory, applying it
through an HDI decline would wrongly predict regression to worse technologies.
Installed sewers, septic tanks and slabs do not disappear when HDI dips, and
abandoned open defecation rarely resurfaces. After all years for a country ×
scenario are projected, an **unimproved-share ratchet** is applied across the
year sequence:

- The combined population share of all seven `unop` technologies
  (`pitNoSlab`, `bucketLatrine`, `hangingToilet`, `flushOpen`, `flushUnknown`,
  `other`, `openDefecation`) may only *decrease* from one projected year to the
  next.
- If the projection exceeds the previous year's unimproved share, the unop
  fracs are scaled down to match it and the freed mass is redistributed
  proportionally among the five improved technologies (`flushPit`, `pitSlab`,
  `compostingToilet`, `flushSeptic`, `flushSewer`), then renormalised to sum 1.

The constraint is intentionally limited to the **unimproved aggregate** and
does not restrict transitions *within* the improved tier (e.g. sewer → septic).
SSP scenarios explicitly project such shifts for countries where decentralised
or suburban infrastructure is expected to grow, and blocking them would defeat
the SSP constraint for those countries.

The measured 2025 mix acts as the floor. The constraint overrides any SSP
target that would imply net regression to unimproved sanitation (e.g. under
SSP3 for countries with stagnating HDI).

### Fallbacks

About 49 countries (mostly small islands and territories) are absent from the
SSP Excel files. For these, the method falls back to a **delta-ladder
approach**: rather than hitting an SSP national target, the current technology
fractions are shifted by the change the ladder predicts across the HDI delta,
then clamped to [0, 1] and renormalised. A further fallback — absolute ladder
lookup with no current baseline — applies to the handful of countries that
also lack a current measured value in `sanitation_combined.csv`.

### Treatment and fixed parameters

Treatment-related parameters (`coverBury`, `fecalSludgeTreated`,
`isWatertight`, `hasLeach`) are held constant at their current values
throughout all scenarios and years.

`sewageTreated` (the share of wastewater receiving any treatment) is sourced
separately from `treatment_fractions/data/treatment_future.csv` per country,
year, and scenario. Because no urban/rural breakdown is available for
treatment, urban and rural rows receive the same national value. Countries
absent from that file fall back to the static `treatment.csv` baseline.

The remaining scalar parameters (`onsiteDumpedland`, `emptyFrequency`,
`pitAdditive`, `urine`, `twinPits`) represent model assumptions that do not
vary with HDI and are carried forward unchanged.

### Rounding

All output fractions are rounded to 3 decimal places using the
**largest-remainder (Hamilton) method**, which guarantees that every row sums
to exactly 1.000 even after rounding.

### Inputs

| Input | Content |
|---|---|
| `original_projections/SSP1-SSP5.xlsx` | National sanitation group fractions (%) and urban population share by country × decade |
| `hdi/data/hdi_future.csv` | SSP HDI projections per country × scenario at 2025, 2030, 2050, 2100 |
| `hdi/data/original/hdr-historical-data.xlsx` | Most recent measured HDI per country (delta anchor) |
| `jmp_household_surveys/data/technology_ladder.csv` | Empirical tech fractions per HDI bin × context |
| `jmp_household_surveys/data/sanitation_combined.csv` | Current-state baseline (2025 values) |

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
| Ladder is built from upward within-country transitions and applied via the unimproved-share ratchet | Encodes the ascent trajectory; the unimproved aggregate can only decrease over time, so transient HDI dips cannot increase open defecation or unimproved pit use; within-improved transitions (e.g. sewer→septic) are unconstrained |
| Treatment parameters are constant at current values | Likely underestimates treatment capacity in high-HDI futures |
| HDI is a sufficient summary statistic for sanitation drivers | Omits policy, geography, and infrastructure inherited stock |
| Low-HDI bins (0.225–0.325) have 1–2 observations | Projections for countries at very low HDI may be unreliable |
| Linear interpolation between bins | Smooth but may not reflect abrupt structural transitions |
| 49 countries not in SSP data use delta-ladder fallback | For small islands/territories, SSP constraint not applied |
