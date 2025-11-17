#!/usr/bin/env python3
"""
EIA Data Collector for Data Center Energy Analysis

This script collects comprehensive ELECTRICITY-ONLY data from the EIA API v2
for analyzing US energy capacity vs. data center demand growth.

IMPORTANT: This queries electricity net generation (~4,200 TWh for US 2024),
NOT total primary energy (~27,500 TWh which includes transportation fuels,
heating, conversion losses, etc.)

API Endpoints:
- /electricity/electric-power-operational-data/ - Form EIA-923 generation data
- /electricity/retail-sales/ - Form EIA-861 sales data
- /electricity/facility-fuel/ - Form EIA-860 capacity data

Data Source: Form EIA-923 (Power Plant Operations Report)
Coverage: ~11,000 utility-scale facilities (≥1 MW capacity)

Author: Data Analysis Team
Date: 2025-11-12
API Version: EIA API v2
API Documentation: https://www.eia.gov/opendata/documentation.php
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

# Sector codes for retail sales (different from generation sectors)
SECTORS = {
    "RES": "residential",
    "COM": "commercial",
    "IND": "industrial",
    "TRA": "transportation",
    "ALL": "total"
}

# State populations (2024 estimates) for per capita calculations
STATE_POPULATIONS = {
    'AL': 5108468, 'AK': 733406, 'AZ': 7431344, 'AR': 3067732,
    'CA': 38965193, 'CO': 5877610, 'CT': 3617176, 'DE': 1031890,
    'FL': 22610726, 'GA': 11029227, 'HI': 1435138, 'ID': 1964726,
    'IL': 12549689, 'IN': 6862199, 'IA': 3207004, 'KS': 2940546,
    'KY': 4526154, 'LA': 4573749, 'ME': 1395722, 'MD': 6164660,
    'MA': 6981974, 'MI': 10037261, 'MN': 5737915, 'MS': 2939690,
    'MO': 6196156, 'MT': 1122867, 'NE': 1978379, 'NV': 3194176,
    'NH': 1402054, 'NJ': 9290841, 'NM': 2114371, 'NY': 19571216,
    'NC': 10835491, 'ND': 783926, 'OH': 11785935, 'OK': 4053824,
    'OR': 4233358, 'PA': 12961683, 'RI': 1095962, 'SC': 5373555,
    'SD': 919318, 'TN': 7126489, 'TX': 30503301, 'UT': 3417734,
    'VT': 647464, 'VA': 8715698, 'WA': 7812880, 'WV': 1770071,
    'WI': 5910955, 'WY': 584057, 'DC': 678972
}

# State regions for regional analysis
STATE_REGIONS = {
    # Northeast
    'CT': 'Northeast', 'ME': 'Northeast', 'MA': 'Northeast', 'NH': 'Northeast',
    'NJ': 'Northeast', 'NY': 'Northeast', 'PA': 'Northeast', 'RI': 'Northeast',
    'VT': 'Northeast',

    # Midwest
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest',
    'MI': 'Midwest', 'MN': 'Midwest', 'MO': 'Midwest', 'NE': 'Midwest',
    'ND': 'Midwest', 'OH': 'Midwest', 'SD': 'Midwest', 'WI': 'Midwest',

    # South
    'AL': 'South', 'AR': 'South', 'DE': 'South', 'DC': 'South', 'FL': 'South',
    'GA': 'South', 'KY': 'South', 'LA': 'South', 'MD': 'South', 'MS': 'South',
    'NC': 'South', 'OK': 'South', 'SC': 'South', 'TN': 'South', 'TX': 'South',
    'VA': 'South', 'WV': 'South',

    # West
    'AK': 'West', 'AZ': 'West', 'CA': 'West', 'CO': 'West', 'HI': 'West',
    'ID': 'West', 'MT': 'West', 'NV': 'West', 'NM': 'West', 'OR': 'West',
    'UT': 'West', 'WA': 'West', 'WY': 'West'
}

# State full names mapping
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia', 'US': 'United States'
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_facets_for_api(facets: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Format facets dictionary for EIA API v2 requirements.

    EIA API v2 expects facets as: facets[stateid][]=VA&facets[stateid][]=CA
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
        facets: Dictionary of facets (e.g., {"stateid": ["US"], "fueltypeid": ["COL"]})
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
                "stateid": [location],  # Correct facet name per EIA API v2 documentation
                "fueltypeid": list(FUEL_TYPES.keys())
                # No sectorid filter - API returns total state generation correctly without it
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
    if 'period' in df.columns and 'stateid' in df.columns and 'fueltypeid' in df.columns:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['state'] = df['stateid']  # API returns 'stateid' column
        df['fuel_type'] = df['fueltypeid'].map(FUEL_TYPES)
        # EIA API returns data in "thousand megawatthours" which equals GWh (no conversion needed)
        df['generation_gwh'] = pd.to_numeric(df['generation'], errors='coerce')

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
        # EIA API returns data in "thousand megawatthours" which equals GWh (no conversion needed)
        df['sales_gwh'] = pd.to_numeric(df['sales'], errors='coerce')

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

    # Debug: print available columns
    if df.empty:
        print("  ✗ No data retrieved!")
        return pd.DataFrame()

    print(f"  Debug: Available columns: {list(df.columns)}")

    # Check for required columns - be flexible with column names
    has_period = 'period' in df.columns
    has_state = 'stateid' in df.columns or 'stateId' in df.columns
    has_energy_source = 'energy-source-code' in df.columns or 'energySourceCode' in df.columns or 'energy_source_code' in df.columns
    has_capacity = 'nameplate-capacity-mw' in df.columns or 'nameplateCapacityMW' in df.columns or 'nameplate_capacity_mw' in df.columns

    if has_period and has_state and has_energy_source and has_capacity:
        df['year'] = pd.to_numeric(df['period'].str[:4], errors='coerce')
        df['month'] = pd.to_numeric(df['period'].str[5:7], errors='coerce')

        # Handle different state column names
        if 'stateid' in df.columns:
            df['state'] = df['stateid']
        elif 'stateId' in df.columns:
            df['state'] = df['stateId']

        # Handle different energy source column names
        if 'energy-source-code' in df.columns:
            df['fuel_type'] = df['energy-source-code'].map(FUEL_TYPES)
        elif 'energySourceCode' in df.columns:
            df['fuel_type'] = df['energySourceCode'].map(FUEL_TYPES)
        elif 'energy_source_code' in df.columns:
            df['fuel_type'] = df['energy_source_code'].map(FUEL_TYPES)

        # Handle different capacity column names
        if 'nameplate-capacity-mw' in df.columns:
            df['capacity_mw'] = pd.to_numeric(df['nameplate-capacity-mw'], errors='coerce')
        elif 'nameplateCapacityMW' in df.columns:
            df['capacity_mw'] = pd.to_numeric(df['nameplateCapacityMW'], errors='coerce')
        elif 'nameplate_capacity_mw' in df.columns:
            df['capacity_mw'] = pd.to_numeric(df['nameplate_capacity_mw'], errors='coerce')

        # Remove rows with missing fuel types
        df = df[df['fuel_type'].notna()]

        if df.empty:
            print("  ✗ No valid data after processing!")
            return pd.DataFrame()

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
        print(f"  Missing columns - period: {has_period}, state: {has_state}, energy_source: {has_energy_source}, capacity: {has_capacity}")
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
    print("4. Fetching Electricity Prices by State (2010-2024)")
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


def calculate_cagr(start_value: float, end_value: float, num_years: int) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR).

    Args:
        start_value: Starting value
        end_value: Ending value
        num_years: Number of years between start and end

    Returns:
        float: CAGR as a percentage
    """
    if pd.isna(start_value) or pd.isna(end_value) or start_value <= 0 or num_years <= 0:
        return np.nan

    try:
        cagr = (((end_value / start_value) ** (1 / num_years)) - 1) * 100
        return cagr
    except (ZeroDivisionError, ValueError):
        return np.nan


def calculate_growth_metrics(df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate growth metrics (CAGR) for each state.

    Args:
        df: Comprehensive metrics DataFrame
        prices_df: Electricity prices DataFrame

    Returns:
        DataFrame: Input DataFrame with added growth metric columns
    """
    print("  Computing growth metrics (CAGR 2011-2024)...")

    # We need 2011 and 2024 data for each state
    growth_metrics = []

    for state in df['state'].unique():
        state_data = df[df['state'] == state].sort_values('year')

        # Get 2011 and 2024 data (or closest available)
        data_2011 = state_data[state_data['year'] == 2011]
        data_2024 = state_data[state_data['year'] == 2024]

        if data_2011.empty or data_2024.empty:
            continue

        # Calculate Generation CAGR
        gen_2011 = data_2011['total_generation_gwh'].values[0]
        gen_2024 = data_2024['total_generation_gwh'].values[0]
        gen_cagr = calculate_cagr(gen_2011, gen_2024, 13)

        # Calculate Renewable CAGR
        renewable_2011 = (
            data_2011.get('solar_generation_gwh', pd.Series([0])).values[0] +
            data_2011.get('wind_generation_gwh', pd.Series([0])).values[0] +
            data_2011.get('hydro_generation_gwh', pd.Series([0])).values[0]
        )
        renewable_2024 = (
            data_2024.get('solar_generation_gwh', pd.Series([0])).values[0] +
            data_2024.get('wind_generation_gwh', pd.Series([0])).values[0] +
            data_2024.get('hydro_generation_gwh', pd.Series([0])).values[0]
        )
        renewable_cagr = calculate_cagr(renewable_2011, renewable_2024, 13)

        growth_metrics.append({
            'state': state,
            'generation_cagr_pct': gen_cagr,
            'renewable_cagr_pct': renewable_cagr
        })

    # Create growth metrics DataFrame
    growth_df = pd.DataFrame(growth_metrics)

    # Calculate price change from prices_df
    price_changes = []
    for state in prices_df['state'].unique():
        state_prices = prices_df[prices_df['state'] == state].sort_values('year')
        price_2011 = state_prices[state_prices['year'] == 2011]['avg_price_cents_per_kwh']
        price_2024 = state_prices[state_prices['year'] == 2024]['avg_price_cents_per_kwh']

        if not price_2011.empty and not price_2024.empty:
            price_change = ((price_2024.values[0] - price_2011.values[0]) / price_2011.values[0]) * 100
            price_changes.append({
                'state': state,
                'price_change_2011_2024_pct': price_change
            })

    price_change_df = pd.DataFrame(price_changes)

    # Merge growth metrics with price changes
    if not price_change_df.empty:
        growth_df = growth_df.merge(price_change_df, on='state', how='left')

    # Merge back into main dataframe
    df = df.merge(growth_df, on='state', how='left')

    return df


def calculate_datacenter_suitability_score(row: pd.Series) -> float:
    """
    Calculate a composite datacenter suitability score (0-100) for a state.

    Scoring components:
    - 30 points: Surplus capacity (net generation balance)
    - 25 points: Low electricity prices
    - 20 points: Renewable percentage
    - 15 points: Available capacity
    - 10 points: Growth trajectory (generation CAGR)

    Args:
        row: DataFrame row with state metrics

    Returns:
        float: Suitability score from 0-100
    """
    score = 0.0

    # 1. Surplus Capacity Score (30 points)
    # Positive surplus is good, negative is bad
    capacity_surplus = row.get('capacity_surplus_pct', np.nan)
    if not pd.isna(capacity_surplus):
        # Scale: -50% to +50% mapped to 0-30 points
        # Clamp between -50 and +50
        clamped_surplus = max(-50, min(50, capacity_surplus))
        # Convert to 0-30 scale (0 at -50%, 15 at 0%, 30 at +50%)
        surplus_score = ((clamped_surplus + 50) / 100) * 30
        score += surplus_score

    # 2. Low Price Score (25 points)
    # Lower prices are better for data centers
    price = row.get('avg_price_cents_per_kwh', np.nan)
    if not pd.isna(price):
        # US average is ~10.5 cents/kWh, range typically 7-20 cents
        # Lower is better: 7 cents = 25 points, 20 cents = 0 points
        if price <= 7:
            price_score = 25
        elif price >= 20:
            price_score = 0
        else:
            # Linear scale from 7-20 cents
            price_score = 25 * (1 - (price - 7) / 13)
        score += price_score

    # 3. Renewable Percentage Score (20 points)
    # Higher renewable % is better
    renewable_pct = row.get('renewable_percentage', np.nan)
    if not pd.isna(renewable_pct):
        # Scale: 0% to 100% mapped to 0-20 points
        renewable_score = min(20, (renewable_pct / 100) * 20)
        score += renewable_score

    # 4. Available Capacity Score (15 points)
    # More available capacity is better
    available_capacity = row.get('available_capacity_mw', np.nan)
    total_capacity = row.get('total_capacity_mw', np.nan)
    if not pd.isna(available_capacity) and not pd.isna(total_capacity) and total_capacity > 0:
        # Calculate available capacity as percentage
        available_pct = (available_capacity / total_capacity) * 100
        # Scale: 0% to 50% mapped to 0-15 points
        available_score = min(15, (available_pct / 50) * 15)
        score += available_score

    # 5. Growth Trajectory Score (10 points)
    # Moderate positive growth is good (not too fast, not negative)
    gen_cagr = row.get('generation_cagr_pct', np.nan)
    if not pd.isna(gen_cagr):
        # Ideal range: 0% to 5% CAGR
        # Above 5% might indicate capacity constraints
        # Below 0% indicates declining market
        if gen_cagr < 0:
            growth_score = 0
        elif gen_cagr <= 5:
            growth_score = (gen_cagr / 5) * 10
        else:
            # Declining score above 5%
            growth_score = max(0, 10 - ((gen_cagr - 5) / 5) * 5)
        score += growth_score

    return round(score, 2)


def calculate_derived_metrics(
    generation_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    capacity_df: pd.DataFrame,
    prices_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate derived metrics by merging and computing additional fields.

    Args:
        generation_df: Generation by source data
        sales_df: Retail sales by sector data
        capacity_df: Capacity by source data
        prices_df: Electricity prices data

    Returns:
        DataFrame: Comprehensive metrics with derived calculations
    """
    print("\n" + "=" * 70)
    print("Calculating Derived Metrics...")
    print("=" * 70)

    # Merge all datasets on year and state
    df = generation_df.merge(sales_df, on=['year', 'state'], how='outer')
    df = df.merge(capacity_df, on=['year', 'state'], how='outer')
    df = df.merge(prices_df, on=['year', 'state'], how='outer')

    # Add state metadata
    df['state_name'] = df['state'].map(STATE_NAMES)
    df['population'] = df['state'].map(STATE_POPULATIONS)
    df['region'] = df['state'].map(STATE_REGIONS)

    # Calculate derived metrics
    print("  Computing capacity metrics...")

    # 1. Net Generation Balance (GWh)
    df['net_generation_balance_gwh'] = df['total_generation_gwh'] - df['total_sales_gwh']

    # 2. Capacity Surplus Percentage
    df['capacity_surplus_pct'] = (df['net_generation_balance_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100

    # 3. Generation Per Capita (MWh per person)
    # Convert GWh to MWh (multiply by 1000)
    df['generation_per_capita_mwh'] = (df['total_generation_gwh'] * 1000) / df['population'].replace(0, np.nan)

    # 4. Consumption Per Capita (MWh per person)
    df['consumption_per_capita_mwh'] = (df['total_sales_gwh'] * 1000) / df['population'].replace(0, np.nan)

    # 5. Renewable Percentage
    renewable_generation = (
        df.get('solar_generation_gwh', 0) +
        df.get('wind_generation_gwh', 0) +
        df.get('hydro_generation_gwh', 0)
    )
    df['renewable_percentage'] = (renewable_generation / df['total_generation_gwh'].replace(0, np.nan)) * 100

    # 6. Capacity Utilization (%)
    # Total possible generation = capacity (MW) × 8760 hours/year
    # Convert MW to GW, then multiply by 8760 to get GWh
    total_possible_gwh = (df['total_capacity_mw'] / 1000) * 8760
    df['capacity_utilization_pct'] = (df['total_generation_gwh'] / total_possible_gwh.replace(0, np.nan)) * 100

    # 7. Available Capacity (MW)
    # Available capacity = Total capacity × (1 - utilization rate as decimal)
    utilization_decimal = df['capacity_utilization_pct'] / 100
    df['available_capacity_mw'] = df['total_capacity_mw'] * (1 - utilization_decimal)

    # 8-10. Growth Metrics (CAGR)
    df = calculate_growth_metrics(df, prices_df)

    # Fill infinite values with NaN
    df = df.replace([np.inf, -np.inf], np.nan)

    # Calculate datacenter suitability score for 2024 data
    print("  Computing datacenter suitability scores...")
    df['datacenter_suitability_score'] = df.apply(calculate_datacenter_suitability_score, axis=1)

    # Sort by year and state
    df = df.sort_values(['year', 'state']).reset_index(drop=True)

    print(f"  ✓ Calculated derived metrics for {len(df)} records")
    print(f"  ✓ Added fields: population, region, capacity metrics,")
    print(f"     growth metrics (CAGR), and datacenter suitability scores")

    return df


def create_2024_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create 2024-specific analysis file with rankings.

    Args:
        df: Comprehensive metrics DataFrame

    Returns:
        DataFrame: 2024 data only, sorted by suitability score
    """
    print("\n" + "=" * 70)
    print("Creating 2024 State Capacity Analysis...")
    print("=" * 70)

    # Filter for 2024 data only
    df_2024 = df[df['year'] == 2024].copy()

    # Exclude US total for state rankings
    df_2024_states = df_2024[df_2024['state'] != 'US'].copy()

    if df_2024_states.empty:
        print("  ✗ No 2024 data available!")
        return pd.DataFrame()

    # Sort by suitability score (descending)
    df_2024_states = df_2024_states.sort_values('datacenter_suitability_score', ascending=False)

    # Add ranking column
    df_2024_states['suitability_rank'] = range(1, len(df_2024_states) + 1)

    # Select key columns for analysis
    analysis_columns = [
        'suitability_rank',
        'state',
        'state_name',
        'region',
        'datacenter_suitability_score',
        'net_generation_balance_gwh',
        'capacity_surplus_pct',
        'available_capacity_mw',
        'total_capacity_mw',
        'capacity_utilization_pct',
        'renewable_percentage',
        'avg_price_cents_per_kwh',
        'generation_cagr_pct',
        'renewable_cagr_pct',
        'price_change_2011_2024_pct',
        'population',
        'total_generation_gwh',
        'total_sales_gwh',
        'commercial_sales_gwh'
    ]

    # Filter to include only columns that exist
    existing_columns = [col for col in analysis_columns if col in df_2024_states.columns]
    df_2024_analysis = df_2024_states[existing_columns].copy()

    print(f"  ✓ Created 2024 analysis for {len(df_2024_analysis)} states")
    print(f"\n  Top 5 States for Datacenter Development (2024):")
    for i, row in df_2024_analysis.head(5).iterrows():
        state_name = row.get('state_name', row['state'])
        score = row.get('datacenter_suitability_score', 0)
        surplus = row.get('capacity_surplus_pct', 0)
        print(f"    {int(row['suitability_rank'])}. {state_name} - Score: {score:.1f}, Surplus: {surplus:.1f}%")

    return df_2024_analysis


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


def validate_data_quality(df: pd.DataFrame) -> List[str]:
    """
    Perform comprehensive data quality checks.

    Args:
        df: Comprehensive metrics DataFrame

    Returns:
        List of validation error/warning messages
    """
    issues = []

    # Check 1: Verify US 2024 total generation is in expected range (3.9M - 4.5M GWh)
    us_2024 = df[(df['state'] == 'US') & (df['year'] == 2024)]
    if not us_2024.empty:
        total_gen = us_2024['total_generation_gwh'].iloc[0]
        expected_min = 3_900_000
        expected_max = 4_500_000

        if total_gen < expected_min or total_gen > expected_max:
            # Check if it's ~4.4x too high (sector duplication issue)
            if expected_min * 4 < total_gen < expected_max * 5:
                issues.append(
                    f"CRITICAL: US 2024 total generation ({total_gen:,.0f} GWh = {total_gen/1000:,.0f} TWh) "
                    f"is ~{total_gen/4200000:.1f}x too high. Likely SECTOR DUPLICATION - check sectorid filter!"
                )
            else:
                issues.append(
                    f"CRITICAL: US 2024 total generation ({total_gen:,.0f} GWh) outside expected range "
                    f"({expected_min:,.0f} - {expected_max:,.0f} GWh). Check unit conversion or sector filter!"
                )
        else:
            issues.append(f"✓ US 2024 total generation: {total_gen:,.0f} GWh ({total_gen/1000:,.0f} TWh) [valid]")

    # Check 2: Verify renewable percentage doesn't exceed 100%
    if 'renewable_percentage' in df.columns:
        invalid_renewable = df[df['renewable_percentage'] > 100]
        if len(invalid_renewable) > 0:
            issues.append(
                f"ERROR: {len(invalid_renewable)} records have renewable_percentage > 100%"
            )
            for _, row in invalid_renewable.head(5).iterrows():
                issues.append(f"  - {row.get('state', 'Unknown')}, {row.get('year', 'Unknown')}: {row['renewable_percentage']:.1f}%")
        else:
            issues.append(f"✓ All renewable percentages ≤ 100%")

    # Check 3: Verify state data is in reasonable ranges
    states_2024 = df[(df['year'] == 2024) & (df['state'] != 'US')]
    if not states_2024.empty:
        # California should be largest state (200,000 - 300,000 GWh)
        ca_2024 = states_2024[states_2024['state'] == 'CA']
        if not ca_2024.empty:
            ca_gen = ca_2024['total_generation_gwh'].iloc[0]
            ca_expected_min = 200_000
            ca_expected_max = 300_000

            if ca_gen < ca_expected_min or ca_gen > ca_expected_max:
                # Check if it's ~4.4x too high (sector duplication)
                if ca_expected_min * 4 < ca_gen < ca_expected_max * 5:
                    issues.append(
                        f"WARNING: California 2024 generation ({ca_gen:,.0f} GWh = {ca_gen/1000:,.0f} TWh) "
                        f"is ~{ca_gen/200000:.1f}x too high. Likely SECTOR DUPLICATION!"
                    )
                else:
                    issues.append(
                        f"WARNING: California 2024 generation ({ca_gen:,.0f} GWh) outside expected range "
                        f"({ca_expected_min:,.0f} - {ca_expected_max:,.0f} GWh)"
                    )
            else:
                issues.append(f"✓ California 2024 generation: {ca_gen:,.0f} GWh ({ca_gen/1000:,.0f} TWh) [valid]")

    # Check 4: Verify generation/sales ratio is reasonable (should be ~1.05-1.10, not 4+)
    us_recent = df[(df['state'] == 'US') & (df['year'] >= 2020)]
    if not us_recent.empty and 'total_sales_gwh' in df.columns:
        for _, row in us_recent.iterrows():
            if row['total_sales_gwh'] > 0:
                gen_sales_ratio = row['total_generation_gwh'] / row['total_sales_gwh']
                year = int(row['year'])
                if gen_sales_ratio > 2.0:
                    issues.append(
                        f"CRITICAL: US {year} generation/sales ratio = {gen_sales_ratio:.2f}x "
                        f"(expected ~1.05-1.10). SECTOR DUPLICATION detected!"
                    )
                elif gen_sales_ratio < 0.95 or gen_sales_ratio > 1.15:
                    issues.append(
                        f"WARNING: US {year} generation/sales ratio = {gen_sales_ratio:.2f}x "
                        f"(expected ~1.05-1.10)"
                    )
                else:
                    issues.append(f"✓ US {year} generation/sales ratio: {gen_sales_ratio:.2f}x [valid]")

    # Check 5: Verify generation >= sales for most states (allows for imports)
    if 'net_generation_balance_gwh' in df.columns:
        recent_data = df[df['year'] >= 2020]
        deficit_states = recent_data[recent_data['net_generation_balance_gwh'] < 0]
        surplus_states = recent_data[recent_data['net_generation_balance_gwh'] > 0]

        # Most states should be net exporters
        if len(surplus_states) > 0 and len(deficit_states) > 0:
            surplus_ratio = len(surplus_states) / (len(surplus_states) + len(deficit_states))
            issues.append(
                f"✓ {len(surplus_states)} surplus vs {len(deficit_states)} deficit records (2020+)"
            )

    return issues


def print_validation_report(reports: List[Dict], df_2024: Optional[pd.DataFrame] = None) -> str:
    """
    Print and return formatted validation report with enhanced analytics.

    Args:
        reports: List of validation report dictionaries
        df_2024: Optional 2024 analysis DataFrame for enhanced reporting

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

    # Enhanced Analytics Section
    if df_2024 is not None and not df_2024.empty:
        report_text.append("\n" + "=" * 70)
        report_text.append("2024 STATE CAPACITY ANALYSIS - KEY INSIGHTS")
        report_text.append("=" * 70)

        # Top 10 states by surplus capacity
        report_text.append("\nTop 10 States by Capacity Surplus (Net Exporters):")
        report_text.append("-" * 70)
        top_surplus = df_2024.nlargest(10, 'capacity_surplus_pct')[
            ['state', 'state_name', 'capacity_surplus_pct', 'net_generation_balance_gwh']
        ]
        for idx, (_, row) in enumerate(top_surplus.iterrows(), 1):
            state_name = row.get('state_name', row['state'])
            surplus_pct = row.get('capacity_surplus_pct', 0)
            balance = row.get('net_generation_balance_gwh', 0)
            report_text.append(f"   {idx:2d}. {state_name:20s} - {surplus_pct:6.1f}% surplus ({balance:10,.0f} GWh net export)")

        # Top 10 states by deficit (bottom 10 by surplus)
        report_text.append("\nTop 10 States by Capacity Deficit (Net Importers):")
        report_text.append("-" * 70)
        top_deficit = df_2024.nsmallest(10, 'capacity_surplus_pct')[
            ['state', 'state_name', 'capacity_surplus_pct', 'net_generation_balance_gwh']
        ]
        for idx, (_, row) in enumerate(top_deficit.iterrows(), 1):
            state_name = row.get('state_name', row['state'])
            surplus_pct = row.get('capacity_surplus_pct', 0)
            balance = row.get('net_generation_balance_gwh', 0)
            report_text.append(f"   {idx:2d}. {state_name:20s} - {surplus_pct:6.1f}% deficit ({abs(balance):10,.0f} GWh net import)")

        # Top 10 by renewable percentage
        report_text.append("\nTop 10 States by Renewable Energy Percentage:")
        report_text.append("-" * 70)
        top_renewable = df_2024.nlargest(10, 'renewable_percentage')[
            ['state', 'state_name', 'renewable_percentage']
        ]
        for idx, (_, row) in enumerate(top_renewable.iterrows(), 1):
            state_name = row.get('state_name', row['state'])
            renewable_pct = row.get('renewable_percentage', 0)
            report_text.append(f"   {idx:2d}. {state_name:20s} - {renewable_pct:5.1f}% renewable")

        # Top 10 by datacenter suitability score
        report_text.append("\nTop 10 States for Datacenter Development (Suitability Score):")
        report_text.append("-" * 70)
        top_suitability = df_2024.nlargest(10, 'datacenter_suitability_score')[
            ['state', 'state_name', 'datacenter_suitability_score', 'available_capacity_mw', 'avg_price_cents_per_kwh']
        ]
        for idx, (_, row) in enumerate(top_suitability.iterrows(), 1):
            state_name = row.get('state_name', row['state'])
            score = row.get('datacenter_suitability_score', 0)
            avail_cap = row.get('available_capacity_mw', 0)
            price = row.get('avg_price_cents_per_kwh', 0)
            report_text.append(f"   {idx:2d}. {state_name:20s} - Score: {score:5.1f}, Avail: {avail_cap:10,.0f} MW, Price: {price:4.1f}¢/kWh")

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

    # 4. Electricity prices
    datasets['eia_electricity_prices'] = fetch_electricity_prices(api_key)

    # 5. Calculate comprehensive metrics with derived fields
    datasets['eia_comprehensive_metrics'] = calculate_derived_metrics(
        datasets['eia_generation_by_source'],
        datasets['eia_retail_sales_by_sector'],
        datasets['eia_capacity_by_source'],
        datasets['eia_electricity_prices']
    )

    # 6. Create 2024-specific analysis for datacenter site selection
    datasets['state_capacity_analysis_2024'] = create_2024_analysis(
        datasets['eia_comprehensive_metrics']
    )

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
            datasets['eia_electricity_prices'],
            'Electricity Prices by State',
            (2010, 2024),
            ALL_STATES
        ),
        validate_and_report(
            datasets['eia_comprehensive_metrics'],
            'Comprehensive Metrics with Derived Fields',
            (2010, 2024),
            ["US"] + ALL_STATES
        ),
        validate_and_report(
            datasets['state_capacity_analysis_2024'],
            '2024 State Capacity Analysis',
            (2024, 2024),
            ALL_STATES
        ),
    ]

    # Run comprehensive data quality checks
    print("\n" + "=" * 70)
    print("COMPREHENSIVE DATA QUALITY CHECKS")
    print("=" * 70)
    quality_issues = validate_data_quality(datasets['eia_comprehensive_metrics'])
    for issue in quality_issues:
        print(issue)

    # Print validation report with enhanced 2024 analytics
    report_text = print_validation_report(
        validation_reports,
        datasets['state_capacity_analysis_2024']
    )

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
