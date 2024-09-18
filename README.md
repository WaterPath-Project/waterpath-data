# WaterPath Datasets

The GloWPa model installation includes a global dataset at 0.5 degree
resolution which can be used as an example. The used input datasets are
described in the sections below.

## Global Gridded Population

Data source used to create global gridded population data.

**Source: WorldPop - Population Counts - Unconstrained global mosaics
2000-2020 (1km)**  
Citation(s): WorldPop ([2018](#ref-WORLDPOP2018))

------------------------------------------------------------------------

## Global Population Dynamics

The fraction urban population at country level has been taken from the
world urbanization prospects 2018.

**Source: United Nations, Department of Economic and Social Affairs,
Population Division (2018). World Urbanization Prospects: The 2018
Revision.**  
Citation(s): United Nations, Department of Economic and Social Affairs,
Population Division ([2018](#ref-WUP2018))

------------------------------------------------------------------------

The fraction of young children at country level has been taken from the
world population prospects 2019

**Source: United Nations, Department of Economic and Social Affairs,
Population Division (2019). World Population Prospects 2019, Online
Edition. Rev. 1**  
Citation(s): United Nations, Department of Economic and Social Affairs,
Population Division ([2019](#ref-WPP2019))

## Human Development Index (HDI)

**Source: United Nations Development Programme - Human Development
Index**  
Citation(s): Programme United Nations Development ([2024](#ref-HDI2024))

## Pathogen Properties

Incidence, shedding rate and shedding duration are based on literature
and explained in Hofstra et al. ([2013](#ref-HOFSTRA2013)) for
**cryptosporidium** and Kiulia et al. ([2015](#ref-KIULIA2015)) for
**rotavirus**.

The data used to estimate the decay of cryptosporiudium in livestock
manure storage can be found in Vermeulen et al.
([2017](#ref-VERMEULEN2017)). Properties used to calculate the decay
during transport from land to water and inside rivers are described by
Vermeulen et al. ([2019](#ref-VERMEULEN2019)).

## Sanitation

The fraction of population with access to various levels of sanitation
at country level are taken from the WHO/UNICEF JMP global database. The
JPM sanitation classification has been re-classified to flushSewer(1),
flushSeptic(2), flushPit(3), flushUnknown(4), flushOpen(5), pitSlab(6),
pitNoSlab(7), hangingToilet(8), bucketLatrine(9), compostingToilet(10),
openDefecation(11) and other(12).

**Source**: <https://washdata.org/data/downloads>  
citation(s): World Health Organization and UNICEF ([2023](#ref-JMP))

## Waste Water Treatment

The treatment data has been taken from the work of Puijenbroek et al.
([2019](#ref-VANPUIJENBROEK2019)). The values can be found in the
[supplementary
data](https://ars-els-cdn-com.ezproxy.library.wur.nl/content/image/1-s2.0-S0301479718311824-mmc1.pdf)
of the paper.

------------------------------------------------------------------------

The removal and liquid fractions are taken from the [sketcher
tool](https://tools.waterpathogens.org/sketcher) of Matt Verbyla.
Ultimately, fEmitted_inEffluent_after_treatment is used in the GloWPa
model, not any of the other variables from this part.

## Hydrology

**surface runoff and river discharge**  
The VIC model is used to produce daily surface runoff and river
discharge based on WATCH forcing data. The model output is averaged over
the period 1970-2000 to produce 30-year monthly climatology ([Vermeulen
et al., 2019](#ref-VERMEULEN2019)).

------------------------------------------------------------------------

**flow direction**  
The 0.5 degrees flow direction is based in the global flow direction map
DDM30 ([Döll & Lehner, 2002](#ref-DOLL2002)) which is also used to
produce the river discharge using the VIC model.

------------------------------------------------------------------------

**river geometry and residence time**  
The river geometry equations are taken from Leopold & Maddock
([1953](#ref-LEOPOLD1953)) to calculate river width, depth and flow
velocity from river discharge. More details can be found in Vermeulen et
al. ([2019](#ref-VERMEULEN2019)).

------------------------------------------------------------------------

**water temperature**  
The monthly mean river water temperature are taken from estimates by the
VIC-RBM model framework ([Vliet et al., 2012](#ref-VLIET2012)).

------------------------------------------------------------------------

**DOC**  
The Global Nutrient Export from Watersheds (Global NEWS) model provides
estimates of river export of DOC for the world ([Harrison et al.,
2005](#ref-HARRISON2005); [Mayorga et al., 2010](#ref-MAYORGA2010)).

## Meteorology

**solar radiation and air temperature**  
Monthly climatology is created from the WATCH forcing data over the
period 1970-2000 ([Weedon et al., 2011](#ref-WATCH2011)).

## Livestock

**animal heads**  
\*Species: cattle, sheep, goats, pigs, chickens, and ducks \*
**Source**: GLW - Gridded Livestock of the World (~1km)  
Citation: Robinson et al. ([2014](#ref-ROBINSON2014))

Species: buffaloes, horses, camels, mules, and donkeys  
**Source**: FAOSTAT (heads) and GLW (spatial distribution)  
Citation: Food and Agriculture Organization of the United Nations (FAO)
([2024](#ref-FAOSTAT2024)) and Robinson et al.
([2014](#ref-ROBINSON2014))

------------------------------------------------------------------------

**body mass**  
**Source**: IPCC guidelines for National Greenhouse Gas inventories  
Citation: IPCC ([2006](#ref-IPCC2006))

------------------------------------------------------------------------

**excretion rates and prevalence**  
[Literature
Review](https://pubs.acs.org/doi/suppl/10.1021/acs.est.7b00452/suppl_file/es7b00452_si_001.pdf)

------------------------------------------------------------------------

**manure production** **Source**: IPCC guidelines for National
Greenhouse Gas inventories  
Level: continent level Citation(s): IPCC ([2006](#ref-IPCC2006))

------------------------------------------------------------------------

**intensive and extensive farming systems**  
**Source**: IMAGE model based on FAO report  
Citation(s): Bouwman et al. ([2013](#ref-BOUWMAN2013))

------------------------------------------------------------------------

**manure storage systems**  
*cattle, buffaloes, pigs*  
**Source**: IPCC Guidelines for National Greenhouse Gas Inventories
(2006)  
level: continent level  
Citation: IPCC ([2006](#ref-IPCC2006))

*chickens, ducks, sheep, goats, buffaloes, horses, asses, camels*  
**Source**: USEPA report on Global methane emissions from livestock and
poultry manure  
level: country level  
Citation: Safley et al. ([1992](#ref-USEPA1992))

# References

<div id="refs" class="references csl-bib-body hanging-indent"
line-spacing="2">

<div id="ref-BOUWMAN2013" class="csl-entry">

Bouwman, L., Goldewijk, K. K., Van Der Hoek, K. W., Beusen, A. H. W.,
Van Vuuren, D. P., Willems, J., Rufino, M. C., & Stehfest, E. (2013).
Exploring global changes in nitrogen and phosphorus cycles in
agriculture induced by livestock production over the 1900-2050 period
\[Journal Article\]. *Proceedings of the National Academy of Sciences of
the United States of America*, *110*(52), 20882–20887.
<https://doi.org/10.1073/pnas.1012878108>

</div>

<div id="ref-DOLL2002" class="csl-entry">

Döll, P., & Lehner, B. (2002). Validation of a new global 30-min
drainage direction map \[Journal Article\]. *Journal of Hydrology*,
*258*(1), 214–231.
https://doi.org/<https://doi.org/10.1016/S0022-1694(01)00565-0>

</div>

<div id="ref-FAOSTAT2024" class="csl-entry">

Food and Agriculture Organization of the United Nations (FAO). (2024).
*FAOSTAT* (Vol. 2024) \[Dataset\].
<https://www.fao.org/faostat/en/#data/QCL>

</div>

<div id="ref-HARRISON2005" class="csl-entry">

Harrison, J. A., Caraco, N., & Seitzinger, S. P. (2005). Global patterns
and sources of dissolved organic matter export to the coastal zone:
Results from a spatially explicit, global model \[Journal Article\].
*Global Biogeochemical Cycles*, *19*(4).
https://doi.org/<https://doi.org/10.1029/2005GB002480>

</div>

<div id="ref-HOFSTRA2013" class="csl-entry">

Hofstra, N., Bouwman, A. F., Beusen, A. H., & Medema, G. J. (2013).
Exploring global cryptosporidium emissions to surface water \[Journal
Article\]. *Sci Total Environ*, *442*, 10–19.
<https://doi.org/10.1016/j.scitotenv.2012.10.013>

</div>

<div id="ref-HOFSTRA2016" class="csl-entry">

Hofstra, N., & Vermeulen, L. (2016). Impacts of population growth,
urbanisation and sanitation changes on global human cryptosporidium
emissions to surface water \[Journal Article\]. *International Journal
of Hygiene and Environmental Health*, *219*.
<https://doi.org/10.1016/j.ijheh.2016.06.005>

</div>

<div id="ref-IPCC2006" class="csl-entry">

IPCC. (2006). *2006 IPCC guidelines for national greenhouse gas
inventories* (Vol. 4) \[Report\].

</div>

<div id="ref-KIULIA2015" class="csl-entry">

Kiulia, N. M., Hofstra, N., Vermeulen, L. C., Obara, M. A., Medema, G.,
& Rose, J. B. (2015). Global occurrence and emission of rotaviruses to
surface waters \[Journal Article\]. *Pathogens*, *4*(2), 229–255.
<https://www.mdpi.com/2076-0817/4/2/229>

</div>

<div id="ref-LEOPOLD1953" class="csl-entry">

Leopold, L. B., & Maddock, T. (1953). *The hydraulic geometry of stream
channels and some physiographic implications* (Vol. 252) \[Book\]. US
Government Printing Office.

</div>

<div id="ref-MAYORGA2010" class="csl-entry">

Mayorga, E., Seitzinger, S. P., Harrison, J. A., Dumont, E., Beusen, A.
H. W., Bouwman, A. F., Fekete, B. M., Kroeze, C., & Van Drecht, G.
(2010). Global nutrient export from WaterSheds 2 (NEWS 2): Model
development and implementation \[Journal Article\]. *Environmental
Modelling & Software*, *25*(7), 837–853.
https://doi.org/<https://doi.org/10.1016/j.envsoft.2010.01.007>

</div>

<div id="ref-HDI2024" class="csl-entry">

Programme United Nations Development. (2024). *Human development index*
\[Dataset\].
<https://hdr.undp.org/sites/default/files/2023-24_HDR/HDR23-24_Statistical_Annex_HDI_Table.xlsx>

</div>

<div id="ref-VANPUIJENBROEK2019" class="csl-entry">

Puijenbroek, P. J. T. M. van, Beusen, A. H. W., & Bouwman, A. F. (2019).
Global nitrogen and phosphorus in urban waste water based on the shared
socio-economic pathways \[Journal Article\]. *Journal of Environmental
Management*, *231*, 446–456.
https://doi.org/<https://doi.org/10.1016/j.jenvman.2018.10.048>

</div>

<div id="ref-ROBINSON2014" class="csl-entry">

Robinson, T. P., Wint, G. R. W., Conchedda, G., Van Boeckel, T. P.,
Ercoli, V., Palamara, E., Cinardi, G., D’Aietti, L., Hay, S. I., &
Gilbert, M. (2014). Mapping the global distribution of livestock
\[Journal Article\]. *PLOS ONE*, *9*(5), e96084.
<https://doi.org/10.1371/journal.pone.0096084>

</div>

<div id="ref-USEPA1992" class="csl-entry">

Safley, L. M., Casada, M. E., Woodbury, J. W., & Roos, K. F. (1992).
*Global methane emissions from livestock and poultry manure* \[Report\].
United States Environmental Protection Agency (USEPA).

</div>

<div id="ref-WUP2018" class="csl-entry">

United Nations, Department of Economic and Social Affairs, Population
Division. (2018). *World urbanization prospects: The 2018 revision,
online edition* \[Dataset\]. United Nations.
<https://population.un.org/wup/Download/>

</div>

<div id="ref-WPP2019" class="csl-entry">

United Nations, Department of Economic and Social Affairs, Population
Division. (2019). *World population prospects 2019, online edition. Rev.
1* \[Dataset\]. United Nations.
<https://population.un.org/wpp2019/Download/Standard/Population/>

</div>

<div id="ref-VERMEULEN2017" class="csl-entry">

Vermeulen, L. C., Benders, J., Medema, G., & Hofstra, N. (2017). Global
cryptosporidium loads from livestock manure \[Journal Article\].
*Environmental Science & Technology*, *51*(15), 8663–8671.
<https://doi.org/10.1021/acs.est.7b00452>

</div>

<div id="ref-VERMEULEN2019" class="csl-entry">

Vermeulen, L. C., van Hengel, M., Kroeze, C., Medema, G., Spanier, J.
E., van Vliet, M. T. H., & Hofstra, N. (2019). Cryptosporidium
concentrations in rivers worldwide. *Water Research*, *149*, 202–214.
https://doi.org/<https://doi.org/10.1016/j.watres.2018.10.069>

</div>

<div id="ref-VLIET2012" class="csl-entry">

Vliet, M. T. H. van, Yearsley, J. R., Franssen, W. H. P., Ludwig, F.,
Haddeland, I., Lettenmaier, D. P., & Kabat, P. (2012). Coupled daily
streamflow and water temperature modelling in large river basins
\[Journal Article\]. *Hydrol. Earth Syst. Sci.*, *16*(11), 4303–4321.
<https://doi.org/10.5194/hess-16-4303-2012>

</div>

<div id="ref-WATCH2011" class="csl-entry">

Weedon, G. P., Gomes, S., Viterbo, P., Shuttleworth, W. J., Blyth, E.,
Österle, H., Adam, J. C., Bellouin, N., Boucher, O., & Best, M. (2011).
Creation of the WATCH forcing data and its use to assess global and
regional reference crop evaporation over land during the twentieth
century \[Journal Article\]. *Journal of Hydrometeorology*, *12*(5),
823–848. https://doi.org/<https://doi.org/10.1175/2011JHM1369.1>

</div>

<div id="ref-JMP" class="csl-entry">

World Health Organization and UNICEF. (2023). *Estimates for drinking
water, sanitation and hygiene services by country (2000-2022)*
\[Dataset\]. <https://washdata.org/data/downloads>

</div>

<div id="ref-WORLDPOP2018" class="csl-entry">

WorldPop. (2018). *Global high resolution population denominators
project* \[Dataset\]. School of Geography; Environmental Science,
University of Southampton; Department of Geography; Geosciences,
University of Louisville; Departement de Geographie, Universite de
Namur; Center for International Earth Science Information Network
(CIESIN), Columbia University; University of Southampton.
<https://doi.org/10.5258/SOTON/WP00647>

</div>

</div>

