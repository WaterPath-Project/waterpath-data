"""
Generate livestock_projections.csv from SSP animal stock projections.

Inputs
------
data/original/future/animals_specs_SSP{1-5}.csv
    Semi-colon delimited, 2-line comment header.  Contains M49 country codes,
    years (2010-2050), head counts and production-system fractions for 10
    species groups per SSP scenario.

data/original/FAOSTAT_country_groups.csv
    Maps M49 codes to ISO3 alpha-3 country codes.

data/original/FAOSTAT_data.csv
    Historical FAOSTAT livestock stocks used to derive the sheep / goat split
    ratio per country.

Output
------
data/livestock_future.csv
    Columns: scenario, year, alpha3 then per-species:
        <species>          – head count
        <species>_i        – fraction in intensive systems
        <species>_fgi      – fraction grazing intensive
        <species>_fge      – fraction grazing pastoral (extensive)
        <species>_foi      – fraction other intensive
        <species>_foe      – fraction other pastoral (extensive)
        <species>_e        – 1 - <species>_i  (explicit extensive fraction)

    Species (in column order): cattle, buffaloes, pigs, poultry, sheep, goats,
    horses, asses, mules, camels.

    Years reported: 2025 (linear interpolation of 2020 and 2030), 2030, 2050,
    2100 (held constant at 2050 – source data does not extend beyond 2050).

Notes
-----
- dairy cattle (species 2) are excluded from output.
- sheep and goats are split from the combined "6_sheep&goats" column using the
  per-country goat fraction derived from the most-recent FAOSTAT stocks year.
  Countries absent from FAOSTAT stocks default to a 50 / 50 split.
- Both sheep and goats inherit the same production-system fractions from
  species 6 (the source data provides no per-species split of fractions within
  the sheep&goats group).
"""

import pandas as pd
from io import StringIO
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SSP_FILES = {
    f"SSP{i}": BASE / f"data/original/future/animals_specs_SSP{i}.csv" for i in range(1, 6)
}

# Mapping: SSP species number → output name (2=dairy excluded)
NUM_TO_SPECIES = {
    1: "cattle",
    3: "buffaloes",
    4: "pigs",
    5: "poultry",
    6: "sheep_goats",   # split into sheep + goats below
    7: "horses",
    8: "asses",
    9: "mules",
    10: "camels",
}

# SSP fraction column suffix → output column suffix
FRAC_MAP = {
    "Fr_intens":           "_i",
    "Fr_grazing_intens":   "_fgi",
    "Fr_grazing_pastoral": "_fge",
    "Fr_other_intens":     "_foi",
    "Fr_other_pastoral":   "_foe",
}

OUTPUT_YEARS = [2030, 2050, 2100]

# Final column order for species (sheep_goats is expanded into sheep then goats)
SPECIES_ORDER = [
    "cattle", "buffaloes", "pigs", "poultry",
    "sheep", "goats",
    "horses", "asses", "mules", "camels",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_ssp(path: Path) -> pd.DataFrame:
    """Read an animals_specs_SSP*.csv file into a tidy DataFrame."""
    with open(path, "r") as fh:
        lines = fh.readlines()
    # Real header embedded in line 1 after the path prefix
    header_line = lines[1].strip()
    idx = header_line.find("isocode;")
    header = header_line[idx:].split(";")
    data_body = "".join(lines[2:])
    df = pd.read_csv(StringIO(";".join(header) + "\n" + data_body), sep=";")
    return df


def build_m49_lookup() -> dict[int, str]:
    """Return {m49_int: iso3} from FAOSTAT_country_groups.csv."""
    fg = pd.read_csv(BASE / "data/original/FAOSTAT_country_groups.csv")
    rows = fg[["M49 Code", "ISO3 Code"]].drop_duplicates()
    lookup: dict[int, str] = {}
    for _, row in rows.iterrows():
        if pd.notna(row["M49 Code"]) and pd.notna(row["ISO3 Code"]):
            lookup[int(round(row["M49 Code"]))] = str(row["ISO3 Code"]).strip()
    return lookup


def build_goat_fractions() -> pd.Series:
    """
    Return a Series indexed by ISO3 giving the goat fraction of combined
    sheep+goats stocks, using the most recent FAOSTAT year per country.
    Defaults to 0.5 for countries not present.
    """
    fd = pd.read_csv(BASE / "data/original/FAOSTAT_data.csv")
    sg = fd[
        fd["Item"].isin(["Sheep", "Goats"]) & (fd["Element"] == "Stocks")
    ][["Area Code (ISO3)", "Item", "Year", "Value"]].copy()

    # Most recent year per country
    most_recent = sg.groupby("Area Code (ISO3)")["Year"].max().reset_index()
    sg = sg.merge(most_recent, on=["Area Code (ISO3)", "Year"])

    piv = sg.pivot_table(index="Area Code (ISO3)", columns="Item", values="Value")
    piv = piv.rename(columns={"Goats": "goats", "Sheep": "sheep"})

    piv["goats"] = piv.get("goats", pd.Series(dtype=float))
    piv["sheep"] = piv.get("sheep", pd.Series(dtype=float))
    total = piv["goats"].fillna(0) + piv["sheep"].fillna(0)
    goat_frac = piv["goats"].fillna(0) / total.replace(0, float("nan"))
    goat_frac = goat_frac.fillna(0.5)   # default 50/50 when no data
    return goat_frac


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_ssp(scenario: str, ssp_df: pd.DataFrame,
                m49_lookup: dict, goat_frac: pd.Series) -> pd.DataFrame:
    """
    Build long-form projection rows for one SSP scenario.
    Returns a DataFrame with columns [scenario, year, alpha3, ...species cols...].
    """
    # Map M49 → ISO3; drop rows without a match
    ssp_df = ssp_df.copy()
    ssp_df["alpha3"] = ssp_df["isocode"].map(lambda x: m49_lookup.get(int(x)))
    ssp_df = ssp_df.dropna(subset=["alpha3"])

    # Build the set of source years needed for interpolation / selection
    # We need 2020 and 2030 for 2025; 2030, 2050 directly; 2100 = hold at 2050
    source_years_needed = {2020, 2030, 2050}
    ssp_df = ssp_df[ssp_df["year"].isin(source_years_needed)].copy()

    # -----------------------------------------------------------------------
    # Collect per-species head counts and fractions for each source year
    # -----------------------------------------------------------------------
    # We'll build one row per (country, source_year) with renamed columns,
    # then derive the output years.

    records = []
    key_cols = ["alpha3", "year"]

    species_col_sets = {}  # species_name → list of output col names

    for num, sp in NUM_TO_SPECIES.items():
        head_col = f"{num}_cattle" if num == 1 else None
        # head count column names in SSP files
        if num == 1:
            head_raw = "1_cattle"
        elif num == 2:
            head_raw = "2_dairy"
        elif num == 3:
            head_raw = "3_buffaloes"
        elif num == 4:
            head_raw = "4_pigs"
        elif num == 5:
            head_raw = "5_poultry"
        elif num == 6:
            head_raw = "6_sheep&goats"
        elif num == 7:
            head_raw = "7_horses"
        elif num == 8:
            head_raw = "8_asses"
        elif num == 9:
            head_raw = "9_mules"
        elif num == 10:
            head_raw = "10_camels"

        frac_cols_map = {}  # output_col → raw_col
        for raw_suf, out_suf in FRAC_MAP.items():
            raw_col = f"{num}_{raw_suf}"
            out_col = f"{sp}{out_suf}"
            frac_cols_map[out_col] = raw_col

        species_col_sets[sp] = {
            "head_raw": head_raw,
            "frac_cols_map": frac_cols_map,
        }

    # Build a wide table indexed by (alpha3, year)
    pivot = ssp_df.set_index(["alpha3", "year"])

    # -----------------------------------------------------------------------
    # Expand all species into renamed columns
    # -----------------------------------------------------------------------
    rows_by_key = {}  # (alpha3, year) → dict
    for (alpha3, yr), row in pivot.iterrows():
        d: dict = {"alpha3": alpha3, "year": yr}
        for sp, spec in NUM_TO_SPECIES.items():
            info = species_col_sets[spec]
            head_val = row.get(info["head_raw"], 0.0)

            if spec == "sheep_goats":
                gf = goat_frac.get(alpha3, 0.5)
                d["_sg_total"] = head_val   # temporary: split below
                d["_sg_gf"] = gf
                for out_col, raw_col in info["frac_cols_map"].items():
                    # store as sheep_ and goats_ with same value
                    sg_out = out_col.replace("sheep_goats", "sheep")
                    gg_out = out_col.replace("sheep_goats", "goats")
                    val = row.get(raw_col, 0.0)
                    d[sg_out] = val
                    d[gg_out] = val
            else:
                d[spec] = head_val
                for out_col, raw_col in info["frac_cols_map"].items():
                    d[out_col] = row.get(raw_col, 0.0)

        rows_by_key[(alpha3, yr)] = d

    base_df = pd.DataFrame.from_records(list(rows_by_key.values()))
    base_df = base_df.set_index(["alpha3", "year"])

    # Now separate sheep / goats head counts from the merged column
    base_df["sheep"] = base_df["_sg_total"] * (1 - base_df["_sg_gf"])
    base_df["goats"] = base_df["_sg_total"] * base_df["_sg_gf"]
    base_df = base_df.drop(columns=["_sg_total", "_sg_gf"])

    # Compute _e = 1 - _i for all species
    for sp in SPECIES_ORDER:
        i_col = f"{sp}_i"
        e_col = f"{sp}_e"
        if i_col in base_df.columns:
            base_df[e_col] = 1.0 - base_df[i_col]

    # -----------------------------------------------------------------------
    # Derive output years
    # -----------------------------------------------------------------------
    out_frames = []
    for out_yr in OUTPUT_YEARS:
        if out_yr == 2025:
            # Linear interpolation between 2020 and 2030
            y2020 = base_df.xs(2020, level="year") if 2020 in base_df.index.get_level_values("year") else None
            y2030 = base_df.xs(2030, level="year") if 2030 in base_df.index.get_level_values("year") else None
            if y2020 is not None and y2030 is not None:
                common = y2020.index.intersection(y2030.index)
                interp = (y2020.loc[common] + y2030.loc[common]) / 2.0
                interp = interp.reset_index().rename(columns={"alpha3": "alpha3"})
                interp["scenario"] = scenario
                interp["year"] = out_yr
                out_frames.append(interp)
        elif out_yr == 2100:
            # Hold 2050 constant
            y2050 = base_df.xs(2050, level="year").reset_index() if 2050 in base_df.index.get_level_values("year") else None
            if y2050 is not None:
                y2050 = y2050.copy()
                y2050["scenario"] = scenario
                y2050["year"] = out_yr
                out_frames.append(y2050)
        else:
            if out_yr in base_df.index.get_level_values("year"):
                yr_df = base_df.xs(out_yr, level="year").reset_index()
                yr_df["scenario"] = scenario
                yr_df["year"] = out_yr
                out_frames.append(yr_df)

    result = pd.concat(out_frames, ignore_index=True)
    return result


def main():
    m49_lookup = build_m49_lookup()
    goat_frac = build_goat_fractions()

    # Build ordered output columns
    value_cols = []
    for sp in SPECIES_ORDER:
        value_cols.append(sp)
        value_cols.append(f"{sp}_i")
        value_cols.append(f"{sp}_fgi")
        value_cols.append(f"{sp}_fge")
        value_cols.append(f"{sp}_foi")
        value_cols.append(f"{sp}_foe")
        value_cols.append(f"{sp}_e")
    output_cols = ["scenario", "year", "alpha3"] + value_cols

    all_frames = []
    for scenario, path in SSP_FILES.items():
        print(f"Processing {scenario} ...")
        ssp_df = read_ssp(path)
        frame = process_ssp(scenario, ssp_df, m49_lookup, goat_frac)
        all_frames.append(frame)

    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.sort_values(["scenario", "year", "alpha3"]).reset_index(drop=True)

    # Select and reorder columns; fill any missing value cols with 0
    for col in value_cols:
        if col not in combined.columns:
            combined[col] = 0.0
    combined = combined[output_cols]

    # Round head counts to integers, fractions to 3 decimal places
    head_cols = [sp for sp in SPECIES_ORDER]
    frac_cols = [c for c in value_cols if c not in head_cols]
    combined[head_cols] = combined[head_cols].round(0).astype("Int64")
    combined[frac_cols] = combined[frac_cols].round(3)

    out_path = BASE / "data/livestock_future.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nWrote {len(combined)} rows to {out_path}")
    print(f"Scenarios: {sorted(combined['scenario'].unique())}")
    print(f"Years:     {sorted(combined['year'].unique())}")
    print(f"Countries: {combined['alpha3'].nunique()}")
    print(f"Columns:   {len(combined.columns)}")


if __name__ == "__main__":
    main()
