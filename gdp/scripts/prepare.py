#!/usr/bin/env python3
"""Generate observed and SSP GDP-per-capita data for WaterPath QMRA.

Outputs (under ../data):
- gdp.csv: observed 2024 GDP per capita, PPP (constant 2021 international $)
- gdp_future.csv: SSP1-5 projections anchored to the observed 2024 value
- assumptions.csv: assumptions consumed by the WaterPath data service

The script downloads and caches the official IIASA SSP Basic Drivers release
3.2 workbook and World Bank API responses under ../data/original. The IIASA
workbook is not intended for redistribution; data/original is gitignored.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PACKAGE_DIR / "data"
ORIGINAL_DIR = DATA_DIR / "original"

IIASA_URL = (
    "https://files.ece.iiasa.ac.at/ssp/downloads/"
    "ssp_basic_drivers_release_3.2_full.xlsx"
)
WB_COUNTRIES_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"
WB_GDP_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.PP.KD"
    "?format=json&date=2024&per_page=400"
)

IIASA_FILE = ORIGINAL_DIR / "ssp_basic_drivers_release_3.2_full.xlsx"
WB_COUNTRIES_FILE = ORIGINAL_DIR / "world_bank_countries.json"
WB_GDP_FILE = ORIGINAL_DIR / "world_bank_gdp_per_capita_2024.json"

MODEL = "OECD ENV-Growth 2025"
TURBULENT_MODEL = "OECD ENV-Growth 2025 [Turbulent Economy Data]"
VARIABLE = "GDP|PPP [per capita]"
UNIT = "USD_2017/yr"
SSPS = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]
TARGET_YEARS = [2024, 2025, 2030, 2050, 2100]

# IIASA uses plain country names; World Bank supplies ISO3. These aliases cover
# country/territory spelling differences. Unmapped IIASA regions are aggregate
# regions (World, R5/R9/R10) and are deliberately excluded.
IIASA_NAME_TO_ALPHA3 = {
    "Congo": "COG",
    "Democratic Republic of the Congo": "COD",
    "Egypt": "EGY",
    "French Guiana": "GUF",
    "Hong Kong": "HKG",
    "Iran": "IRN",
    "Kyrgyzstan": "KGZ",
    "Laos": "LAO",
    "Macao": "MAC",
    "Mayotte": "MYT",
    "Micronesia": "FSM",
    "North Korea": "PRK",
    "Palestine": "PSE",
    "Puerto Rico": "PRI",
    "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT",
    "Slovakia": "SVK",
    "Somalia": "SOM",
    "South Korea": "KOR",
    "Syria": "SYR",
    "Taiwan": "TWN",
    "Turkey": "TUR",
    "United States Virgin Islands": "VIR",
    "Venezuela": "VEN",
    "Western Sahara": "ESH",
    "Yemen": "YEM",
}


def _download(url: str, destination: Path, refresh: bool) -> Path:
    """Download *url* unless a cached file exists."""
    if destination.is_file() and destination.stat().st_size > 0 and not refresh:
        print(f"Using cached source: {destination.name}")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "waterpath-data-service"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _normalize_name(value: str) -> str:
    """Normalize country names for tolerant IIASA-to-World-Bank matching."""
    ascii_name = (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return re.sub(r"[^a-z0-9]", "", ascii_name.replace("the", ""))


def _read_world_bank_sources(refresh: bool) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return observed 2024 GDP values and normalized name -> ISO3 mapping."""
    _download(WB_COUNTRIES_URL, WB_COUNTRIES_FILE, refresh)
    _download(WB_GDP_URL, WB_GDP_FILE, refresh)

    countries_payload = json.loads(WB_COUNTRIES_FILE.read_text(encoding="utf-8"))
    countries = countries_payload[1]
    actual_countries = [row for row in countries if row["region"]["id"] != "NA"]
    name_to_alpha3 = {
        _normalize_name(row["name"]): row["id"] for row in actual_countries
    }
    valid_alpha3 = {row["id"] for row in actual_countries}

    gdp_payload = json.loads(WB_GDP_FILE.read_text(encoding="utf-8"))
    rows = []
    for record in gdp_payload[1]:
        alpha3 = str(record.get("countryiso3code", "")).strip().upper()
        value = record.get("value")
        if alpha3 in valid_alpha3 and value is not None:
            rows.append(
                {
                    "alpha3": alpha3,
                    "country": record["country"]["value"],
                    "year": 2024,
                    "gdp_per_capita": round(float(value), 2),
                }
            )

    observed = pd.DataFrame(rows).sort_values("alpha3").reset_index(drop=True)
    return observed, name_to_alpha3


def _read_iiasa_rows(source: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read only the GDP-per-capita rows and years needed from the workbook."""
    columns = [
        "Model", "Scenario", "Region", "Variable", "Unit",
        "2020", "2025", "2030", "2050", "2100",
    ]
    data = pd.read_excel(source, sheet_name="data", usecols=columns)
    mask = (
        (data["Model"] == MODEL)
        & (data["Variable"] == VARIABLE)
        & (data["Unit"] == UNIT)
        & (data["Scenario"].isin(["Historical Reference", *SSPS]))
    )
    main = data.loc[mask].copy()

    turbulent_columns = [
        "Model", "Scenario", "Region", "Variable", "Unit",
        "2025", "2030", "2050", "2100",
    ]
    turbulent = pd.read_excel(
        source,
        sheet_name="data_turbulent_economy_data",
        usecols=turbulent_columns,
    )
    turbulent_mask = (
        (turbulent["Model"] == TURBULENT_MODEL)
        & (turbulent["Variable"] == VARIABLE)
        & (turbulent["Unit"] == UNIT)
        & (turbulent["Scenario"].isin(SSPS))
    )
    return main, turbulent.loc[turbulent_mask].copy()


def _add_alpha3(
    frame: pd.DataFrame,
    world_bank_names: dict[str, str],
) -> pd.DataFrame:
    """Map IIASA region names to ISO3, dropping regional aggregates."""
    aliases = {_normalize_name(k): v for k, v in IIASA_NAME_TO_ALPHA3.items()}
    lookup = {**world_bank_names, **aliases}
    result = frame.copy()
    result["alpha3"] = result["Region"].map(
        lambda value: lookup.get(_normalize_name(value))
    )
    return result.dropna(subset=["alpha3"])


def _build_future(
    main: pd.DataFrame,
    turbulent: pd.DataFrame,
    observed: pd.DataFrame,
    world_bank_names: dict[str, str],
) -> pd.DataFrame:
    """Build SSP projections anchored to observed World Bank 2024 values.

    For regular economies, one year of 2020-2025 modeled compound growth is
    applied to the observed 2024 anchor. Values after 2025 preserve each SSP's
    proportional trajectory from the IIASA 2025 value.

    The turbulent-economy sheet has no historical 2020 value, so its 2025 value
    is set equal to observed 2024 and later growth is relative to IIASA 2025.
    """
    main = _add_alpha3(main, world_bank_names)
    turbulent = _add_alpha3(turbulent, world_bank_names)
    observed_map = observed.set_index("alpha3")["gdp_per_capita"].to_dict()

    historical = (
        main[main["Scenario"] == "Historical Reference"]
        .drop_duplicates("alpha3")
        .set_index("alpha3")
    )
    projections = main[main["Scenario"].isin(SSPS)]

    rows: list[dict] = []
    for _, projection in projections.iterrows():
        alpha3 = projection["alpha3"]
        scenario = projection["Scenario"]
        observed_2024 = observed_map.get(alpha3)
        if observed_2024 is None or alpha3 not in historical.index:
            continue

        historical_2020 = float(historical.at[alpha3, "2020"])
        projected_2025 = float(projection["2025"])
        if not np.isfinite(historical_2020) or historical_2020 <= 0:
            continue
        if not np.isfinite(projected_2025) or projected_2025 <= 0:
            continue

        annual_growth = (projected_2025 / historical_2020) ** (1.0 / 5.0)
        anchored_2025 = float(observed_2024) * annual_growth
        rows.append(_future_row(alpha3, scenario, 2024, observed_2024, False))
        rows.append(_future_row(alpha3, scenario, 2025, anchored_2025, False))
        for year in (2030, 2050, 2100):
            source_value = float(projection[str(year)])
            anchored_value = anchored_2025 * source_value / projected_2025
            rows.append(_future_row(alpha3, scenario, year, anchored_value, False))

    for _, projection in turbulent.iterrows():
        alpha3 = projection["alpha3"]
        scenario = projection["Scenario"]
        observed_2024 = observed_map.get(alpha3)
        projected_2025 = float(projection["2025"])
        if observed_2024 is None or not np.isfinite(projected_2025) or projected_2025 <= 0:
            continue

        rows.append(_future_row(alpha3, scenario, 2024, observed_2024, True))
        rows.append(_future_row(alpha3, scenario, 2025, observed_2024, True))
        for year in (2030, 2050, 2100):
            source_value = float(projection[str(year)])
            value = float(observed_2024) * source_value / projected_2025
            rows.append(_future_row(alpha3, scenario, year, value, True))

    result = pd.DataFrame(rows)
    result = result.drop_duplicates(["alpha3", "ssp", "year"], keep="first")
    return result.sort_values(["alpha3", "ssp", "year"]).reset_index(drop=True)


def _future_row(
    alpha3: str,
    scenario: str,
    year: int,
    value: float,
    turbulent: bool,
) -> dict:
    return {
        "alpha3": alpha3,
        "ssp": scenario,
        "year": year,
        "gdp_per_capita": round(float(value), 2),
        "turbulent_economy": turbulent,
    }


def _write_assumptions(path: Path) -> None:
    records = [
        {
            "id": "gdp_1",
            "scenario": "all",
            "year": "2024",
            "admin_level": "all",
            "pathogen": "all",
            "assumption": (
                "Observed national GDP per capita is World Bank indicator "
                "NY.GDP.PCAP.PP.KD (PPP, constant 2021 international dollars), 2024."
            ),
        },
        {
            "id": "gdp_2",
            "scenario": "SSP1-SSP5",
            "year": "2025-2100",
            "admin_level": "all",
            "pathogen": "all",
            "assumption": (
                "Future growth follows OECD ENV-Growth 2025 GDP|PPP per-capita "
                "trajectories from IIASA SSP Basic Drivers release 3.2. Each country "
                "and SSP is multiplicatively anchored to the World Bank 2024 value."
            ),
        },
        {
            "id": "gdp_3",
            "scenario": "SSP1-SSP5",
            "year": "2025",
            "admin_level": "all",
            "pathogen": "all",
            "assumption": (
                "The regular-economy 2025 value applies one year of compound growth "
                "from the IIASA historical-2020 to projected-2025 interval."
            ),
        },
        {
            "id": "gdp_4",
            "scenario": "SSP1-SSP5",
            "year": "2025-2100",
            "admin_level": "all",
            "pathogen": "all",
            "assumption": (
                "Afghanistan and Palestine use IIASA's separately flagged Turbulent "
                "Economy Data and are not robust for country-level analysis. With no "
                "historical 2020 value, 2025 is held at the observed 2024 level. Syria "
                "and Venezuela are omitted because no World Bank 2024 anchor exists."
            ),
        },
        {
            "id": "gdp_5",
            "scenario": "all",
            "year": "all",
            "admin_level": "subnational",
            "pathogen": "all",
            "assumption": (
                "National SSP growth factors are applied uniformly to the Kummu et al. "
                "2024 gridded GDP-per-capita pattern for subnational projections."
            ),
        },
    ]
    pd.DataFrame(records).to_csv(path, sep=";", index=False, lineterminator="\n")


def prepare(refresh: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _download(IIASA_URL, IIASA_FILE, refresh)
    observed, world_bank_names = _read_world_bank_sources(refresh)
    main, turbulent = _read_iiasa_rows(IIASA_FILE)
    future = _build_future(main, turbulent, observed, world_bank_names)

    observed.to_csv(DATA_DIR / "gdp.csv", index=False, lineterminator="\n")
    future.to_csv(DATA_DIR / "gdp_future.csv", index=False, lineterminator="\n")
    _write_assumptions(DATA_DIR / "assumptions.csv")

    expected_rows = future["alpha3"].nunique() * len(SSPS) * len(TARGET_YEARS)
    if len(future) != expected_rows:
        raise RuntimeError(
            f"Incomplete future matrix: {len(future)} rows, expected {expected_rows}."
        )
    print(
        f"Wrote gdp.csv: {len(observed)} countries; "
        f"gdp_future.csv: {len(future)} rows for "
        f"{future['alpha3'].nunique()} countries."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download all source data instead of using data/original cache.",
    )
    args = parser.parse_args()
    prepare(refresh=args.refresh)


if __name__ == "__main__":
    main()
