#!/usr/bin/env python3
"""
EIA Electricity Data Collector - UTILITY-SCALE ELECTRICITY ONLY

Uses: electricity/electric-power-operational-data
Filters: sector=electric_power (this is critical for electricity-only data)

This excludes total energy (transportation, heating, etc.)
"""

import requests
import pandas as pd
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "https://api.eia.gov/v2"
ENDPOINT = "/electricity/electric-power-operational-data/data/"

# Fuel type mappings (valid codes for electric-power-operational-data)
FUEL_TYPES = {
    "COL": "coal",
    "NG": "natural_gas",
    "NUC": "nuclear",
    "WAT": "hydro",        # WAT, not HYC
    "WND": "wind",
    "SUN": "solar",
    "GEO": "geothermal",
    "BM": "biomass",       # BM, not BIO
    "WH": "waste_heat",    # Waste heat
    "OTH": "other"         # PEL (petroleum) removed - not valid
}

# US States
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]


def get_api_key() -> str:
    """Get API key from user."""
    print("=" * 70)
    print("EIA Electricity Collector - UTILITY-SCALE ONLY")
    print("=" * 70)
    print("\nDataset: electricity/electric-power-operational-data")
    print("Filter: sector=electric_power (excludes total energy)")
    print("\nRegister for free API key at: https://www.eia.gov/opendata/register.php\n")

    api_key = input("Enter your EIA API key: ").strip()
    if not api_key:
        print("ERROR: API key required!")
        sys.exit(1)
    return api_key


def fetch_generation_data(api_key: str, state: str, start_year: int, end_year: int):
    """
    Fetch utility-scale electricity generation data.

    Uses electric-power-operational-data with sector=electric_power filter.
    This ensures we get ELECTRICITY ONLY (not total energy).
    """
    print(f"\nFetching electricity generation for {state}...")

    url = BASE_URL + ENDPOINT

    # Build query parameters
    # NOTE: fuel_type is NOT a facet in this dataset - we filter it in Python after retrieval
    params = {
        "api_key": api_key,
        "frequency": "annual",
        "start": str(start_year),
        "end": str(end_year),
        "offset": 0,
        "length": 5000,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        # CRITICAL: Filter by sector to get utility-scale electricity ONLY
        "facets[sector][]": "electric_power",
        # State filter
        "facets[state][]": state
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if "response" in data and "data" in data["response"]:
            records = data["response"]["data"]
            print(f"  ✓ Retrieved {len(records)} records")
            return records
        else:
            print(f"  ✗ No data in response")
            return []

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request failed: {e}")
        return []


def process_generation_data(all_records):
    """Convert raw API records to clean DataFrame."""
    if not all_records:
        print("No data to process!")
        return pd.DataFrame()

    print(f"\nProcessing {len(all_records)} records...")

    df = pd.DataFrame(all_records)

    # Check what columns we have
    print(f"Available columns: {list(df.columns)}")

    # The response from electric-power-operational-data should have:
    # - period (year)
    # - state
    # - fuel_type (NOT fueltype or fuel_type_code)
    # - sector
    # - generation (value in MWh)

    # Try to identify the value column
    value_col = None
    if 'generation' in df.columns:
        value_col = 'generation'
    elif 'value' in df.columns:
        value_col = 'value'
    else:
        print(f"ERROR: No generation/value column found. Columns: {list(df.columns)}")
        return pd.DataFrame()

    # Check for required columns
    required_cols = ['period', 'state', 'fuel_type']
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        print(f"Available: {list(df.columns)}")
        return pd.DataFrame()

    # Clean and transform
    df['year'] = pd.to_numeric(df['period'], errors='coerce')

    # Filter to only fuel types we care about (fuel_type is not a facet, so filter in Python)
    valid_fuel_codes = list(FUEL_TYPES.keys())
    print(f"Filtering to valid fuel types: {valid_fuel_codes}")
    df = df[df['fuel_type'].isin(valid_fuel_codes)].copy()
    print(f"Records after fuel filtering: {len(df)}")

    # Map fuel codes to readable names
    df['fuel_name'] = df['fuel_type'].map(FUEL_TYPES)

    # Handle unmapped fuel types (keep original code if not in mapping)
    df.loc[df['fuel_name'].isna(), 'fuel_name'] = df.loc[df['fuel_name'].isna(), 'fuel_type']

    # Now use fuel_name as our fuel_type column for consistency
    df['fuel_type'] = df['fuel_name']

    df['generation_mwh'] = pd.to_numeric(df[value_col], errors='coerce')

    # Convert MWh to GWh
    df['generation_gwh'] = df['generation_mwh'] / 1000

    # Aggregate by year, state, fuel type
    result = df.groupby(['year', 'state', 'fuel_type'])['generation_gwh'].sum().reset_index()

    # Pivot to wide format
    pivot = result.pivot_table(
        index=['year', 'state'],
        columns='fuel_type',
        values='generation_gwh',
        aggfunc='sum'
    ).reset_index()

    # Rename columns
    pivot.columns = [f'{col}_generation_gwh' if col not in ['year', 'state'] else col
                     for col in pivot.columns]

    # Calculate total
    gen_cols = [col for col in pivot.columns if col.endswith('_generation_gwh')]
    pivot['total_generation_gwh'] = pivot[gen_cols].sum(axis=1)

    # Fill NaN with 0
    pivot = pivot.fillna(0)

    print(f"✓ Processed into {len(pivot)} state-year records")

    return pivot


def main():
    """Main execution."""
    api_key = get_api_key()

    # Test with just a few states first to verify it's working
    # NOTE: "US" is not a valid state code - we need to sum all states for national total
    test_states = ["CA", "TX", "NY", "FL"]
    start_year = 2020
    end_year = 2024

    print(f"\nCollecting data for {len(test_states)} states ({start_year}-{end_year})...")
    print("NOTE: Using sector=electric_power filter for utility-scale electricity only")

    all_records = []

    for state in test_states:
        records = fetch_generation_data(api_key, state, start_year, end_year)
        all_records.extend(records)
        time.sleep(0.5)  # Rate limiting

    # Process data
    df = process_generation_data(all_records)

    if df.empty:
        print("\nNo data collected. Exiting.")
        return

    # Validation check
    print("\n" + "=" * 70)
    print("VALIDATION CHECK")
    print("=" * 70)

    # Check California (should be ~200-250 TWh)
    ca_2024 = df[(df['state'] == 'CA') & (df['year'] == 2024)]
    if not ca_2024.empty:
        total = ca_2024['total_generation_gwh'].iloc[0]
        print(f"CA 2024 total generation: {total:,.0f} GWh ({total/1000:,.1f} TWh)")

        if 180_000 <= total <= 280_000:
            print("✓ CORRECT - California electricity data looks good!")
        elif total > 500_000:
            print("✗ ERROR - Still pulling total energy data (too high)")
        else:
            print(f"? Unexpected value - expected 180-280K GWh")
    else:
        print("⚠ No California 2024 data found")

    # Check Texas (should be ~450-550 TWh)
    tx_2024 = df[(df['state'] == 'TX') & (df['year'] == 2024)]
    if not tx_2024.empty:
        total = tx_2024['total_generation_gwh'].iloc[0]
        print(f"TX 2024 total generation: {total:,.0f} GWh ({total/1000:,.1f} TWh)")

        if 400_000 <= total <= 600_000:
            print("✓ CORRECT - Texas electricity data looks good!")
        else:
            print(f"? Check this value (expected 400-600K GWh)")
    else:
        print("⚠ No Texas 2024 data found")

    # Estimate US total by summing all states collected
    total_2024 = df[df['year'] == 2024]['total_generation_gwh'].sum()
    print(f"\nTotal from {len(test_states)} states (2024): {total_2024:,.0f} GWh ({total_2024/1000:,.1f} TWh)")
    print(f"(Full US total would be ~4,200 TWh when all 50 states summed)")

    # Save output
    output_file = Path.cwd() / "eia_electricity_test.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved to: {output_file}")

    print(f"\nFirst few rows:")
    print(df.head(10))


if __name__ == "__main__":
    main()
