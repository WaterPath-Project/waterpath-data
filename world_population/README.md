# Population baseline and projections: Method documentation

WaterPath Toolkit produces human emissions baseline and future projections (tabular and raster), using external sources and key assumptions.

## Tabular data

### Sources:
- **Country-level population counts, fraction under 5** taken from World Population Prospects and UNDP
  - world-population CSV: `world_population/data/world-population.csv`
  - HDI CSV: `hdi/data/hdi.csv`
- **National and sub-national baseline** urbanization rates from Copernicus and **national only SSP projections** from ISIMIP: `world_admin_units_urbanisation_degree/data/world_urbanisation_level{N}.csv` and `world_admin_units_urbanisation_degree/data/world_urbanisation_level0_future.csv` respectively.

### Processing
 1. Read selected area GADM shapefile
 2. Build mappings: gid -> iso.
 3. Bootstrap isodata.csv using data from `world-population.csv` and `hdi.csv`, excluding the fractionUrban for now.
 4. To determine fractionUrban:
    - Baseline (national and sub‑national) is taken from the admin‑level `world_admin_units_urbanisation_level{N}.csv`.
    - Projection (national): when generating a country‑level scenario the service fetches `world_urbanisation_level0_future.csv` (by SSP/year).
    - Projection (sub‑national): fraction is left as the baseline national value (no downscaling to sub‑areas is performed at the moment, as Copernicus does not provide future projections).

## Raster data

### Sources:
- **Raster population data** taken from WorldPop (2025) at 1km resolution, stored as in-memory tif files in the WaterPath Data Service (e.g. `FuturePop_<SSP>_<year>_1km_v0_2.tif`).

### Processing:
 1. Read selected area GADM shapefile and generated isodata.csv.
 2. Build mappings: gid -> iso.
 3. Auto-select target resolution (approx 100 pixels across bbox diagonal).
 4. Rasterize polygons in `isoraster.tif` with pixel values equal to `iso`.
 5. Calculate per-pixel urban fraction using `fraction_urban_pop`.
 6. Resample the source population raster (WorldPop, 1 km pixels) onto the target grid. The challenge is that the source and target pixels cover different physical areas, so raw population numbers across pixels cannot be directly averaged. Instead, we: (a) divide each source pixel's population by its physical area in km² to get a population density (people per km²); (b) average those densities across all source pixels that overlap each target pixel, proportional to how much of each source pixel falls inside the target pixel; (c) multiply the resulting density by the target pixel's physical area to get a people count for that pixel. Ocean or missing source pixels are treated as zero population (see China issue) so they do not inflate the average in coastal or partially-covered pixels. This approach preserves the total population across the study area to within rounding at the edges.
 7. Split per-pixel counts into `pop_urban.tif` and `pop_rural.tif` using the per-pixel urban fraction.

## Key assumption and challenges
- Source nodata pixels are treated as zero before resampling so that area-weighted resampling preserves total population.
- Find a better way to do urban fraction projections.
- Should we use WorldPop for baseline population numbers?