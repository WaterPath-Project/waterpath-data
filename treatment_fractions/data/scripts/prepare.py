"""
prepare.py
----------
Generates treatment.csv (2010 baseline) and treatment_future.csv (SSP1-5 projections)
from SSP Excel files. No regression is used; all values are read directly from the xlsx.

Baseline (treatment.csv):
  SSP 2010 column — identical across all five SSPs, read from SSP1 only.
  Values are converted from % of total population to fractions.

Future (treatment_future.csv):
  Per-SSP scenario columns for years 2020–2100 (every decade).

Missing countries:
  Group A — countries absent from SSP but mappable to a dissolved predecessor state.
    Predecessor trajectories (2010 and all future decades) are used as-is.
      SRB, MNE → Yugoslavia (m49=891)
      SDN, SSD → Sudan pre-2011 (m49=736)
      CUW, BES, SXM → Netherlands Antilles (m49=530)
  Group B/C — all other countries absent from SSP: all fractions set to 0.

Outputs:
  treatment.csv         — 2010 baseline, one row per country
  treatment_future.csv  — year, ssp, alpha3, Fraction*treatment
                          SSP1-5 at years 2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100
"""

import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
ORIGINAL_DIR = DATA_DIR / "original"
REPO_ROOT = DATA_DIR.parent.parent  # waterpath-data/

SSP_FILES = {f"SSP{i}": ORIGINAL_DIR / f"SSP{i}.xlsx" for i in range(1, 6)}
UNSD_FILE = REPO_ROOT / "unsd_countries" / "data" / "unsd_countries.csv"

TREATMENT_CSV = DATA_DIR / "treatment.csv"
TREATMENT_FUTURE_CSV = DATA_DIR / "treatment_future.csv"

SHEET_TO_COL = {
    "prim": "FractionPrimarytreatment",
    "secu": "FractionSecondarytreatment",
    "tert": "FractionTertiarytreatment",
    "quat": "FractionQuarternarytreatment",
}

FUTURE_YEARS = [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100]

# Group A: countries absent from SSP mapped to a dissolved predecessor (m49)
PREDECESSOR_MAP = {
    "SRB": 891,  # Serbia → Yugoslavia
    "MNE": 891,  # Montenegro → Yugoslavia
    "SDN": 736,  # Sudan → Sudan pre-2011
    "SSD": 736,  # South Sudan → Sudan pre-2011
    "CUW": 530,  # Curaçao → Netherlands Antilles
    "BES": 530,  # Bonaire, Sint Eustatius and Saba → Netherlands Antilles
    "SXM": 530,  # Sint Maarten (Dutch part) → Netherlands Antilles
}

# Group B/C: all other countries absent from SSP — zero treatment assumed
ZERO_COUNTRIES = [
    "ATG", "BLM", "BMU", "CYM", "FSM", "GIB", "GUM", "IMN", "KIR", "MAC",
    "MAF", "MCO", "MDV", "MHL", "MNP", "MYT", "NIU", "NRU", "PLW", "PSE",
    "PYF", "SHN", "SMR", "SYC", "TUV", "VGB", "WLF",
]


def load_m49_to_alpha3():
    df = pd.read_csv(UNSD_FILE, sep=";")
    return dict(zip(df["M49 Code"].astype(int), df["ISO-alpha3 Code"]))


def load_ssp_sheet(filepath, sheet, m49_to_alpha3):
    """Load one sheet from an SSP xlsx.

    Returns:
      a3_df  — DataFrame indexed by alpha3, integer year columns, values as fractions
      m49_df — DataFrame indexed by m49 (for predecessor lookups), same columns
    """
    df = pd.read_excel(filepath, sheet_name=sheet, header=3)
    df = df.rename(columns={"ISO-CODE": "m49"})
    df = df[pd.to_numeric(df["m49"], errors="coerce").notna()].copy()
    df["m49"] = df["m49"].astype(int)
    df["alpha3"] = df["m49"].map(m49_to_alpha3)
    year_cols = [c for c in df.columns if isinstance(c, int)]
    a3_df = (
        df.dropna(subset=["alpha3"])
        .drop_duplicates("alpha3")
        .set_index("alpha3")[year_cols]
        / 100.0
    )
    m49_df = df.drop_duplicates("m49").set_index("m49")[year_cols] / 100.0
    return a3_df, m49_df


def clean(val):
    """Return 0.0 for NaN; otherwise round to 4 d.p."""
    if pd.isna(val):
        return 0.0
    return round(float(val), 4)


def get_val(ssp_data, sheet, alpha3, year):
    """Look up a single (sheet, alpha3, year) value, applying predecessor mapping."""
    a3_df, m49_df = ssp_data[sheet]
    if alpha3 in a3_df.index:
        val = a3_df.at[alpha3, year] if year in a3_df.columns else 0.0
    elif alpha3 in PREDECESSOR_MAP:
        pred_m49 = PREDECESSOR_MAP[alpha3]
        val = (
            m49_df.at[pred_m49, year]
            if (pred_m49 in m49_df.index and year in m49_df.columns)
            else 0.0
        )
    else:
        val = 0.0
    return clean(val)


def build_row(ssp_data, alpha3, year):
    """Build a dict of fraction values for one (alpha3, year) combination."""
    row = {}
    for sheet, col in SHEET_TO_COL.items():
        row[col] = get_val(ssp_data, sheet, alpha3, year)
    return row


def main():
    m49_to_alpha3 = load_m49_to_alpha3()

    # Load all SSP sheets once
    print("Loading SSP data...")
    all_ssp = {}
    for ssp_name, ssp_file in SSP_FILES.items():
        all_ssp[ssp_name] = {
            sheet: load_ssp_sheet(ssp_file, sheet, m49_to_alpha3)
            for sheet in SHEET_TO_COL
        }
        print(f"  Loaded {ssp_name}")

    # Full country set: SSP-covered + Group A + Group B/C
    base_alpha3 = set(all_ssp["SSP1"]["prim"][0].index)
    all_alpha3 = sorted(base_alpha3 | set(PREDECESSOR_MAP) | set(ZERO_COUNTRIES))

    all_cols = list(SHEET_TO_COL.values())

    # --- treatment.csv: 2010 baseline, read from SSP1 (identical across all SSPs) ---
    print("Building treatment.csv (2010 baseline from SSP1)...")
    baseline_rows = []
    for alpha3 in all_alpha3:
        row = {"alpha3": alpha3}
        row.update(build_row(all_ssp["SSP1"], alpha3, 2010))
        baseline_rows.append(row)

    baseline_df = pd.DataFrame(baseline_rows, columns=["alpha3"] + all_cols)
    baseline_df.to_csv(TREATMENT_CSV, index=False)
    print(f"  Saved {len(baseline_df)} countries to {TREATMENT_CSV}")

    # --- treatment_future.csv: per-SSP, decades 2020–2100 ---
    print("Building treatment_future.csv...")
    future_rows = []
    for ssp_name in SSP_FILES:
        for year in FUTURE_YEARS:
            for alpha3 in all_alpha3:
                row = {"year": year, "ssp": ssp_name, "alpha3": alpha3}
                row.update(build_row(all_ssp[ssp_name], alpha3, year))
                future_rows.append(row)

    future_df = pd.DataFrame(future_rows, columns=["year", "ssp", "alpha3"] + all_cols)
    future_df = future_df.sort_values(["ssp", "year", "alpha3"]).reset_index(drop=True)
    future_df.to_csv(TREATMENT_FUTURE_CSV, index=False)
    print(f"  Saved {len(future_df)} rows to {TREATMENT_FUTURE_CSV}")


if __name__ == "__main__":
    main()
