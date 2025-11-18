#!/usr/bin/env python3
"""
EIA-923 Excel File Processor

Processes downloaded EIA-923 Excel files (2014-2024) to extract
utility-scale electricity generation data by state, year, and fuel type.

Input: EIA923/*.xlsx files
Output: Clean CSV with state-level generation data in GWh
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Fuel type code mapping - maps EIA codes to clean energy source categories
FUEL_MAPPING = {
    # Coal
    'BIT': 'coal',      # Bituminous coal
    'SUB': 'coal',      # Subbituminous coal
    'LIG': 'coal',      # Lignite
    'ANT': 'coal',      # Anthracite
    'RC': 'coal',       # Refined coal
    'SGC': 'coal',      # Coal-derived synthesis gas
    'WC': 'coal',       # Waste coal

    # Natural Gas
    'NG': 'gas',        # Natural gas
    'BFG': 'gas',       # Blast furnace gas
    'OG': 'gas',        # Other gas

    # Nuclear
    'NUC': 'nuclear',   # Nuclear

    # Hydro
    'WAT': 'hydro',     # Conventional hydroelectric

    # Solar
    'SUN': 'solar',     # Solar

    # Wind
    'WND': 'wind',      # Wind

    # Petroleum/Oil
    'DFO': 'oil',       # Distillate fuel oil
    'RFO': 'oil',       # Residual fuel oil
    'WO': 'oil',        # Waste oil
    'KER': 'oil',       # Kerosene
    'PC': 'oil',        # Petroleum coke
    'JF': 'oil',        # Jet fuel

    # Biomass/Other renewables
    'WDS': 'other',     # Wood/wood waste solids
    'OBL': 'other',     # Other biomass liquids
    'OBS': 'other',     # Other biomass solids
    'BLQ': 'other',     # Black liquor
    'WDL': 'other',     # Wood waste liquids
    'AB': 'other',      # Agricultural byproducts
    'MSW': 'other',     # Municipal solid waste
    'LFG': 'other',     # Landfill gas
    'OBG': 'other',     # Other biomass gas
    'GEO': 'other',     # Geothermal
    'PUR': 'other',     # Purchased steam
    'OTH': 'other',     # Other
    'MWH': 'other',     # Electricity from batteries/storage
    'TDF': 'other',     # Tire-derived fuel
}


def read_eia923_file(filepath):
    """
    Read EIA-923 Excel file and extract generation data.

    Args:
        filepath: Path to EIA-923 Excel file

    Returns:
        DataFrame with columns [year, state, fuel_code, net_generation_mwh]
        or None if file cannot be read
    """
    print(f"\n  Reading: {filepath.name}")

    try:
        # Read Page 1 Generation and Fuel Data sheet
        # Skip first 5 rows (headers), row 6 (index 5) has column names
        df = pd.read_excel(
            filepath,
            sheet_name='Page 1 Generation and Fuel Data',
            header=5  # Row 6 (0-indexed as 5) contains column headers
        )

        # Expected columns (with newlines as they appear in Excel)
        cols_needed = {
            'Plant State': 'state',
            'Reported\nFuel Type Code': 'fuel_code',
            'YEAR': 'year',
            'Net Generation\n(Megawatthours)': 'net_generation_mwh'
        }

        # Check if all required columns exist
        missing_cols = []
        for col in cols_needed.keys():
            if col not in df.columns:
                missing_cols.append(col)

        if missing_cols:
            print(f"    ✗ Missing columns: {missing_cols}")
            print(f"    Available columns: {df.columns.tolist()[:10]}...")
            return None

        # Extract and rename needed columns
        df_clean = df[list(cols_needed.keys())].copy()
        df_clean.columns = list(cols_needed.values())

        # Remove rows where state or net_generation is missing/null
        initial_rows = len(df_clean)
        df_clean = df_clean.dropna(subset=['state', 'net_generation_mwh'])

        # Convert net_generation to numeric (handle any text/errors)
        df_clean['net_generation_mwh'] = pd.to_numeric(
            df_clean['net_generation_mwh'],
            errors='coerce'
        )

        # Remove rows with NaN generation after conversion
        df_clean = df_clean.dropna(subset=['net_generation_mwh'])

        # Remove rows with zero generation (but keep small negative values - generator auxiliary use)
        df_clean = df_clean[df_clean['net_generation_mwh'] != 0]

        # Clean state codes (should be 2-letter codes)
        df_clean['state'] = df_clean['state'].astype(str).str.strip().str.upper()
        df_clean = df_clean[df_clean['state'].str.len() == 2]

        # Clean fuel codes
        df_clean['fuel_code'] = df_clean['fuel_code'].astype(str).str.strip().str.upper()

        # Convert year to int
        df_clean['year'] = pd.to_numeric(df_clean['year'], errors='coerce')
        df_clean = df_clean.dropna(subset=['year'])
        df_clean['year'] = df_clean['year'].astype(int)

        print(f"    ✓ Loaded {len(df_clean):,} records (from {initial_rows:,} total rows)")
        print(f"      Year: {df_clean['year'].unique()}")
        print(f"      States: {df_clean['state'].nunique()}")
        print(f"      Fuel types: {df_clean['fuel_code'].nunique()}")

        return df_clean

    except Exception as e:
        print(f"    ✗ Error reading file: {e}")
        return None


def process_all_eia923_files(directory='EIA923'):
    """
    Process all EIA-923 files in directory.

    Args:
        directory: Path to directory containing EIA-923 Excel files

    Returns:
        Combined DataFrame with all years, or None if no files found
    """
    directory_path = Path(directory)

    if not directory_path.exists():
        print(f"✗ ERROR: Directory '{directory}' not found!")
        return None

    # Get all Excel files matching pattern
    files = sorted(directory_path.glob('EIA923_Schedules_*.xlsx'))

    if not files:
        print(f"✗ ERROR: No EIA-923 files found in '{directory}'")
        print(f"  Expected pattern: EIA923_Schedules_*.xlsx")
        return None

    print(f"\nFound {len(files)} EIA-923 files:")
    for f in files:
        print(f"  - {f.name}")

    all_data = []

    print("\nProcessing files:")
    for filepath in files:
        df = read_eia923_file(filepath)

        if df is not None:
            all_data.append(df)

    # Combine all dataframes
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n✓ Combined data:")
        print(f"  Total records: {len(combined):,}")
        print(f"  Years covered: {sorted(combined['year'].unique())}")
        print(f"  States: {combined['state'].nunique()}")
        print(f"  Unique fuel codes: {combined['fuel_code'].nunique()}")
        return combined
    else:
        print("\n✗ No data loaded from any file")
        return None


def map_fuel_to_source(df, fuel_mapping=FUEL_MAPPING):
    """
    Map EIA fuel type codes to clean energy source categories.

    Args:
        df: DataFrame with 'fuel_code' column
        fuel_mapping: Dictionary mapping fuel codes to source names

    Returns:
        DataFrame with 'energy_source' column added
    """
    df = df.copy()

    # Map fuel codes to sources
    df['energy_source'] = df['fuel_code'].map(fuel_mapping)

    # Check for unmapped fuel codes
    unmapped = df[df['energy_source'].isna()]['fuel_code'].unique()
    if len(unmapped) > 0:
        print(f"\n⚠ WARNING: Found {len(unmapped)} unmapped fuel codes:")
        print(f"  Codes: {sorted(unmapped)}")
        unmapped_rows = df['energy_source'].isna().sum()
        total_mwh = df[df['energy_source'].isna()]['net_generation_mwh'].sum()
        print(f"  Rows affected: {unmapped_rows:,} ({unmapped_rows/len(df)*100:.2f}%)")
        print(f"  Total generation: {total_mwh:,.0f} MWh ({total_mwh/1e6:.2f} TWh)")
        print(f"  → Setting all unmapped codes to 'other'")
        df.loc[df['energy_source'].isna(), 'energy_source'] = 'other'

    return df


def aggregate_by_state_year_source(df):
    """
    Aggregate generation data by state, year, and energy source.

    Args:
        df: DataFrame with year, state, energy_source, net_generation_mwh

    Returns:
        DataFrame with pivoted columns for each energy source
        Format: [year, state, coal_generation_mwh, gas_generation_mwh, ...]
    """
    # Group and sum
    agg = df.groupby(['year', 'state', 'energy_source'])['net_generation_mwh'].sum().reset_index()

    # Pivot to wide format
    wide = agg.pivot_table(
        index=['year', 'state'],
        columns='energy_source',
        values='net_generation_mwh',
        fill_value=0
    ).reset_index()

    # Ensure all expected columns exist
    expected_sources = ['coal', 'gas', 'nuclear', 'hydro', 'solar', 'wind', 'oil', 'other']
    for source in expected_sources:
        if source not in wide.columns:
            wide[source] = 0

    # Calculate total
    source_cols = [col for col in expected_sources if col in wide.columns]
    wide['total'] = wide[source_cols].sum(axis=1)

    # Rename columns to match our schema
    rename_map = {
        'coal': 'coal_generation_mwh',
        'gas': 'gas_generation_mwh',
        'nuclear': 'nuclear_generation_mwh',
        'hydro': 'hydro_generation_mwh',
        'solar': 'solar_generation_mwh',
        'wind': 'wind_generation_mwh',
        'oil': 'oil_generation_mwh',
        'other': 'other_generation_mwh',
        'total': 'total_generation_mwh'
    }

    wide = wide.rename(columns=rename_map)

    # Sort by year and state
    wide = wide.sort_values(['year', 'state']).reset_index(drop=True)

    return wide


def add_us_total(df):
    """
    Add a 'US' row for each year with national totals.

    Args:
        df: DataFrame with state-level generation data

    Returns:
        DataFrame with US totals added
    """
    # Columns to sum
    gen_cols = [col for col in df.columns if col.endswith('_generation_mwh')]

    # Group by year and sum across all states
    us_totals = df.groupby('year')[gen_cols].sum().reset_index()
    us_totals['state'] = 'US'

    # Combine with state data
    combined = pd.concat([df, us_totals], ignore_index=True)
    combined = combined.sort_values(['year', 'state']).reset_index(drop=True)

    return combined


def convert_mwh_to_gwh(df):
    """
    Convert megawatthours (MWh) to gigawatthours (GWh).
    1 GWh = 1,000 MWh

    Args:
        df: DataFrame with *_generation_mwh columns

    Returns:
        DataFrame with *_generation_gwh columns (MWh columns removed)
    """
    df = df.copy()

    # Find all generation columns
    mwh_cols = [col for col in df.columns if col.endswith('_generation_mwh')]

    # Convert to GWh
    for col in mwh_cols:
        new_col = col.replace('_mwh', '_gwh')
        df[new_col] = df[col] / 1000

    # Drop MWh columns
    df = df.drop(columns=mwh_cols)

    return df


def validate_data(df):
    """
    Validate the processed data for correctness.

    Args:
        df: Final processed DataFrame with GWh values
    """
    print("\n" + "="*70)
    print("DATA VALIDATION")
    print("="*70)

    # Check US 2024 total
    us_2024 = df[(df['year'] == 2024) & (df['state'] == 'US')]
    if len(us_2024) > 0:
        total_gwh = us_2024['total_generation_gwh'].values[0]
        total_twh = total_gwh / 1000

        print(f"\nUS 2024 Total: {total_gwh:,.0f} GWh ({total_twh:,.2f} TWh)")

        if 4_000_000 < total_gwh < 4_500_000:
            print("  ✓ CORRECT: Value is in expected range (4.0-4.5 million GWh)")
        else:
            print(f"  ⚠ WARNING: Expected 4.0-4.5 million GWh, got {total_gwh:,.0f}")
    else:
        print("\n⚠ No US 2024 data found")

    # Check California 2024
    ca_2024 = df[(df['year'] == 2024) & (df['state'] == 'CA')]
    if len(ca_2024) > 0:
        ca_total_gwh = ca_2024['total_generation_gwh'].values[0]
        ca_total_twh = ca_total_gwh / 1000

        print(f"\nCA 2024 Total: {ca_total_gwh:,.0f} GWh ({ca_total_twh:,.2f} TWh)")

        if 180_000 < ca_total_gwh < 250_000:
            print("  ✓ CORRECT: California in expected range (180-250k GWh)")
        else:
            print(f"  ⚠ WARNING: Expected 180-250k GWh, got {ca_total_gwh:,.0f}")
    else:
        print("\n⚠ No CA 2024 data found")

    # Check Texas 2024
    tx_2024 = df[(df['year'] == 2024) & (df['state'] == 'TX')]
    if len(tx_2024) > 0:
        tx_total_gwh = tx_2024['total_generation_gwh'].values[0]
        tx_total_twh = tx_total_gwh / 1000

        print(f"\nTX 2024 Total: {tx_total_gwh:,.0f} GWh ({tx_total_twh:,.2f} TWh)")

        if 500_000 < tx_total_gwh < 650_000:
            print("  ✓ CORRECT: Texas in expected range (500-650k GWh)")
        else:
            print(f"  ⚠ WARNING: Expected 500-650k GWh, got {tx_total_gwh:,.0f}")
    else:
        print("\n⚠ No TX 2024 data found")

    # Check for negative values
    gen_cols = [col for col in df.columns if '_generation_gwh' in col]
    negative_count = (df[gen_cols] < 0).sum().sum()
    if negative_count == 0:
        print("\n✓ No negative values found")
    else:
        print(f"\n⚠ Found {negative_count} negative values (may be normal for auxiliary use)")

    # Check year coverage
    years = sorted(df['year'].unique())
    print(f"\n✓ Years covered: {years[0]}-{years[-1]} ({len(years)} years)")

    # Check states
    states_no_us = df[df['state'] != 'US']['state'].nunique()
    print(f"✓ Number of states (excluding US): {states_no_us}")

    # Check completeness - should have data for all years for major states
    expected_years = list(range(2014, 2025))
    for state in ['US', 'CA', 'TX', 'NY', 'FL']:
        state_years = sorted(df[df['state'] == state]['year'].unique())
        if state_years == expected_years:
            print(f"  ✓ {state}: Complete data for all years")
        else:
            missing = set(expected_years) - set(state_years)
            print(f"  ⚠ {state}: Missing years {missing}")

    print("\n" + "="*70)


def main():
    """
    Main execution function.
    """
    print("="*70)
    print("EIA-923 DATA PROCESSING")
    print("Processing downloaded EIA-923 Excel files (2014-2024)")
    print("="*70)

    # Step 1: Load all files
    print("\nStep 1: Loading EIA-923 files from EIA923/ directory...")
    raw_data = process_all_eia923_files('EIA923')

    if raw_data is None:
        print("\n✗ Failed to load data. Exiting.")
        print("\nPlease ensure:")
        print("  1. EIA923/ directory exists")
        print("  2. Excel files are named: EIA923_Schedules_2_3_4_5_M_12_YYYY_Final.xlsx")
        print("  3. Files contain 'Page 1 Generation and Fuel Data' sheet")
        return None

    # Step 2: Map fuel codes
    print("\nStep 2: Mapping fuel codes to energy sources...")
    data = map_fuel_to_source(raw_data)

    # Step 3: Aggregate
    print("\nStep 3: Aggregating by state, year, and source...")
    aggregated = aggregate_by_state_year_source(data)
    print(f"  ✓ Aggregated to {len(aggregated):,} state-year records")

    # Step 4: Add US totals
    print("\nStep 4: Adding US national totals...")
    with_us = add_us_total(aggregated)
    print(f"  ✓ Total records with US: {len(with_us):,}")

    # Step 5: Convert to GWh
    print("\nStep 5: Converting MWh to GWh...")
    final = convert_mwh_to_gwh(with_us)
    print(f"  ✓ Converted all generation values to GWh")

    # Step 6: Validate
    validate_data(final)

    # Step 7: Save
    print("\nStep 7: Saving outputs...")

    # Save main generation file
    output_file = 'eia_generation_by_source_2014_2024.csv'
    final.to_csv(output_file, index=False)
    print(f"  ✓ Saved CSV: {output_file}")

    # Save Excel with multiple sheets
    excel_file = 'eia_generation_by_source_2014_2024.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        final.to_excel(writer, sheet_name='generation_by_source', index=False)

        # Add a US summary sheet
        us_summary = final[final['state'] == 'US'][
            ['year', 'coal_generation_gwh', 'gas_generation_gwh',
             'nuclear_generation_gwh', 'hydro_generation_gwh',
             'solar_generation_gwh', 'wind_generation_gwh',
             'oil_generation_gwh', 'other_generation_gwh',
             'total_generation_gwh']
        ].copy()
        us_summary.to_excel(writer, sheet_name='us_total_summary', index=False)

        # Add state rankings for 2024
        state_2024 = final[(final['year'] == 2024) & (final['state'] != 'US')].copy()
        state_2024 = state_2024.sort_values('total_generation_gwh', ascending=False)
        state_2024.to_excel(writer, sheet_name='state_rankings_2024', index=False)

    print(f"  ✓ Saved Excel: {excel_file}")

    # Print summary
    print("\n" + "="*70)
    print("PROCESSING COMPLETE")
    print("="*70)
    print(f"\nFinal dataset shape: {final.shape[0]} rows × {final.shape[1]} columns")
    print(f"Years: {final['year'].min()} - {final['year'].max()}")
    print(f"States (including US): {final['state'].nunique()}")

    print("\nColumns:")
    for col in final.columns:
        print(f"  - {col}")

    print("\nSample data (US 2024):")
    us_2024 = final[(final['year'] == 2024) & (final['state'] == 'US')]
    if len(us_2024) > 0:
        print("\n" + us_2024.to_string(index=False))

    print("\n" + "="*70)

    return final


if __name__ == "__main__":
    df = main()
    if df is not None:
        print("\n✓ SUCCESS: Data processing completed")
        print(f"✓ Output files:")
        print(f"  - eia_generation_by_source_2014_2024.csv")
        print(f"  - eia_generation_by_source_2014_2024.xlsx")
    else:
        print("\n✗ FAILED: Data processing encountered errors")
        sys.exit(1)
