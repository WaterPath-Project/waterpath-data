"""
prepare.py
----------
Generates treatment.csv (2025 baseline) and treatment_future.csv (SSP1-5 projections)
from SSP Excel files combined with van_puijenbroek_2019.csv as an observed anchor point.

For primary, secondary, tertiary:
  Regression is fit on data points (2010, 2019, 2050, 2100) using:
    - SSP Excel sheet values at 2010, 2050, 2100 (as % of population → converted to fractions)
    - van_puijenbroek_2019.csv values at 2019 (already fractions)
  Values are predicted for 2025 and 2030 via linear least-squares regression.
  SSP values at 2050 and 2100 are used directly (not via regression).

For quaternary:
  Only SSP data exists (no 2019 anchor), so regression uses (2010, 2050, 2100).

Outputs:
  treatment.csv       — 2025 baseline (mean across SSP1-5), existing column format + quaternary
  treatment_future.csv — year, ssp, alpha3, Fraction*treatment
                         SSP1-5 at years 2025, 2030, 2050, 2100
                         ssp='baseline' at year 2025 (mean across SSP1-5)
"""

import numpy as np
import pandas as pd
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent
ORIGINAL_DIR = DATA_DIR / "original"
REPO_ROOT = DATA_DIR.parent.parent  # waterpath-data/

SSP_FILES = {f"SSP{i}": ORIGINAL_DIR / f"SSP{i}.xlsx" for i in range(1, 6)}
VP_FILE = ORIGINAL_DIR / "van_puijenbroek_2019.csv"
UNSD_FILE = REPO_ROOT / "unsd_countries" / "data" / "unsd_countries.csv"

TREATMENT_CSV = DATA_DIR / "treatment.csv"
TREATMENT_FUTURE_CSV = DATA_DIR / "treatment_future.csv"

SHEET_TO_COL = {
    "prim": "FractionPrimarytreatment",
    "secu": "FractionSecondarytreatment",
    "tert": "FractionTertiarytreatment",
    "quat": "FractionQuarternarytreatment",
}

# Years to emit in treatment_future.csv
PREDICT_YEARS = [2025, 2030, 2050, 2100]
# SSP anchor years are used directly (no regression needed)
SSP_DIRECT_YEARS = {2050, 2100}
VP_YEAR = 2019


def load_m49_to_alpha3():
    df = pd.read_csv(UNSD_FILE, sep=";")
    return dict(zip(df["M49 Code"].astype(int), df["ISO-alpha3 Code"]))


def load_ssp_sheet(filepath, sheet, m49_to_alpha3):
    """Load one treatment sheet from an SSP Excel file.

    Returns a DataFrame with alpha-3 as the index and integer year columns,
    with values as fractions (converted from % of population).
    """
    df = pd.read_excel(filepath, sheet_name=sheet, header=3)
    df = df.rename(columns={"ISO-CODE": "m49"})
    # Drop rows where m49 is not a number (e.g. stray header rows)
    df = df[pd.to_numeric(df["m49"], errors="coerce").notna()].copy()
    df["m49"] = df["m49"].astype(int)
    df["alpha3"] = df["m49"].map(m49_to_alpha3)
    df = df.dropna(subset=["alpha3"])
    df = df.drop_duplicates(subset=["alpha3"]).set_index("alpha3")
    year_cols = [c for c in df.columns if isinstance(c, int)]
    return df[year_cols] / 100.0  # % → fraction


def regress_and_predict(xs, ys, year):
    """Fit a linear least-squares regression on (xs, ys) and predict at `year`.

    Drops NaN pairs before fitting. Returns np.nan if fewer than 2 valid points.
    Result is clamped to [0, 1].
    """
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    mask = ~np.isnan(ys)
    if mask.sum() < 2:
        return np.nan
    coeffs = np.polyfit(xs[mask], ys[mask], deg=1)
    return float(np.clip(np.polyval(coeffs, year), 0.0, 1.0))


def build_projections(ssp_data, vp_series, has_vp):
    """Compute predicted values at PREDICT_YEARS for each country.

    Returns dict: {alpha3: {year: value}}
    """
    results = {}
    for alpha3 in ssp_data.index:
        row = ssp_data.loc[alpha3]
        vp_val = vp_series.at[alpha3] if (has_vp and alpha3 in vp_series.index) else None

        preds = {}
        for yr in PREDICT_YEARS:
            if yr in SSP_DIRECT_YEARS and yr in row.index and not np.isnan(row[yr]):
                # Use SSP model value directly for anchor years 2050 / 2100
                preds[yr] = float(np.clip(row[yr], 0.0, 1.0))
            else:
                if vp_val is not None and not np.isnan(vp_val):
                    xs = [2010, VP_YEAR, 2050, 2100]
                    ys = [
                        row.get(2010, np.nan),
                        vp_val,
                        row.get(2050, np.nan),
                        row.get(2100, np.nan),
                    ]
                else:
                    xs = [2010, 2050, 2100]
                    ys = [
                        row.get(2010, np.nan),
                        row.get(2050, np.nan),
                        row.get(2100, np.nan),
                    ]
                preds[yr] = regress_and_predict(xs, ys, yr)
        results[alpha3] = preds
    return results


def mean_across_ssps(all_projections, col_name, alpha3, year):
    vals = [
        all_projections[s][col_name][alpha3][year]
        for s in SSP_FILES
        if alpha3 in all_projections[s][col_name]
        and not np.isnan(all_projections[s][col_name][alpha3][year])
    ]
    return float(np.mean(vals)) if vals else np.nan




def main():
    m49_to_alpha3 = load_m49_to_alpha3()
    vp = pd.read_csv(VP_FILE).set_index("alpha3")

    print("Loading SSP projections...")
    all_projections = {}
    for ssp_name, ssp_file in SSP_FILES.items():
        print(f"  {ssp_name}")
        all_projections[ssp_name] = {}
        for sheet, col_name in SHEET_TO_COL.items():
            ssp_data = load_ssp_sheet(ssp_file, sheet, m49_to_alpha3)
            has_vp = col_name in vp.columns
            vp_col = vp[col_name] if has_vp else None
            all_projections[ssp_name][col_name] = build_projections(ssp_data, vp_col, has_vp)

    all_cols = list(SHEET_TO_COL.values())
    all_alpha3 = sorted(
        set().union(*[set(all_projections[s][all_cols[0]].keys()) for s in SSP_FILES])
    )

    # --- treatment_future.csv ---
    future_rows = []
    for ssp_name in SSP_FILES:
        for yr in PREDICT_YEARS:
            for alpha3 in all_alpha3:
                row = {"year": yr, "ssp": ssp_name, "alpha3": alpha3}
                for col_name in all_cols:
                    row[col_name] = (
                        all_projections[ssp_name][col_name]
                        .get(alpha3, {})
                        .get(yr, np.nan)
                    )
                future_rows.append(row)

    future_df = pd.DataFrame(future_rows, columns=["year", "ssp", "alpha3"] + all_cols)
    future_df = future_df.sort_values(["ssp", "year", "alpha3"]).reset_index(drop=True)
    for col in all_cols:
        future_df[col] = future_df[col].map(lambda v: round(v, 2) if pd.notna(v) else v)
    future_df.to_csv(TREATMENT_FUTURE_CSV, index=False, float_format="%.2f")
    print(f"Saved {len(future_df)} rows to {TREATMENT_FUTURE_CSV}")

    # --- treatment.csv (2025 baseline, mean across SSP1-5) ---
    baseline_rows = []
    for alpha3 in all_alpha3:
        row = {"alpha3": alpha3}
        for col_name in all_cols:
            val = mean_across_ssps(all_projections, col_name, alpha3, 2025)
            row[col_name] = val if not np.isnan(val) else np.nan
        baseline_rows.append(row)

    baseline_df = pd.DataFrame(baseline_rows, columns=["alpha3"] + all_cols)
    for col in all_cols:
        baseline_df[col] = baseline_df[col].map(lambda v: round(v, 2) if pd.notna(v) else v)
    baseline_df.to_csv(TREATMENT_CSV, index=False, float_format="%.2f")
    print(f"Saved {len(baseline_df)} countries to {TREATMENT_CSV}")


if __name__ == "__main__":
    main()
