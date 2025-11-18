#!/usr/bin/env python3
"""
EIA Electricity Data Collector - UTILITY-SCALE ELECTRICITY ONLY

Uses: electricity/eia923/generation (EIA-923 generation table)
This contains actual net_generation values in MWh

EIA-923 covers utility-scale electricity generation from plants with
capacity >= 1 MW.
"""

import requests
import pandas as pd
import time
import sys
from pathlib import Path

# Configuration
BASE_URL = "https://api.eia.gov/v2"
ENDPOINT = "/electricity/eia923/generation/data/"

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
    print("EIA-923 Electricity Generation Collector")
    print("=" * 70)
    print("\nDataset: electricity/eia923/generation")
    print("Source: EIA-923 generation table (utility-scale plants >= 1 MW)")
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

    # The response from eia923/generation should have:
    # - period (year)
    # - plant_state (state code)
    # - fuel_type or fuel_type_code
    # - sector or sector_id
    # - net_generation (value in MWh) - THIS IS THE KEY FIELD

    # Map actual column names to expected names
    column_mapping = {
        'plant_state': 'state',
        'plantState': 'state',
        'state-name': 'state',
        'sector_id': 'sector',
        'sectorid': 'sector',
        'fuel_type_code': 'fuel_type',
        'fueltypeid': 'fuel_type',
        'fuelTypeCode': 'fuel_type',
        'net_generation': 'generation_mwh',
        'netGeneration': 'generation_mwh',
        'generation': 'generation_mwh'
    }

    # Rename columns (only rename if column exists)
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            df = df.rename(columns={old_name: new_name})

    # Check if we have the critical generation value column
    if 'generation_mwh' not in df.columns:
        print(f"\nERROR: No generation value column found!")
        print(f"Expected 'net_generation' or similar, but got: {list(df.columns)}")
        print(f"\nThis endpoint might not contain generation values.")
        return pd.DataFrame()

    print(f"✓ Found generation column: generation_mwh")

    # Check for required columns (using mapped names)
    required_cols = ['period', 'state']
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        print(f"ERROR: Missing required columns after mapping: {missing}")
        print(f"Available: {list(df.columns)}")
        return pd.DataFrame()

    print(f"\nApplying filters in Python:")
    print(f"  Original records: {len(df)}")

    # Filter by sector if the column exists (EIA-923 is already utility-scale only)
    if 'sector' in df.columns:
        print(f"  Unique sector values: {df['sector'].unique()[:10]}")
        # EIA-923 is already utility-scale (>= 1 MW), but we can filter if needed
        # Common sector codes: electric_power, ELE, 1, etc.
        sector_filters = ['electric_power', 'ELE', 'electric-power', '1', '01', 2]
        for sector_val in sector_filters:
            temp_df = df[df['sector'] == sector_val].copy()
            if len(temp_df) > 0:
                print(f"  ✓ Filtering to sector='{sector_val}': {len(temp_df)} records")
                df = temp_df
                break
    else:
        print(f"  Note: No sector column - EIA-923 is already utility-scale only (>= 1 MW)")

    # Filter to desired states if specified
    if filter_states:
        print(f"  Unique state values (sample): {df['state'].unique()[:10]}")
        df = df[df['state'].isin(filter_states)].copy()
        print(f"  After state filter {filter_states}: {len(df)}")

    # Filter to only fuel types we care about (if fuel_type column exists)
    if 'fuel_type' in df.columns:
        print(f"  Unique fuel_type values (sample): {df['fuel_type'].unique()[:15]}")
        valid_fuel_codes = list(FUEL_TYPES.keys())
        df = df[df['fuel_type'].isin(valid_fuel_codes)].copy()
        print(f"  After fuel_type filter: {len(df)}")
    else:
        print(f"  Note: No fuel_type column found, will aggregate all fuel types")

    if df.empty:
        print("WARNING: No records remain after filtering!")
        return pd.DataFrame()

    # Clean and transform
    df['year'] = pd.to_numeric(df['period'], errors='coerce')

    # Ensure generation_mwh is numeric
    df['generation_mwh'] = pd.to_numeric(df['generation_mwh'], errors='coerce')

    # Convert MWh to GWh
    df['generation_gwh'] = df['generation_mwh'] / 1000

    # Map fuel codes to readable names if fuel_type exists
    if 'fuel_type' in df.columns:
        df['fuel_name'] = df['fuel_type'].map(FUEL_TYPES)
        # Handle unmapped fuel types (keep original code if not in mapping)
        df.loc[df['fuel_name'].isna(), 'fuel_name'] = df.loc[df['fuel_name'].isna(), 'fuel_type']
        df['fuel_type'] = df['fuel_name']

        # Aggregate by year, state, fuel type
        result = df.groupby(['year', 'state', 'fuel_type'])['generation_gwh'].sum().reset_index()
    else:
        # If no fuel_type column, just aggregate by year and state
        result = df.groupby(['year', 'state'])['generation_gwh'].sum().reset_index()
        result['fuel_type'] = 'all'

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
    print("\nUsing: EIA-923 generation table")
    print("This contains actual net_generation values in MWh")
    print("\nFetching all data, then filtering to:")
    print(f"  - States: {', '.join(test_states)}")
    print(f"  - Fuel types (if available): {', '.join(FUEL_TYPES.keys())}")

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
