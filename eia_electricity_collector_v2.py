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


def fetch_all_generation_data(api_key: str, start_year: int, end_year: int):
    """
    Fetch ALL electricity generation data.

    NOTE: This dataset does NOT support facet filtering for state, sector, or fuel_type.
    We must fetch all data and filter in Python.

    Valid facets: fuel_region, period, respondent, respondent_name, timezone
    NOT valid: state, sector, fuel_type
    """
    print(f"\nFetching ALL electricity generation data ({start_year}-{end_year})...")
    print("NOTE: This dataset doesn't support state/sector/fuel_type facets")
    print("Fetching all data, will filter in Python...")

    url = BASE_URL + ENDPOINT

    all_records = []
    offset = 0
    batch_size = 5000

    while True:
        # Build query parameters - NO FACETS (not supported)
        params = {
            "api_key": api_key,
            "frequency": "annual",
            "start": str(start_year),
            "end": str(end_year),
            "offset": offset,
            "length": batch_size,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc"
        }

        try:
            print(f"  Fetching records {offset} to {offset + batch_size}...")
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            if "response" in data and "data" in data["response"]:
                records = data["response"]["data"]
                all_records.extend(records)
                print(f"  ✓ Retrieved {len(records)} records (total so far: {len(all_records)})")

                # Check if we got fewer records than requested (indicates last page)
                if len(records) < batch_size:
                    print(f"  ✓ Reached end of data")
                    break

                offset += batch_size
                time.sleep(0.5)  # Rate limiting between pages
            else:
                print(f"  ✗ No data in response")
                break

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Request failed: {e}")
            if all_records:
                print(f"  Continuing with {len(all_records)} records fetched so far...")
                break
            else:
                return []

    print(f"\n✓ Total records fetched: {len(all_records)}")
    return all_records


def process_generation_data(all_records, filter_states=None):
    """Convert raw API records to clean DataFrame.

    Args:
        all_records: Raw records from API
        filter_states: List of state codes to filter (e.g., ["CA", "TX"])
                      If None, includes all states
    """
    if not all_records:
        print("No data to process!")
        return pd.DataFrame()

    print(f"\nProcessing {len(all_records)} records...")

    df = pd.DataFrame(all_records)

    # Check what columns we have
    print(f"Available columns: {list(df.columns)}")

    # Debug: Print first record to see all fields
    if len(all_records) > 0:
        print(f"\nSample record (first one):")
        for key, value in all_records[0].items():
            print(f"  {key}: {value}")

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
    required_cols = ['period', 'state', 'fuel_type', 'sector']
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        print(f"Available: {list(df.columns)}")
        return pd.DataFrame()

    print(f"\nApplying filters in Python (facets not supported by this dataset):")

    # Filter to electric_power sector ONLY (utility-scale electricity)
    print(f"  Original records: {len(df)}")
    df = df[df['sector'] == 'electric_power'].copy()
    print(f"  After sector=electric_power filter: {len(df)}")

    # Filter to desired states if specified
    if filter_states:
        df = df[df['state'].isin(filter_states)].copy()
        print(f"  After state filter {filter_states}: {len(df)}")

    # Filter to only fuel types we care about
    valid_fuel_codes = list(FUEL_TYPES.keys())
    df = df[df['fuel_type'].isin(valid_fuel_codes)].copy()
    print(f"  After fuel_type filter: {len(df)}")

    if df.empty:
        print("WARNING: No records remain after filtering!")
        return pd.DataFrame()

    # Clean and transform
    df['year'] = pd.to_numeric(df['period'], errors='coerce')

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
    # NOTE: This dataset requires fetching ALL data, then filtering in Python
    test_states = ["CA", "TX", "NY", "FL"]
    start_year = 2020
    end_year = 2024

    print(f"\nTarget states for analysis: {test_states}")
    print(f"Time range: {start_year}-{end_year}")
    print("\nNOTE: This dataset doesn't support state/sector/fuel_type facets")
    print("Fetching all data, then filtering to:")
    print(f"  - Sector: electric_power (utility-scale only)")
    print(f"  - States: {', '.join(test_states)}")
    print(f"  - Fuel types: {', '.join(FUEL_TYPES.keys())}")

    # Fetch ALL data (no state filter possible in API)
    all_records = fetch_all_generation_data(api_key, start_year, end_year)

    # Process and filter data in Python
    df = process_generation_data(all_records, filter_states=test_states)

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
