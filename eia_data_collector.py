#!/usr/bin/env python3
"""
EIA Data Collector for Data Center Energy Analysis

This script collects comprehensive electricity data from the EIA API v2
for analyzing US energy capacity vs. data center demand growth.

Author: Data Analysis Team
Date: 2025-11-12
API Version: EIA API v2
"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
import sys
import json
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://api.eia.gov/v2"

# States to include in detailed analysis
PRIORITY_STATES = ["TX", "CA", "FL", "NY", "PA", "IL", "OH", "NC", "GA", "VA"]

# All US states for comprehensive data
ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

# Fuel type codes
FUEL_TYPES = {
    "COL": "coal",
    "NG": "gas",
    "NUC": "nuclear",
    "HYC": "hydro",
    "WND": "wind",
    "SUN": "solar",
    "OTH": "other"
}

# Sector codes
SECTORS = {
    "RES": "residential",
    "COM": "commercial",
    "IND": "industrial",
    "TRA": "transportation",
    "ALL": "total"
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_facets_for_api(facets: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Format facets dictionary for EIA API v2 requirements.

    EIA API v2 expects facets as: facets[location][]=VA&facets[location][]=CA
    This function converts our dict format to what requests library needs.

    Args:
        facets: Dictionary of facet names to lists of values

    Returns:
        Dict with properly formatted parameter keys (as lists for multiple values)
    """
    formatted = {}
    for facet_name, values in facets.items():
        # Create keys like "facets[stateid][]" with list of values
        key = f"facets[{facet_name}][]"
        formatted[key] = values
    return formatted


def build_api_params(
    frequency: str,
    data_fields: List[str],
    facets: Dict[str, List[str]],
    start: str,
    end: str,
    offset: int = 0,
    length: int = 5000,
    sort_by: Optional[str] = None
) -> Dict:
    """
    Build properly formatted parameters for EIA API v2.

    Args:
        frequency: Data frequency (annual, monthly, etc.)
        data_fields: List of data fields to retrieve
        facets: Dictionary of facets (e.g., {"location": ["US"], "fueltypeid": ["COL"]})
        start: Start date
        end: End date
        offset: Pagination offset
        length: Number of records to retrieve
        sort_by: Optional sort column

    Returns:
        Dict of parameters formatted for EIA API v2
    """
    params = {
        "frequency": frequency,
        "start": start,
        "end": end,
        "offset": offset,
        "length": length
    }

    # Add data fields with [] notation for arrays
    # For single field, use string; for multiple, use list (requests handles it)
    if len(data_fields) == 1:
        params["data[]"] = data_fields[0]
    else:
        params["data[]"] = data_fields

    # Add formatted facets
    formatted_facets = format_facets_for_api(facets)
    params.update(formatted_facets)

    # Add sort if specified
    if sort_by:
        params["sort[0][column]"] = sort_by
        params["sort[0][direction]"] = "asc"

    return params


def get_api_key() -> str:
    """
    Prompt user for EIA API key.

    Returns:
        str: API key entered by user
    """
    print("=" * 70)
    print("EIA DATA COLLECTOR - Data Center Energy Analysis")
    print("=" * 70)
    print("\nThis script will collect comprehensive electricity data from the EIA API.")
    print("You can get a free API key at: https://www.eia.gov/opendata/register.php\n")

    api_key = input("Please enter your EIA API key: ").strip()

    if not api_key:
        print("ERROR: API key cannot be empty!")
        sys.exit(1)

    return api_key


def test_api_connection(api_key: str) -> bool:
    """
    Test API connection with a simple query.

    Args:
        api_key: EIA API key

    Returns:
        bool: True if connection successful
    """
    print("\n" + "=" * 70)
    print("Testing API Connection...")
    print("=" * 70)

    test_url = f"{BASE_URL}/electricity/retail-sales/data/"
    headers = {"X-Api-Key": api_key}

    # Build parameters with properly formatted facets
    params = {
        "frequency": "annual",
        "data[]": "sales",
        "start": "2023",
        "end": "2023",
        "length": 1
    }

    # Add formatted facets
    facets = format_facets_for_api({"stateid": ["US"]})
    params.update(facets)

    try:
        response = requests.get(test_url, headers=headers, params=params, timeout=30)

        if response.status_code == 200:
            print("✓ API connection successful!")
            return True
        elif response.status_code == 403:
            print("✗ Authentication failed! Please check your API key.")
            return False
        else:
            print(f"✗ Connection failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False


def make_api_request(
    endpoint: str,
    api_key: str,
    params: Dict,
    max_retries: int = 3,
    retry_delay: int = 2
) -> Optional[Dict]:
    """
    Make API request with error handling and retry logic.

    Args:
        endpoint: API endpoint path
        api_key: EIA API key
        params: Request parameters
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Dict: JSON response data or None if failed
    """
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Api-Key": api_key}

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=60)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit
                wait_time = retry_delay * (attempt + 1)
                print(f"  Rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            elif response.status_code == 403:
                print(f"  Authentication error: {response.text}")
                return None
            else:
                print(f"  Request failed with status {response.status_code}: {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        except requests.exceptions.RequestException as e:
            print(f"  Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    return None


def fetch_paginated_data(
    endpoint: str,
    api_key: str,
    base_params: Dict,
    max_records: int = 50000
) -> List[Dict]:
    """
    Fetch data with pagination support.

    Args:
        endpoint: API endpoint path
        api_key: EIA API key
        base_params: Base request parameters
        max_records: Maximum records to fetch

    Returns:
        List[Dict]: All data records
    """
    all_data = []
    offset = 0
    length = 5000  # Max per request

    while offset < max_records:
        params = base_params.copy()
        params["offset"] = offset
        params["length"] = length

        response_data = make_api_request(endpoint, api_key, params)

        if not response_data or "response" not in response_data:
            break

        data = response_data["response"].get("data", [])

        if not data:
            break

        all_data.extend(data)

        # Check if we got all data
        # EIA API v2 returns numeric values as strings in JSON
        total = response_data["response"].get("total", 0)
        try:
            # Convert total to int (handles both string and int cases)
            total = int(total) if total else 0
        except (ValueError, TypeError):
            # If conversion fails, assume we got all data
            total = len(all_data)

        if len(all_data) >= total or len(data) < length:
            break

        offset += length
        time.sleep(0.5)  # Avoid rate limiting

    return all_data


# ============================================================================
# DATA COLLECTION FUNCTIONS
# ============================================================================

def fetch_generation_by_source(api_key: str) -> pd.DataFrame:
    """
    Fetch annual electricity generation by source (2010-2024).

    Args:
        api_key: EIA API key

    Returns:
        DataFrame: Generation data by year, state, and fuel type
    """
    print("\n" + "=" * 70)
    print("1. Fetching Annual Electricity Generation by Source (2010-2024)")
    print("=" * 70)
    print("   Collecting data for US total + all 50 states")

    start_time = time.time()
    endpoint = "/electricity/electric-power-operational-data/data/"

    # Include US total plus all 50 states
    locations = ["US"] + ALL_STATES

    all_records = []

    for location in locations:
        print(f"  Fetching data for {location}...")

        params = build_api_params(
            frequency="annual",
            data_fields=["generation"],
            facets={
                "location": [location],
                "fueltypeid": list(FUEL_TYPES.keys())
            },
            start="2010",
            end="2024",
            sort_by="period"
        )

        data = fetch_paginated_data(endpoint, api_key, params)
        all_records.extend(data)
        time.sleep(0.3)

    if not all_records:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    # Process data
    df = pd.DataFrame(all_records)

    # Create pivot table
    if 'period' in df.columns and 'location' in df.columns and 'fueltypeid' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['state'] = df['location']
        df['fuel_type'] = df['fueltypeid'].map(FUEL_TYPES)
        df['generation_gwh'] = pd.to_numeric(df['generation'], errors='coerce') / 1000  # Convert to GWh

        # Pivot to wide format
        pivot = df.pivot_table(
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

        # Sort
        pivot = pivot.sort_values(['year', 'state']).reset_index(drop=True)

        elapsed = time.time() - start_time
        print(f"  ✓ Retrieved {len(pivot)} records in {elapsed:.1f} seconds")

        return pivot
    else:
        print("  ✗ Unexpected data format!")
        return pd.DataFrame()


def fetch_retail_sales_by_sector(api_key: str) -> pd.DataFrame:
    """
    Fetch total electricity retail sales by sector (2010-2024).

    Args:
        api_key: EIA API key

    Returns:
        DataFrame: Sales data by year, state, and sector
    """
    print("\n" + "=" * 70)
    print("2. Fetching Total Electricity Retail Sales by Sector (2010-2024)")
    print("=" * 70)
    print("   Collecting data for US total + all 50 states")

    start_time = time.time()
    endpoint = "/electricity/retail-sales/data/"

    locations = ["US"] + ALL_STATES

    all_records = []

    for location in locations:
        print(f"  Fetching data for {location}...")

        params = build_api_params(
            frequency="annual",
            data_fields=["sales"],
            facets={
                "stateid": [location],
                "sectorid": list(SECTORS.keys())
            },
            start="2010",
            end="2024",
            sort_by="period"
        )

        data = fetch_paginated_data(endpoint, api_key, params)
        all_records.extend(data)
        time.sleep(0.3)

    if not all_records:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    # Process data
    df = pd.DataFrame(all_records)

    if 'period' in df.columns and 'stateid' in df.columns and 'sectorid' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['state'] = df['stateid']
        df['sector'] = df['sectorid'].map(SECTORS)
        df['sales_gwh'] = pd.to_numeric(df['sales'], errors='coerce') / 1000  # Convert to GWh

        # Pivot to wide format
        pivot = df.pivot_table(
            index=['year', 'state'],
            columns='sector',
            values='sales_gwh',
            aggfunc='sum'
        ).reset_index()

        # Rename columns
        pivot.columns = [f'{col}_sales_gwh' if col not in ['year', 'state'] else col
                        for col in pivot.columns]

        # Fill NaN with 0
        pivot = pivot.fillna(0)

        # Sort
        pivot = pivot.sort_values(['year', 'state']).reset_index(drop=True)

        elapsed = time.time() - start_time
        print(f"  ✓ Retrieved {len(pivot)} records in {elapsed:.1f} seconds")

        return pivot
    else:
        print("  ✗ Unexpected data format!")
        return pd.DataFrame()


def fetch_capacity_by_source(api_key: str) -> pd.DataFrame:
    """
    Fetch electricity generation capacity by source (2015-2024).

    Note: This endpoint only supports monthly frequency, so we fetch monthly data
    and aggregate to annual by taking the December value (end-of-year capacity).

    Args:
        api_key: EIA API key

    Returns:
        DataFrame: Capacity data by year, state, and fuel type
    """
    print("\n" + "=" * 70)
    print("3. Fetching Electricity Generation Capacity by Source (2015-2024)")
    print("=" * 70)
    print("   Collecting data for US total + all 50 states")
    print("   (Note: Fetching monthly data and aggregating to annual)")

    start_time = time.time()
    endpoint = "/electricity/operating-generator-capacity/data/"

    locations = ["US"] + ALL_STATES

    all_records = []

    for location in locations:
        print(f"  Fetching data for {location}...")

        # Use monthly frequency (only supported by this endpoint)
        params = build_api_params(
            frequency="monthly",
            data_fields=["nameplate-capacity-mw"],
            facets={
                "stateid": [location],  # Note: uses stateid, not location
                "energy_source_code": list(FUEL_TYPES.keys())
            },
            start="2015-01",
            end="2024-12",
            sort_by="period"
        )

        data = fetch_paginated_data(endpoint, api_key, params)
        all_records.extend(data)
        time.sleep(0.3)

    if not all_records:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    # Process data
    df = pd.DataFrame(all_records)

    if 'period' in df.columns and 'stateid' in df.columns and 'energy-source-code' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['month'] = pd.to_numeric(df['period'].str[5:7], errors='coerce')
        df['state'] = df['stateid']
        df['fuel_type'] = df['energy-source-code'].map(FUEL_TYPES)
        df['capacity_mw'] = pd.to_numeric(df['nameplate-capacity-mw'], errors='coerce')

        # Take December values for each year (end-of-year capacity)
        # If December is missing, take the last available month
        df_annual = df.sort_values(['year', 'month']).groupby(['year', 'state', 'fuel_type']).tail(1)

        # Pivot to wide format
        pivot = df_annual.pivot_table(
            index=['year', 'state'],
            columns='fuel_type',
            values='capacity_mw',
            aggfunc='sum'
        ).reset_index()

        # Rename columns
        pivot.columns = [f'{col}_capacity_mw' if col not in ['year', 'state'] else col
                        for col in pivot.columns]

        # Calculate total
        cap_cols = [col for col in pivot.columns if col.endswith('_capacity_mw')]
        pivot['total_capacity_mw'] = pivot[cap_cols].sum(axis=1)

        # Fill NaN with 0
        pivot = pivot.fillna(0)

        # Sort
        pivot = pivot.sort_values(['year', 'state']).reset_index(drop=True)

        elapsed = time.time() - start_time
        print(f"  ✓ Retrieved {len(pivot)} records in {elapsed:.1f} seconds")

        return pivot
    else:
        print("  ✗ Unexpected data format!")
        return pd.DataFrame()


def fetch_seds_state_energy(api_key: str) -> pd.DataFrame:
    """
    Fetch State Energy Data System (SEDS) data for all 50 states (2010-2023).

    Args:
        api_key: EIA API key

    Returns:
        DataFrame: State energy consumption and production data
    """
    print("\n" + "=" * 70)
    print("4. Fetching State Energy Data System (SEDS) - All 50 States (2010-2023)")
    print("=" * 70)

    start_time = time.time()
    endpoint = "/seds/data/"

    # SEDS MSN codes
    msn_codes = ["TETCB", "TEPRB", "ESTCB"]

    all_records = []

    print(f"  Fetching data for all 50 states...")

    # SEDS requires seriesId facet with format: SEDS.{MSN}.{STATE}.A
    # We'll fetch all combinations of MSN codes and states
    for msn in msn_codes:
        print(f"    Fetching {msn}...")

        # Build series IDs for all states for this MSN code
        series_ids = [f"SEDS.{msn}.{state}.A" for state in ALL_STATES]

        # SEDS API has a limit on facet values, so we may need to batch
        # Fetch in batches of 50 series IDs at a time
        batch_size = 50
        for i in range(0, len(series_ids), batch_size):
            batch = series_ids[i:i+batch_size]

            params = build_api_params(
                frequency="annual",
                data_fields=["value"],
                facets={
                    "seriesId": batch  # Note: SEDS uses seriesId, not stateId or msn
                },
                start="2010",
                end="2023",
                sort_by="period"
            )

            data = fetch_paginated_data(endpoint, api_key, params)
            all_records.extend(data)
            time.sleep(0.5)

    if not all_records:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    # Process data
    df = pd.DataFrame(all_records)

    if 'period' in df.columns and 'seriesId' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['value_btu'] = pd.to_numeric(df['value'], errors='coerce')

        # Parse seriesId to extract MSN and state
        # Format is: SEDS.{MSN}.{STATE}.A
        df['series_parts'] = df['seriesId'].str.split('.')
        df['msn'] = df['series_parts'].str[1]  # Extract MSN (e.g., TETCB)
        df['state'] = df['series_parts'].str[2]  # Extract state (e.g., CA)

        # Map MSN codes to readable names
        msn_map = {
            "TETCB": "total_energy_consumption_btu",
            "TEPRB": "total_energy_production_btu",
            "ESTCB": "total_electricity_consumption_btu"
        }
        df['metric'] = df['msn'].map(msn_map)

        # Pivot to wide format
        pivot = df.pivot_table(
            index=['year', 'state'],
            columns='metric',
            values='value_btu',
            aggfunc='sum'
        ).reset_index()

        # Add state names (simplified mapping)
        state_names = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming"
        }
        pivot['state_name'] = pivot['state'].map(state_names)

        # Reorder columns
        cols = ['year', 'state', 'state_name', 'total_energy_consumption_btu',
                'total_energy_production_btu', 'total_electricity_consumption_btu']
        pivot = pivot[[col for col in cols if col in pivot.columns]]

        # Fill NaN with 0
        pivot = pivot.fillna(0)

        # Sort
        pivot = pivot.sort_values(['year', 'state']).reset_index(drop=True)

        elapsed = time.time() - start_time
        print(f"  ✓ Retrieved {len(pivot)} records in {elapsed:.1f} seconds")

        return pivot
    else:
        print("  ✗ Unexpected data format!")
        return pd.DataFrame()


def fetch_electricity_prices(api_key: str) -> pd.DataFrame:
    """
    Fetch electricity prices by state (2010-2024).

    Args:
        api_key: EIA API key

    Returns:
        DataFrame: Average electricity prices by year and state
    """
    print("\n" + "=" * 70)
    print("5. Fetching Electricity Prices by State (2010-2024)")
    print("=" * 70)

    start_time = time.time()
    endpoint = "/electricity/retail-sales/data/"

    all_records = []

    print(f"  Fetching price data for all 50 states...")

    params = build_api_params(
        frequency="annual",
        data_fields=["price"],
        facets={
            "stateid": ALL_STATES,
            "sectorid": ["ALL"]
        },
        start="2010",
        end="2024",
        sort_by="period"
    )

    data = fetch_paginated_data(endpoint, api_key, params)
    all_records.extend(data)

    if not all_records:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    # Process data
    df = pd.DataFrame(all_records)

    if 'period' in df.columns and 'stateid' in df.columns and 'price' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['state'] = df['stateid']
        df['avg_price_cents_per_kwh'] = pd.to_numeric(df['price'], errors='coerce')

        # Select relevant columns
        result = df[['year', 'state', 'avg_price_cents_per_kwh']].copy()

        # Remove duplicates
        result = result.drop_duplicates(subset=['year', 'state'])

        # Sort
        result = result.sort_values(['year', 'state']).reset_index(drop=True)

        elapsed = time.time() - start_time
        print(f"  ✓ Retrieved {len(result)} records in {elapsed:.1f} seconds")

        return result
    else:
        print("  ✗ Unexpected data format!")
        return pd.DataFrame()


# ============================================================================
# DATA VALIDATION AND QUALITY REPORTING
# ============================================================================

def validate_and_report(
    df: pd.DataFrame,
    dataset_name: str,
    expected_years: Tuple[int, int],
    expected_states: Optional[List[str]] = None
) -> Dict:
    """
    Validate dataset and generate quality report.

    Args:
        df: DataFrame to validate
        dataset_name: Name of the dataset
        expected_years: Tuple of (start_year, end_year)
        expected_states: List of expected state codes

    Returns:
        Dict: Validation report
    """
    report = {
        "dataset": dataset_name,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "missing_values": {},
        "year_range": None,
        "states_included": [],
        "validation_errors": []
    }

    if df.empty:
        report["validation_errors"].append("Dataset is empty!")
        return report

    # Check year range
    if 'year' in df.columns:
        min_year = df['year'].min()
        max_year = df['year'].max()
        report["year_range"] = f"{int(min_year)}-{int(max_year)}"

        if min_year > expected_years[0]:
            report["validation_errors"].append(
                f"Missing data before {int(min_year)} (expected from {expected_years[0]})"
            )
        if max_year < expected_years[1]:
            report["validation_errors"].append(
                f"Missing data after {int(max_year)} (expected until {expected_years[1]})"
            )

    # Check states
    if 'state' in df.columns:
        states = df['state'].unique().tolist()
        report["states_included"] = sorted(states)

        if expected_states:
            missing_states = set(expected_states) - set(states)
            if missing_states:
                report["validation_errors"].append(
                    f"Missing states: {', '.join(sorted(missing_states))}"
                )

    # Check missing values
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    report["missing_values"] = {
        col: f"{missing[col]} ({missing_pct[col]}%)"
        for col in df.columns if missing[col] > 0
    }

    return report


def print_validation_report(reports: List[Dict]) -> str:
    """
    Print and return formatted validation report.

    Args:
        reports: List of validation report dictionaries

    Returns:
        str: Formatted report text
    """
    report_text = []
    report_text.append("\n" + "=" * 70)
    report_text.append("DATA QUALITY VALIDATION REPORT")
    report_text.append("=" * 70)

    for i, report in enumerate(reports, 1):
        report_text.append(f"\n{i}. {report['dataset']}")
        report_text.append("-" * 70)
        report_text.append(f"   Total Rows: {report['total_rows']:,}")
        report_text.append(f"   Total Columns: {report['total_columns']}")

        if report['year_range']:
            report_text.append(f"   Year Range: {report['year_range']}")

        if report['states_included']:
            report_text.append(f"   States Included: {len(report['states_included'])} ({', '.join(report['states_included'][:5])}...)")

        if report['missing_values']:
            report_text.append("   Missing Values:")
            for col, val in report['missing_values'].items():
                report_text.append(f"      - {col}: {val}")
        else:
            report_text.append("   Missing Values: None")

        if report['validation_errors']:
            report_text.append("   ⚠ Validation Warnings:")
            for error in report['validation_errors']:
                report_text.append(f"      - {error}")
        else:
            report_text.append("   ✓ All validation checks passed")

    report_text.append("\n" + "=" * 70)

    full_report = "\n".join(report_text)
    print(full_report)

    return full_report


# ============================================================================
# DATA EXPORT FUNCTIONS
# ============================================================================

def save_csv_files(datasets: Dict[str, pd.DataFrame], output_dir: Path):
    """
    Save all datasets as CSV files.

    Args:
        datasets: Dictionary of dataset name to DataFrame
        output_dir: Directory to save files
    """
    print("\n" + "=" * 70)
    print("Saving CSV Files...")
    print("=" * 70)

    for name, df in datasets.items():
        if not df.empty:
            filepath = output_dir / f"{name}.csv"
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved: {filepath} ({len(df):,} rows)")
        else:
            print(f"  ✗ Skipped {name} (no data)")


def save_excel_master(
    datasets: Dict[str, pd.DataFrame],
    validation_reports: List[Dict],
    output_dir: Path,
    api_key_masked: str
):
    """
    Save master Excel file with all datasets and metadata.

    Args:
        datasets: Dictionary of dataset name to DataFrame
        validation_reports: List of validation reports
        output_dir: Directory to save file
        api_key_masked: Masked API key for metadata
    """
    print("\n" + "=" * 70)
    print("Creating Master Excel File...")
    print("=" * 70)

    filepath = output_dir / "eia_master_data.xlsx"

    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Write each dataset to a separate sheet
            for name, df in datasets.items():
                if not df.empty:
                    sheet_name = name.replace('eia_', '')[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"  ✓ Added sheet: {sheet_name}")

            # Create metadata sheet
            metadata = {
                'Attribute': [
                    'Collection Date/Time',
                    'API Version',
                    'API Key (masked)',
                    'Script Version',
                    'Total Datasets',
                    '',
                    'Dataset Statistics:',
                ] + [f"  {r['dataset']}" for r in validation_reports],
                'Value': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'EIA API v2',
                    api_key_masked,
                    '1.0',
                    str(len(datasets)),
                    '',
                    '',
                ] + [f"{r['total_rows']:,} rows, {r['year_range']}" for r in validation_reports]
            }

            metadata_df = pd.DataFrame(metadata)
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            print(f"  ✓ Added metadata sheet")

        print(f"\n  ✓ Master Excel file saved: {filepath}")

    except Exception as e:
        print(f"  ✗ Error saving Excel file: {e}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""

    # Get API key
    api_key = get_api_key()
    api_key_masked = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]

    # Test connection
    if not test_api_connection(api_key):
        print("\nExiting due to connection failure.")
        sys.exit(1)

    # Create output directory
    output_dir = Path.cwd()

    # Collect all datasets
    print("\n" + "=" * 70)
    print("STARTING DATA COLLECTION")
    print("=" * 70)

    datasets = {}
    collection_start = time.time()

    # 1. Generation by source
    datasets['eia_generation_by_source'] = fetch_generation_by_source(api_key)

    # 2. Retail sales by sector
    datasets['eia_retail_sales_by_sector'] = fetch_retail_sales_by_sector(api_key)

    # 3. Capacity by source
    datasets['eia_capacity_by_source'] = fetch_capacity_by_source(api_key)

    # 4. SEDS state energy
    datasets['eia_state_energy_seds'] = fetch_seds_state_energy(api_key)

    # 5. Electricity prices
    datasets['eia_electricity_prices'] = fetch_electricity_prices(api_key)

    total_time = time.time() - collection_start

    print("\n" + "=" * 70)
    print(f"DATA COLLECTION COMPLETE - Total time: {total_time:.1f} seconds")
    print("=" * 70)

    # Validate data
    validation_reports = [
        validate_and_report(
            datasets['eia_generation_by_source'],
            'Annual Electricity Generation by Source',
            (2010, 2024),
            ["US"] + ALL_STATES
        ),
        validate_and_report(
            datasets['eia_retail_sales_by_sector'],
            'Retail Sales by Sector',
            (2010, 2024),
            ["US"] + ALL_STATES
        ),
        validate_and_report(
            datasets['eia_capacity_by_source'],
            'Generation Capacity by Source',
            (2015, 2024),
            ["US"] + ALL_STATES
        ),
        validate_and_report(
            datasets['eia_state_energy_seds'],
            'State Energy Data System (SEDS)',
            (2010, 2023),
            ALL_STATES
        ),
        validate_and_report(
            datasets['eia_electricity_prices'],
            'Electricity Prices by State',
            (2010, 2024),
            ALL_STATES
        ),
    ]

    # Print validation report
    report_text = print_validation_report(validation_reports)

    # Save validation report to file
    report_file = output_dir / "data_quality_report.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)
    print(f"\n✓ Data quality report saved: {report_file}")

    # Save CSV files
    save_csv_files(datasets, output_dir)

    # Save Excel master file
    save_excel_master(datasets, validation_reports, output_dir, api_key_masked)

    # Final summary
    print("\n" + "=" * 70)
    print("SUMMARY - All Files Created:")
    print("=" * 70)

    total_rows = sum(len(df) for df in datasets.values())

    print(f"\nCSV Files:")
    for name in datasets.keys():
        filepath = output_dir / f"{name}.csv"
        if filepath.exists():
            print(f"  ✓ {filepath.name}")

    print(f"\nExcel File:")
    print(f"  ✓ eia_master_data.xlsx")

    print(f"\nReports:")
    print(f"  ✓ data_quality_report.txt")

    print(f"\nTotal Records Collected: {total_rows:,}")
    print(f"Total Execution Time: {total_time:.1f} seconds")

    print("\n" + "=" * 70)
    print("✓ DATA COLLECTION COMPLETE - Ready for analysis!")
    print("=" * 70)


if __name__ == "__main__":
    main()
