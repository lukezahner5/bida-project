#!/usr/bin/env python3
"""
EIA Electricity Data Collector - Clean Implementation
Uses Form EIA-923 for utility-scale electricity generation ONLY
"""

import requests
import pandas as pd
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "https://api.eia.gov/v2"
ENDPOINT = "/electricity/eia923/data/"

# Fuel type mappings (EIA-923 codes)
FUEL_TYPES = {
    "COL": "coal",
    "NG": "natural_gas",
    "NUC": "nuclear",
    "HYC": "hydro",
    "WND": "wind",
    "SUN": "solar",
    "GEO": "geothermal",
    "BIO": "biomass",
    "OTH": "other",
    "PEL": "petroleum"
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
    print("EIA Electricity Data Collector (Form EIA-923)")
    print("=" * 70)
    print("\nThis script collects UTILITY-SCALE ELECTRICITY generation only.")
    print("Register for free API key at: https://www.eia.gov/opendata/register.php\n")

    api_key = input("Enter your EIA API key: ").strip()
    if not api_key:
        print("ERROR: API key required!")
        sys.exit(1)
    return api_key


def fetch_generation_data(api_key: str, state: str, start_year: int, end_year: int):
    """
    Fetch electricity generation data from EIA-923.

    This uses the correct endpoint for ELECTRICITY ONLY (not total energy).
    """
    print(f"\nFetching electricity generation for {state}...")

    # Build query parameters
    params = {
        "api_key": api_key,
        "frequency": "annual",
        "start": str(start_year),
        "end": str(end_year),
        "offset": 0,
        "length": 5000,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc"
    }

    # Add facets for filtering
    # CRITICAL: Filter by sector=electric_utility to get utility-scale electricity only
    params["facets[sector][]"] = "electric_utility"
    params["facets[state][]"] = state

    # Add fuel type filters
    for fuel_code in FUEL_TYPES.keys():
        # Need to use indexed parameter name for multiple values
        params[f"facets[fuel_type_code][{fuel_code}]"] = fuel_code

    url = BASE_URL + ENDPOINT

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

    # The response should have:
    # - period (year)
    # - state
    # - fuel_type_code
    # - sector
    # - value (generation in MWh)

    required_cols = ['period', 'state', 'fuel_type_code', 'value']
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        return pd.DataFrame()

    # Clean and transform
    df['year'] = pd.to_numeric(df['period'], errors='coerce')
    df['fuel_type'] = df['fuel_type_code'].map(FUEL_TYPES)
    df['generation_mwh'] = pd.to_numeric(df['value'], errors='coerce')

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
    test_states = ["US", "CA", "TX", "NY"]
    start_year = 2020
    end_year = 2024

    print(f"\nCollecting data for {len(test_states)} locations ({start_year}-{end_year})...")

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

    us_2024 = df[(df['state'] == 'US') & (df['year'] == 2024)]
    if not us_2024.empty:
        total = us_2024['total_generation_gwh'].iloc[0]
        print(f"US 2024 total generation: {total:,.0f} GWh ({total/1000:,.0f} TWh)")

        if 3_900_000 <= total <= 4_500_000:
            print("✓ CORRECT - This is electricity-only data!")
        elif 15_000_000 <= total <= 25_000_000:
            print("✗ ERROR - This is still total energy data (too high by ~4-5x)")
        else:
            print(f"? UNKNOWN - Value outside expected ranges")

    ca_2024 = df[(df['state'] == 'CA') & (df['year'] == 2024)]
    if not ca_2024.empty:
        total = ca_2024['total_generation_gwh'].iloc[0]
        print(f"CA 2024 total generation: {total:,.0f} GWh ({total/1000:,.0f} TWh)")

        if 180_000 <= total <= 280_000:
            print("✓ CORRECT - California electricity data looks good!")
        else:
            print(f"? Check this value")

    # Save output
    output_file = Path.cwd() / "eia_electricity_test.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved to: {output_file}")

    print(f"\nFirst few rows:")
    print(df.head(10))


if __name__ == "__main__":
    main()
