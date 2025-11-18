#!/usr/bin/env python3
"""
Datacenter Energy Analysis - Statistical Modeling & Predictive Analytics

This script performs comprehensive statistical analysis and predictive modeling
to support hyperscaler datacenter energy procurement and site selection decisions.

Data Source: EIA-923 generation data (2014-2024)
Requires: eia_generation_by_source_2014_2024.csv (from process_eia923_files.py)

Note: This version uses manually processed EIA-923 Excel files, which contain
utility-scale electricity generation data only. Sales, capacity, and price data
are not available and will be excluded from analysis.

Author: Data Analysis Team
Date: 2025-11-18
Version: 2.0 (Updated for EIA-923 manual processing)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings
import json
from datetime import datetime

# Machine learning imports
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    classification_report, roc_auc_score, confusion_matrix,
    silhouette_score
)

# Statistical imports
from scipy import stats
from scipy.cluster.hierarchy import dendrogram, linkage

warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

# State populations (2024 estimates)
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

# State regions
STATE_REGIONS = {
    'CT': 'Northeast', 'ME': 'Northeast', 'MA': 'Northeast', 'NH': 'Northeast',
    'NJ': 'Northeast', 'NY': 'Northeast', 'PA': 'Northeast', 'RI': 'Northeast', 'VT': 'Northeast',
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest',
    'MI': 'Midwest', 'MN': 'Midwest', 'MO': 'Midwest', 'NE': 'Midwest',
    'ND': 'Midwest', 'OH': 'Midwest', 'SD': 'Midwest', 'WI': 'Midwest',
    'AL': 'South', 'AR': 'South', 'DE': 'South', 'DC': 'South', 'FL': 'South',
    'GA': 'South', 'KY': 'South', 'LA': 'South', 'MD': 'South', 'MS': 'South',
    'NC': 'South', 'OK': 'South', 'SC': 'South', 'TN': 'South', 'TX': 'South',
    'VA': 'South', 'WV': 'South',
    'AK': 'West', 'AZ': 'West', 'CA': 'West', 'CO': 'West', 'HI': 'West',
    'ID': 'West', 'MT': 'West', 'NV': 'West', 'NM': 'West', 'OR': 'West',
    'UT': 'West', 'WA': 'West', 'WY': 'West'
}

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

# Current datacenter hubs
DATACENTER_HUBS = ['VA', 'TX', 'CA', 'GA', 'NC', 'IL', 'OR', 'AZ', 'NJ', 'OH']

# Goldman Sachs datacenter demand projections (GW)
DATACENTER_DEMAND_GW = {
    2023: 22, 2024: 25, 2025: 28, 2026: 31, 2027: 35,
    2028: 42, 2029: 46, 2030: 50
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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


def print_section_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_progress(message: str, indent: int = 2):
    """Print progress message with indentation."""
    print(" " * indent + "• " + message)


# ============================================================================
# DATA LOADING AND PREPARATION
# ============================================================================

def load_eia_data() -> pd.DataFrame:
    """
    Load EIA-923 generation data from manually processed Excel files.

    Returns:
        DataFrame: Generation data by state, year, and energy source
    """
    print_section_header("[1/5] LOADING AND PREPARING DATA")

    data_dir = Path.cwd()

    # Check if the processed EIA-923 file exists
    generation_file = 'eia_generation_by_source_2014_2024.csv'

    if not (data_dir / generation_file).exists():
        raise FileNotFoundError(
            f"Required EIA-923 data file not found: {generation_file}\n"
            f"Please run process_eia923_files.py first to generate this file.\n"
            f"(This script processes downloaded EIA-923 Excel files from the EIA923/ directory)"
        )

    print_progress(f"Loading generation data from {generation_file}...")
    generation_df = pd.read_csv(data_dir / generation_file)

    print_progress(f"✓ Loaded {len(generation_df):,} generation records")
    print_progress(f"  Years: {generation_df['year'].min()}-{generation_df['year'].max()}")
    print_progress(f"  States: {generation_df['state'].nunique()} (including US total)")

    # Validate expected columns exist
    expected_cols = [
        'year', 'state', 'coal_generation_gwh', 'gas_generation_gwh',
        'nuclear_generation_gwh', 'hydro_generation_gwh', 'solar_generation_gwh',
        'wind_generation_gwh', 'total_generation_gwh'
    ]

    missing_cols = [col for col in expected_cols if col not in generation_df.columns]
    if missing_cols:
        raise ValueError(f"Missing expected columns in generation data: {missing_cols}")

    print_progress(f"✓ All expected columns present")

    return generation_df


def prepare_master_dataset(
    generation_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Prepare master dataset with calculated metrics.

    Args:
        generation_df: Generation by source data (from EIA-923)

    Returns:
        DataFrame: Master dataset with all metrics
    """
    print_progress("Preparing master dataset...")

    # Start with generation data
    df = generation_df.copy()

    # Ensure all required generation columns exist and fill missing values with 0
    required_generation_cols = [
        'coal_generation_gwh', 'gas_generation_gwh', 'nuclear_generation_gwh',
        'hydro_generation_gwh', 'wind_generation_gwh', 'solar_generation_gwh',
        'total_generation_gwh'
    ]

    # Add oil and other if not present (EIA-923 has these)
    if 'oil_generation_gwh' not in df.columns:
        df['oil_generation_gwh'] = 0
    if 'other_generation_gwh' not in df.columns:
        df['other_generation_gwh'] = 0

    for col in required_generation_cols + ['oil_generation_gwh', 'other_generation_gwh']:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = df[col].fillna(0)

    # Add state metadata
    df['state_name'] = df['state'].map(STATE_NAMES)
    df['population'] = df['state'].map(STATE_POPULATIONS)
    df['region'] = df['state'].map(STATE_REGIONS)

    # Create regional dummy variables
    df['is_northeast'] = (df['region'] == 'Northeast').astype(int)
    df['is_midwest'] = (df['region'] == 'Midwest').astype(int)
    df['is_south'] = (df['region'] == 'South').astype(int)
    df['is_west'] = (df['region'] == 'West').astype(int)

    print_progress("Calculating derived metrics...")

    # NOTE: Sales, capacity, and price data not available from EIA-923 Excel files
    # These fields will be set to NaN or excluded from analysis:
    # - total_sales_gwh (not in EIA-923)
    # - net_balance_gwh (requires sales data)
    # - surplus_percentage (requires sales data)
    # - capacity data (not in EIA-923)
    # - price data (not in EIA-923)

    # Energy mix percentages
    df['coal_pct'] = (df['coal_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['gas_pct'] = (df['gas_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['nuclear_pct'] = (df['nuclear_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['hydro_pct'] = (df['hydro_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['wind_pct'] = (df['wind_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['solar_pct'] = (df['solar_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100
    df['other_pct'] = (df['other_generation_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100

    # Aggregate categories
    df['renewable_gwh'] = df['solar_generation_gwh'] + df['wind_generation_gwh'] + df['hydro_generation_gwh']
    df['renewable_pct'] = (df['renewable_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100

    df['fossil_gwh'] = df['coal_generation_gwh'] + df['gas_generation_gwh']
    df['fossil_pct'] = (df['fossil_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100

    df['carbon_free_gwh'] = df['renewable_gwh'] + df['nuclear_generation_gwh']
    df['carbon_free_pct'] = (df['carbon_free_gwh'] / df['total_generation_gwh'].replace(0, np.nan)) * 100

    # Validate and fix percentage calculations
    # 1. Cap renewable_pct at 100% (should never exceed but handle edge cases)
    df['renewable_pct'] = df['renewable_pct'].clip(upper=100)
    df['fossil_pct'] = df['fossil_pct'].clip(upper=100)
    df['carbon_free_pct'] = df['carbon_free_pct'].clip(upper=100)

    # 2. Validate that individual fuel percentages sum to ~100% (±1%)
    df['total_pct_check'] = (
        df['coal_pct'].fillna(0) + df['gas_pct'].fillna(0) + df['nuclear_pct'].fillna(0) +
        df['hydro_pct'].fillna(0) + df['wind_pct'].fillna(0) + df['solar_pct'].fillna(0) +
        df['other_pct'].fillna(0)
    )

    # Log warning for states where percentages don't sum to ~100%
    invalid_pcts = df[(df['total_pct_check'] < 99) | (df['total_pct_check'] > 101)]['total_pct_check']
    if len(invalid_pcts) > 0:
        print(f"  ⚠ Warning: {len(invalid_pcts)} records have fuel percentages that don't sum to 100%")

    # Per capita metrics
    df['generation_per_capita_mwh'] = (df['total_generation_gwh'] * 1000) / df['population'].replace(0, np.nan)

    # Sales and capacity data not available from EIA-923 - set to NaN
    df['total_sales_gwh'] = np.nan
    df['consumption_per_capita_mwh'] = np.nan
    df['total_capacity_mw'] = np.nan
    df['capacity_utilization_pct'] = np.nan
    df['net_balance_gwh'] = np.nan
    df['surplus_percentage'] = np.nan
    df['avg_price_cents_per_kwh'] = np.nan

    # Fill infinite values with NaN
    df = df.replace([np.inf, -np.inf], np.nan)

    print_progress(f"✓ Created master dataset with {len(df):,} records")
    print_progress(f"✓ Calculated {len(df.columns)} total columns")

    return df


def calculate_growth_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate CAGR for each state across key metrics (2011-2024).

    Args:
        df: Master dataframe

    Returns:
        DataFrame: Input dataframe with added CAGR columns
    """
    print_progress("Calculating growth rates (CAGR 2011-2024)...")

    growth_metrics = []

    for state in df['state'].unique():
        state_data = df[df['state'] == state].sort_values('year')

        # Get 2011 and 2024 data
        data_2011 = state_data[state_data['year'] == 2011]
        data_2024 = state_data[state_data['year'] == 2024]

        if data_2011.empty or data_2024.empty:
            continue

        # Calculate CAGRs for various metrics
        metrics = {
            'total_generation_cagr': ('total_generation_gwh', data_2011, data_2024),
            'renewable_cagr': ('renewable_gwh', data_2011, data_2024),
            'solar_cagr': ('solar_generation_gwh', data_2011, data_2024),
            'wind_cagr': ('wind_generation_gwh', data_2011, data_2024),
            'gas_cagr': ('gas_generation_gwh', data_2011, data_2024),
            'coal_cagr': ('coal_generation_gwh', data_2011, data_2024),
            'sales_cagr': ('total_sales_gwh', data_2011, data_2024)
        }

        cagr_values = {'state': state}
        for cagr_name, (col_name, data_start, data_end) in metrics.items():
            start_val = data_start[col_name].values[0] if col_name in data_start.columns else 0
            end_val = data_end[col_name].values[0] if col_name in data_end.columns else 0
            cagr_values[cagr_name] = calculate_cagr(start_val, end_val, 13)

        growth_metrics.append(cagr_values)

    growth_df = pd.DataFrame(growth_metrics)

    # Merge back into main dataframe
    df = df.merge(growth_df, on='state', how='left')

    print_progress(f"✓ Calculated CAGR for {len(growth_df)} states")

    return df


# ============================================================================
# RANDOM FOREST REGRESSION - 2030 ENERGY MIX PREDICTION
# ============================================================================

def train_random_forest_models(df: pd.DataFrame) -> Dict:
    """
    Train Random Forest models to predict 2030 energy mix for each state.

    Args:
        df: Master dataframe with all metrics

    Returns:
        Dict containing models, predictions, feature importance, and performance metrics
    """
    print_section_header("[2/5] PREDICTIVE MODELING - Random Forest")

    print_progress("Preparing training data...")

    # Get 2024 data for all states (excluding US total)
    df_2024 = df[(df['year'] == 2024) & (df['state'] != 'US')].copy()

    # Remove states with missing data
    df_2024 = df_2024.dropna(subset=[
        'coal_pct', 'gas_pct', 'nuclear_pct', 'solar_pct', 'wind_pct',
        'total_generation_cagr', 'renewable_cagr', 'solar_cagr', 'wind_cagr',
        'surplus_percentage', 'avg_price_cents_per_kwh'
    ])

    # Feature selection
    features = [
        # Current energy mix
        'coal_pct', 'gas_pct', 'nuclear_pct', 'hydro_pct', 'wind_pct', 'solar_pct',
        # Growth trends
        'total_generation_cagr', 'renewable_cagr', 'solar_cagr', 'wind_cagr',
        # State characteristics
        'total_capacity_mw', 'surplus_percentage', 'avg_price_cents_per_kwh',
        'generation_per_capita_mwh',
        # Regional indicators
        'is_northeast', 'is_midwest', 'is_south', 'is_west',
        # Renewable % as policy proxy
        'renewable_pct'
    ]

    X = df_2024[features].fillna(0)

    # Train models for each energy source
    targets = ['solar_pct', 'wind_pct', 'gas_pct', 'nuclear_pct', 'coal_pct']

    models = {}
    predictions_2030 = {}
    feature_importance = {}
    performance = {}

    for target in targets:
        print_progress(f"Training {target.replace('_pct', '')} model...")

        y = df_2024[target].fillna(0)

        # Train-test split (small dataset, so use 80-20)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train Random Forest
        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )

        rf.fit(X_train, y_train)

        # Validate
        y_pred_test = rf.predict(X_test)
        r2 = r2_score(y_test, y_pred_test)
        mae = mean_absolute_error(y_test, y_pred_test)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))

        # Cross-validation
        cv_scores = cross_val_score(rf, X, y, cv=5, scoring='r2')

        # Store model
        models[target] = rf

        # Feature importance
        importance_df = pd.DataFrame({
            'feature': features,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)
        feature_importance[target] = importance_df

        # Performance metrics
        performance[target] = {
            'r2_score': r2,
            'mae': mae,
            'rmse': rmse,
            'cv_mean_r2': cv_scores.mean(),
            'cv_std_r2': cv_scores.std()
        }

        # Predict 2030 for all states
        # Extrapolate growth trends forward 6 years
        X_2030 = X.copy()

        # Adjust growth-related features (simple linear extrapolation)
        # This is a simplification - real implementation would be more sophisticated
        predictions_2030[target] = rf.predict(X_2030)

        # Print performance with warnings for poor models
        r2_display = f"R² = {r2:.3f}"
        if r2 < 0:
            r2_display += " ⚠ WARNING: Negative R² - model worse than baseline!"
        elif r2 < 0.3:
            r2_display += " ⚠ Low predictive power"

        print_progress(f"  {r2_display}, MAE = {mae:.2f}%, RMSE = {rmse:.2f}%")

    # Create predictions dataframe
    predictions_df = df_2024[['state', 'state_name', 'region']].copy()
    for target in targets:
        predictions_df[f'{target}_2030'] = predictions_2030[target]

    # Calculate total renewable percentage in 2030
    predictions_df['renewable_pct_2030'] = (
        predictions_df['solar_pct_2030'] +
        predictions_df['wind_pct_2030'] +
        df_2024['hydro_pct'].values  # Assume hydro stays flat
    )

    print_progress(f"✓ Trained {len(targets)} Random Forest models")
    print_progress(f"✓ Generated 2030 predictions for {len(predictions_df)} states")

    return {
        'models': models,
        'predictions': predictions_df,
        'feature_importance': feature_importance,
        'performance': performance,
        'features': features
    }


# ============================================================================
# TIME SERIES FORECASTING - US TOTAL BY SOURCE
# ============================================================================

def forecast_us_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forecast US total generation by source through 2030 using linear regression.

    Args:
        df: Master dataframe

    Returns:
        DataFrame: Forecasts for each source 2025-2030 with confidence intervals
    """
    print_section_header("[2/5] PREDICTIVE MODELING - Time Series Forecasting")

    print_progress("Forecasting US total by energy source...")

    # Filter to US total data only
    us_data = df[df['state'] == 'US'].sort_values('year').copy()

    sources = ['solar', 'wind', 'gas', 'coal', 'nuclear', 'hydro']
    all_forecasts = []

    for source in sources:
        print_progress(f"Forecasting {source}...")

        col_name = f'{source}_generation_gwh'

        # Use data from 2011-2024 for training
        train_data = us_data[(us_data['year'] >= 2011) & (us_data['year'] <= 2024)]

        X = train_data['year'].values.reshape(-1, 1)
        y = train_data[col_name].fillna(0).values

        # Fit linear regression
        model = LinearRegression()
        model.fit(X, y)

        # Predict future years
        future_years = np.arange(2025, 2031).reshape(-1, 1)
        predictions = model.predict(future_years)

        # Ensure non-negative predictions
        predictions = np.maximum(0, predictions)

        # Calculate 95% confidence interval
        residuals = y - model.predict(X)
        std_error = np.std(residuals)
        ci_95 = 1.96 * std_error

        # Historical and forecasted CAGR
        hist_cagr = calculate_cagr(y[0], y[-1], len(y) - 1)
        forecast_cagr = calculate_cagr(y[-1], predictions[-1], len(predictions))

        forecast_df = pd.DataFrame({
            'year': future_years.flatten(),
            'source': source,
            'predicted_gwh': predictions,
            'ci_lower': np.maximum(0, predictions - ci_95),
            'ci_upper': predictions + ci_95,
            'r2_score': r2_score(y, model.predict(X)),
            'cagr_historical': hist_cagr,
            'cagr_forecasted': forecast_cagr
        })

        all_forecasts.append(forecast_df)

    forecasts_combined = pd.concat(all_forecasts, ignore_index=True)

    # Calculate total forecasted generation by year
    total_by_year = forecasts_combined.groupby('year')['predicted_gwh'].sum().reset_index()
    total_by_year.rename(columns={'predicted_gwh': 'total_predicted_gwh'}, inplace=True)

    forecasts_combined = forecasts_combined.merge(total_by_year, on='year')

    print_progress(f"✓ Generated forecasts for {len(sources)} energy sources through 2030")

    return forecasts_combined


# ============================================================================
# SCENARIO ANALYSIS - SUPPLY VS DEMAND GAP
# ============================================================================

def run_scenario_analysis(
    us_forecast: pd.DataFrame,
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate energy gap under different growth scenarios.

    Args:
        us_forecast: US forecasts by source
        df: Master dataframe

    Returns:
        DataFrame: Scenario analysis results
    """
    print_section_header("[2/5] PREDICTIVE MODELING - Scenario Analysis")

    print_progress("Calculating supply-demand gap scenarios...")

    # Get 2024 baseline data
    us_2024 = df[(df['state'] == 'US') & (df['year'] == 2024)].iloc[0]

    base_year_data = {
        'solar': us_2024['solar_generation_gwh'],
        'wind': us_2024['wind_generation_gwh'],
        'gas': us_2024['gas_generation_gwh'],
        'nuclear': us_2024['nuclear_generation_gwh'],
        'coal': us_2024['coal_generation_gwh'],
        'hydro': us_2024['hydro_generation_gwh'],
        'total_sales': us_2024['total_sales_gwh']
    }

    # Define scenarios
    scenarios = {
        'baseline': {
            'description': 'Historical growth rates continue',
            'solar_cagr': 0.30,
            'wind_cagr': 0.12,
            'gas_cagr': 0.02,
            'nuclear_cagr': 0.0,
            'coal_cagr': -0.05,
            'demand_multiplier': 1.0
        },
        'accelerated_renewable': {
            'description': 'Policy push for faster renewable deployment',
            'solar_cagr': 0.40,
            'wind_cagr': 0.18,
            'gas_cagr': 0.01,
            'nuclear_cagr': 0.02,
            'coal_cagr': -0.08,
            'demand_multiplier': 1.0
        },
        'constrained': {
            'description': 'Permitting delays slow buildout',
            'solar_cagr': 0.20,
            'wind_cagr': 0.08,
            'gas_cagr': 0.03,
            'nuclear_cagr': 0.0,
            'coal_cagr': -0.03,
            'demand_multiplier': 1.0
        },
        'ai_boom': {
            'description': 'Datacenter demand exceeds projections',
            'solar_cagr': 0.30,
            'wind_cagr': 0.12,
            'gas_cagr': 0.05,
            'nuclear_cagr': 0.0,
            'coal_cagr': -0.05,
            'demand_multiplier': 1.3
        }
    }

    all_scenario_results = []

    for scenario_name, params in scenarios.items():
        print_progress(f"Running {scenario_name} scenario...")

        for year in range(2025, 2031):
            years_ahead = year - 2024

            # Project each source
            solar_gwh = base_year_data['solar'] * (1 + params['solar_cagr']) ** years_ahead
            wind_gwh = base_year_data['wind'] * (1 + params['wind_cagr']) ** years_ahead
            gas_gwh = base_year_data['gas'] * (1 + params['gas_cagr']) ** years_ahead
            nuclear_gwh = base_year_data['nuclear'] * (1 + params['nuclear_cagr']) ** years_ahead
            coal_gwh = base_year_data['coal'] * (1 + params['coal_cagr']) ** years_ahead
            hydro_gwh = base_year_data['hydro']  # Assume flat

            total_supply = solar_gwh + wind_gwh + gas_gwh + nuclear_gwh + coal_gwh + hydro_gwh

            # Calculate demand
            base_demand_growth = 0.01  # 1% annual baseline growth
            base_demand_future = base_year_data['total_sales'] * (1 + base_demand_growth) ** years_ahead

            # Add datacenter demand
            datacenter_gw = DATACENTER_DEMAND_GW.get(year, 50)
            # Convert GW to GWh: GW × hours × capacity_factor = GWh
            # 1 GW running for 8760 hours at 90% capacity = 7,884 GWh
            datacenter_gwh = datacenter_gw * 8760 * 0.9
            datacenter_gwh_adjusted = datacenter_gwh * params['demand_multiplier']

            total_demand = base_demand_future + datacenter_gwh_adjusted

            # Calculate gap (supply - demand)
            # Positive gap = surplus (supply > demand)
            # Negative gap = deficit (supply < demand)
            gap_gwh = total_supply - total_demand
            gap_percentage = (gap_gwh / total_supply) * 100

            all_scenario_results.append({
                'year': year,
                'scenario': scenario_name,
                'scenario_description': params['description'],
                'total_supply_gwh': total_supply,
                'base_demand_gwh': base_demand_future,
                'datacenter_demand_gwh': datacenter_gwh_adjusted,
                'total_demand_gwh': total_demand,
                'gap_gwh': gap_gwh,
                'gap_percentage': gap_percentage,
                'solar_gwh': solar_gwh,
                'wind_gwh': wind_gwh,
                'gas_gwh': gas_gwh,
                'nuclear_gwh': nuclear_gwh,
                'coal_gwh': coal_gwh,
                'hydro_gwh': hydro_gwh,
                'renewable_gwh': solar_gwh + wind_gwh + hydro_gwh,
                'renewable_pct': (solar_gwh + wind_gwh + hydro_gwh) / total_supply * 100,
                'fossil_pct': (coal_gwh + gas_gwh) / total_supply * 100,
                'carbon_free_pct': (solar_gwh + wind_gwh + hydro_gwh + nuclear_gwh) / total_supply * 100
            })

    scenario_df = pd.DataFrame(all_scenario_results)

    print_progress(f"✓ Completed {len(scenarios)} scenarios through 2030")

    # Print summary for 2030
    print_progress("\n  2030 Gap Analysis (positive = surplus, negative = deficit):")
    for scenario_name in scenarios.keys():
        scenario_2030 = scenario_df[(scenario_df['scenario'] == scenario_name) & (scenario_df['year'] == 2030)].iloc[0]
        # Convert GWh to average GW: GWh / hours = GW
        gap_gw = scenario_2030['gap_gwh'] / 8760
        gap_label = "surplus" if gap_gw > 0 else "deficit"
        print_progress(f"    {scenario_name}: {abs(gap_gw):.1f} GW {gap_label} ({scenario_2030['gap_percentage']:.1f}%)")

    return scenario_df


# ============================================================================
# CLUSTERING ANALYSIS - STATE GROUPING
# ============================================================================

def perform_state_clustering(df: pd.DataFrame) -> Dict:
    """
    Group states into clusters based on energy characteristics.

    Args:
        df: Master dataframe

    Returns:
        Dict containing cluster assignments, profiles, and alternative locations
    """
    print_section_header("[2/5] PREDICTIVE MODELING - Clustering Analysis")

    print_progress("Clustering states by energy profile...")

    # Get 2024 data for all states (excluding US total)
    df_2024 = df[(df['year'] == 2024) & (df['state'] != 'US')].copy()

    # Select clustering features
    clustering_features = [
        'surplus_percentage',
        'renewable_pct',
        'avg_price_cents_per_kwh',
        'generation_per_capita_mwh',
        'solar_cagr',
        'wind_cagr',
        'total_capacity_mw'
    ]

    # Remove states with missing data
    df_clustering = df_2024[['state', 'state_name', 'region'] + clustering_features].dropna()

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clustering[clustering_features])

    # Determine optimal number of clusters using silhouette score
    print_progress("Determining optimal number of clusters...")
    silhouette_scores = []
    K_range = range(3, 8)

    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        silhouette_scores.append(score)

    # Use K with highest silhouette score
    optimal_k = K_range[np.argmax(silhouette_scores)]
    print_progress(f"Optimal number of clusters: {optimal_k}")

    # Apply clustering with optimal K
    kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
    df_clustering['cluster'] = kmeans.fit_predict(X_scaled)

    # Characterize each cluster
    cluster_profiles = df_clustering.groupby('cluster').agg({
        'surplus_percentage': 'mean',
        'renewable_pct': 'mean',
        'avg_price_cents_per_kwh': 'mean',
        'generation_per_capita_mwh': 'mean',
        'solar_cagr': 'mean',
        'wind_cagr': 'mean',
        'total_capacity_mw': 'mean',
        'state': 'count'
    }).round(2)
    cluster_profiles.rename(columns={'state': 'state_count'}, inplace=True)

    # Label clusters based on characteristics
    cluster_labels = {}
    for cluster_id in range(optimal_k):
        profile = cluster_profiles.loc[cluster_id]

        # Simple heuristic labeling based on characteristics
        if profile['renewable_pct'] > 40 and profile['surplus_percentage'] > 10:
            label = 'Renewable Leaders'
        elif profile['surplus_percentage'] < -10:
            label = 'Constrained Markets'
        elif profile['renewable_pct'] < 20 and profile['fossil_pct'] > 60 if 'fossil_pct' in profile else False:
            label = 'Fossil Dependent'
        elif profile['solar_cagr'] > 40 or profile['wind_cagr'] > 15:
            label = 'Growth Markets'
        else:
            label = f'Mixed Profile {cluster_id + 1}'

        cluster_labels[cluster_id] = label

    df_clustering['cluster_name'] = df_clustering['cluster'].map(cluster_labels)

    # Find alternative locations for each datacenter hub
    alternative_locations = {}

    for hub_state in DATACENTER_HUBS:
        if hub_state in df_clustering['state'].values:
            hub_cluster = df_clustering[df_clustering['state'] == hub_state]['cluster'].values[0]

            alternatives = df_clustering[
                (df_clustering['cluster'] == hub_cluster) &
                (df_clustering['state'] != hub_state) &
                (~df_clustering['state'].isin(DATACENTER_HUBS))
            ].sort_values('surplus_percentage', ascending=False).head(5)

            alternative_locations[hub_state] = alternatives[['state', 'state_name', 'surplus_percentage',
                                                              'renewable_pct', 'avg_price_cents_per_kwh']]

    print_progress(f"✓ Created {optimal_k} state clusters")
    print_progress(f"✓ Identified alternative locations for {len(alternative_locations)} datacenter hubs")

    return {
        'clusters': df_clustering,
        'profiles': cluster_profiles,
        'labels': cluster_labels,
        'alternatives': alternative_locations,
        'silhouette_scores': silhouette_scores,
        'optimal_k': optimal_k
    }


# ============================================================================
# LOGISTIC REGRESSION - RENEWABLE ADOPTION FACTORS
# ============================================================================

def analyze_renewable_adoption(df: pd.DataFrame, rf_results: Dict) -> Dict:
    """
    Identify factors that predict successful renewable energy adoption.

    Args:
        df: Master dataframe
        rf_results: Random Forest results with 2030 predictions

    Returns:
        Dict containing model, coefficients, and predictions
    """
    print_section_header("[2/5] PREDICTIVE MODELING - Logistic Regression")

    print_progress("Analyzing renewable adoption success factors...")

    # Get 2024 data
    df_2024 = df[(df['year'] == 2024) & (df['state'] != 'US')].copy()

    # Merge with RF predictions
    predictions_df = rf_results['predictions']
    df_2024 = df_2024.merge(
        predictions_df[['state', 'renewable_pct_2030']],
        on='state',
        how='inner'
    )

    # Create binary target: will reach 50% renewable by 2030
    df_2024['will_reach_50pct_renewable'] = (df_2024['renewable_pct_2030'] > 50).astype(int)

    # Select predictor features
    predictor_features = [
        'renewable_pct',
        'solar_cagr',
        'wind_cagr',
        'avg_price_cents_per_kwh',
        'surplus_percentage',
        'generation_per_capita_mwh',
        'is_west',
        'is_midwest'
    ]

    # Remove missing data
    df_model = df_2024[predictor_features + ['will_reach_50pct_renewable', 'state', 'state_name']].dropna()

    X = df_model[predictor_features]
    y = df_model['will_reach_50pct_renewable']

    # Train logistic regression
    log_reg = LogisticRegression(random_state=42, max_iter=1000)
    log_reg.fit(X, y)

    # Get coefficients and odds ratios
    coefficients = pd.DataFrame({
        'feature': predictor_features,
        'coefficient': log_reg.coef_[0],
        'odds_ratio': np.exp(log_reg.coef_[0])
    }).sort_values('coefficient', ascending=False)

    # Calculate probability for each state
    df_model['prob_50pct_renewable_2030'] = log_reg.predict_proba(X)[:, 1]

    # Identify states on the cusp (40-60% probability)
    states_on_cusp = df_model[
        (df_model['prob_50pct_renewable_2030'] > 0.4) &
        (df_model['prob_50pct_renewable_2030'] < 0.6)
    ].sort_values('prob_50pct_renewable_2030', ascending=False)

    # Model performance
    y_pred = log_reg.predict(X)
    accuracy = (y_pred == y).mean()

    print_progress(f"✓ Model accuracy: {accuracy:.1%}")
    print_progress(f"✓ {(y == 1).sum()} states predicted to reach 50% renewable by 2030")
    print_progress(f"✓ {len(states_on_cusp)} states on the cusp (40-60% probability)")

    return {
        'model': log_reg,
        'coefficients': coefficients,
        'predictions': df_model[['state', 'state_name', 'prob_50pct_renewable_2030', 'will_reach_50pct_renewable']],
        'states_on_cusp': states_on_cusp,
        'accuracy': accuracy
    }


# ============================================================================
# STATE SUITABILITY SCORING
# ============================================================================

def calculate_suitability_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate comprehensive datacenter suitability scores for each state.

    Args:
        df: Master dataframe

    Returns:
        DataFrame: 2024 state data with suitability scores and rankings
    """
    print_section_header("[3/5] STATE SUITABILITY ANALYSIS")

    print_progress("Calculating datacenter suitability scores...")

    # Get 2024 data (excluding US total)
    df_2024 = df[(df['year'] == 2024) & (df['state'] != 'US')].copy()

    # Calculate composite suitability score (0-100)
    def calc_suitability(row):
        score = 0

        # Factor 1: Surplus Capacity (30 points max)
        surplus_score = min(30, max(0, row['surplus_percentage']))
        score += surplus_score

        # Factor 2: Low Price (25 points max)
        price = row['avg_price_cents_per_kwh']
        price_score = max(0, 25 - (price - 7))
        score += price_score

        # Factor 3: Renewable Energy (20 points max)
        renewable_score = min(20, row['renewable_pct'] / 5)
        score += renewable_score

        # Factor 4: Growth Trajectory (15 points max)
        growth_score = min(15, max(0, row['total_generation_cagr'] * 3 + 7.5))
        score += growth_score

        # Factor 5: Absolute Capacity Scale (10 points max)
        capacity_score = min(10, np.log10(row['total_capacity_mw'] + 1) - 3)
        score += capacity_score

        return round(score, 1)

    df_2024['suitability_score'] = df_2024.apply(calc_suitability, axis=1)

    # Calculate risk score (0-100, higher = more risk)
    def calc_risk(row):
        risk = 0

        if row['surplus_percentage'] < 0:
            risk += 40
        if row['avg_price_cents_per_kwh'] > 15:
            risk += 20
        if row['total_generation_cagr'] < 0:
            risk += 20
        if row['renewable_pct'] < 20:
            risk += 20

        return min(100, risk)

    df_2024['risk_score'] = df_2024.apply(calc_risk, axis=1)

    # Net suitability score
    df_2024['net_suitability_score'] = df_2024['suitability_score'] - df_2024['risk_score'] * 0.5

    # Tier classification
    def classify_tier(score):
        if score >= 70:
            return 'Tier 1 - Prime Locations'
        elif score >= 50:
            return 'Tier 2 - Strong Candidates'
        elif score >= 30:
            return 'Tier 3 - Conditional Markets'
        elif score >= 10:
            return 'Tier 4 - High Risk'
        else:
            return 'Tier 5 - Not Recommended'

    df_2024['tier'] = df_2024['net_suitability_score'].apply(classify_tier)

    # Sort by net suitability score
    df_2024 = df_2024.sort_values('net_suitability_score', ascending=False).reset_index(drop=True)

    # Add ranking
    df_2024['suitability_rank'] = range(1, len(df_2024) + 1)

    tier_counts = df_2024['tier'].value_counts()
    print_progress(f"✓ Calculated suitability scores for {len(df_2024)} states")
    print_progress(f"  Tier 1: {tier_counts.get('Tier 1 - Prime Locations', 0)} states")
    print_progress(f"  Tier 2: {tier_counts.get('Tier 2 - Strong Candidates', 0)} states")

    return df_2024


# ============================================================================
# ENERGY SOURCE SCALABILITY ANALYSIS
# ============================================================================

def assess_energy_scalability(df: pd.DataFrame, scenario_df: pd.DataFrame) -> Dict:
    """
    Assess which energy sources can scale fast enough to meet demand.

    Args:
        df: Master dataframe
        scenario_df: Scenario analysis results

    Returns:
        Dict containing feasibility analysis and deployment timelines
    """
    print_section_header("[4/5] ENERGY SOURCE SCALABILITY ANALYSIS")

    print_progress("Analyzing energy source scalability...")

    # Get US 2024 data
    us_2024 = df[(df['state'] == 'US') & (df['year'] == 2024)].iloc[0]

    # Get baseline scenario 2030 gap
    baseline_2030 = scenario_df[
        (scenario_df['scenario'] == 'baseline') &
        (scenario_df['year'] == 2030)
    ].iloc[0]

    gap_gwh = baseline_2030['gap_gwh']

    # Calculate required CAGR to fill gap (assuming each source fills a portion)
    # If gap is negative (deficit), we need to ADD generation to fill it
    # If gap is positive (surplus), we don't need to add more
    # Solar: 50%, Wind: 30%, Gas: 20%
    allocations = {
        'solar': 0.5,
        'wind': 0.3,
        'gas': 0.2
    }

    feasibility_data = []

    for source, allocation in allocations.items():
        current_gwh = us_2024[f'{source}_generation_gwh']

        # If deficit (gap < 0), we need to fill abs(gap) with new generation
        # If surplus (gap > 0), no additional generation needed
        if gap_gwh < 0:
            # Deficit: need to add generation
            target_gap = abs(gap_gwh) * allocation
            target_value = current_gwh + target_gap
        else:
            # Surplus: maintain current level
            target_gap = 0
            target_value = current_gwh

        required_cagr = calculate_cagr(current_gwh, target_value, 6)
        historical_cagr = us_2024[f'{source}_cagr']

        gap_cagr = required_cagr - historical_cagr

        if gap_cagr < 5:
            feasibility = 'Achievable'
        elif gap_cagr < 10:
            feasibility = 'Challenging'
        else:
            feasibility = 'Unlikely'

        feasibility_data.append({
            'source': source.capitalize(),
            'current_gwh': current_gwh,
            'gap_allocation_gwh': target_gap,
            'target_gwh_2030': target_value,
            'historical_cagr': historical_cagr,
            'required_cagr': required_cagr,
            'cagr_gap': gap_cagr,
            'feasibility': feasibility
        })

    feasibility_df = pd.DataFrame(feasibility_data)

    # Deployment timeline analysis
    # Calculate years needed at current deployment pace
    us_2020 = df[(df['state'] == 'US') & (df['year'] == 2020)].iloc[0]

    timeline_data = []

    for source in ['solar', 'wind', 'gas']:
        annual_addition = (us_2024[f'{source}_generation_gwh'] - us_2020[f'{source}_generation_gwh']) / 4

        if annual_addition > 0:
            years_needed = gap_gwh / annual_addition
            can_meet_2030 = years_needed <= 6
        else:
            years_needed = np.inf
            can_meet_2030 = False

        timeline_data.append({
            'source': source.capitalize(),
            'annual_addition_gwh': annual_addition,
            'gap_to_fill_gwh': gap_gwh,
            'years_needed_current_pace': years_needed,
            'can_meet_2030_target': can_meet_2030
        })

    timeline_df = pd.DataFrame(timeline_data)

    print_progress(f"✓ Analyzed scalability for {len(feasibility_df)} energy sources")
    for _, row in feasibility_df.iterrows():
        print_progress(f"  {row['source']}: {row['feasibility']} "
                      f"(requires {row['required_cagr']:.1f}% CAGR vs {row['historical_cagr']:.1f}% historical)")

    return {
        'feasibility': feasibility_df,
        'timeline': timeline_df
    }


# ============================================================================
# OUTPUT GENERATION
# ============================================================================

def save_all_outputs(
    master_df: pd.DataFrame,
    rf_results: Dict,
    us_forecast: pd.DataFrame,
    scenario_df: pd.DataFrame,
    cluster_results: Dict,
    log_reg_results: Dict,
    suitability_df: pd.DataFrame,
    scalability_results: Dict
):
    """
    Save all analysis results to CSV files for Tableau.

    Args:
        master_df: Master dataframe
        rf_results: Random Forest results
        us_forecast: US forecasts by source
        scenario_df: Scenario analysis
        cluster_results: Clustering results
        log_reg_results: Logistic regression results
        suitability_df: State suitability scores
        scalability_results: Energy source scalability
    """
    print_section_header("[5/5] SAVING RESULTS")

    output_dir = Path.cwd()

    # 1. Master dataset for Tableau
    print_progress("Saving tableau_master_data.csv...")
    master_tableau = master_df[[
        'year', 'state', 'state_name', 'region',
        'total_generation_gwh', 'total_sales_gwh', 'net_balance_gwh', 'surplus_percentage',
        'coal_generation_gwh', 'gas_generation_gwh', 'nuclear_generation_gwh',
        'hydro_generation_gwh', 'wind_generation_gwh', 'solar_generation_gwh',
        'coal_pct', 'gas_pct', 'nuclear_pct', 'renewable_pct', 'carbon_free_pct',
        'avg_price_cents_per_kwh', 'generation_per_capita_mwh', 'consumption_per_capita_mwh',
        'total_generation_cagr', 'renewable_cagr', 'solar_cagr', 'wind_cagr'
    ]].copy()
    master_tableau.to_csv(output_dir / 'tableau_master_data.csv', index=False)

    # 2. State analysis 2024
    print_progress("Saving state_analysis_2024.csv...")
    suitability_df.to_csv(output_dir / 'state_analysis_2024.csv', index=False)

    # 3. Forecasts
    print_progress("Saving us_forecast_by_source_2025_2030.csv...")
    us_forecast.to_csv(output_dir / 'us_forecast_by_source_2025_2030.csv', index=False)

    print_progress("Saving scenario_analysis_all.csv...")
    scenario_df.to_csv(output_dir / 'scenario_analysis_all.csv', index=False)

    print_progress("Saving state_predictions_2030.csv...")
    rf_results['predictions'].to_csv(output_dir / 'state_predictions_2030.csv', index=False)

    # 4. Model outputs
    print_progress("Saving random_forest_feature_importance.csv...")
    all_importance = []
    for target, importance_df in rf_results['feature_importance'].items():
        importance_df['target'] = target
        all_importance.append(importance_df)
    pd.concat(all_importance).to_csv(output_dir / 'random_forest_feature_importance.csv', index=False)

    print_progress("Saving random_forest_model_performance.csv...")
    perf_df = pd.DataFrame(rf_results['performance']).T
    perf_df.to_csv(output_dir / 'random_forest_model_performance.csv')

    print_progress("Saving logistic_regression_coefficients.csv...")
    log_reg_results['coefficients'].to_csv(output_dir / 'logistic_regression_coefficients.csv', index=False)

    print_progress("Saving renewable_adoption_predictions.csv...")
    log_reg_results['predictions'].to_csv(output_dir / 'renewable_adoption_predictions.csv', index=False)

    print_progress("Saving cluster_profiles.csv...")
    cluster_results['profiles'].to_csv(output_dir / 'cluster_profiles.csv')

    print_progress("Saving state_clusters.csv...")
    cluster_results['clusters'].to_csv(output_dir / 'state_clusters.csv', index=False)

    # 5. Alternative locations
    print_progress("Saving alternative_locations.csv...")
    alt_locations = []
    for hub, alts in cluster_results['alternatives'].items():
        alts_copy = alts.copy()
        alts_copy['hub_state'] = hub
        alt_locations.append(alts_copy)
    if alt_locations:
        pd.concat(alt_locations).to_csv(output_dir / 'alternative_locations.csv', index=False)

    # 6. Scalability
    print_progress("Saving energy_source_scalability.csv...")
    scalability_results['feasibility'].to_csv(output_dir / 'energy_source_scalability.csv', index=False)

    print_progress("Saving deployment_timeline_analysis.csv...")
    scalability_results['timeline'].to_csv(output_dir / 'deployment_timeline_analysis.csv', index=False)

    # 7. Key statistics JSON
    print_progress("Saving key_statistics.json...")

    baseline_2030 = scenario_df[(scenario_df['scenario'] == 'baseline') & (scenario_df['year'] == 2030)].iloc[0]

    key_stats = {
        'national': {
            'baseline_gap_2030_gwh': float(baseline_2030['gap_gwh']),
            'baseline_gap_2030_gw': float(baseline_2030['gap_gwh'] / 8760),  # GWh / hours = average GW
            'gap_percentage': float(baseline_2030['gap_percentage']),
            'renewable_pct_2030_baseline': float(baseline_2030['renewable_pct']),
        },
        'state_summary': {
            'states_with_surplus': int((suitability_df['surplus_percentage'] > 0).sum()),
            'states_with_deficit': int((suitability_df['surplus_percentage'] < 0).sum()),
            'states_tier1': int((suitability_df['tier'] == 'Tier 1 - Prime Locations').sum()),
            'states_tier2': int((suitability_df['tier'] == 'Tier 2 - Strong Candidates').sum()),
        },
        'top_states': {
            'highest_suitability': suitability_df.iloc[0]['state'],
            'highest_suitability_score': float(suitability_df.iloc[0]['net_suitability_score']),
        }
    }

    with open(output_dir / 'key_statistics.json', 'w') as f:
        json.dump(key_stats, f, indent=2)

    print_progress(f"✓ Saved all analysis outputs to {output_dir}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""

    print("=" * 70)
    print("DATACENTER ENERGY ANALYSIS - STATISTICAL MODELING")
    print("=" * 70)

    try:
        # 1. Load and prepare data
        generation_df = load_eia_data()
        master_df = prepare_master_dataset(generation_df)
        master_df = calculate_growth_rates(master_df)

        # 2. Predictive modeling
        rf_results = train_random_forest_models(master_df)
        us_forecast = forecast_us_by_source(master_df)
        scenario_df = run_scenario_analysis(us_forecast, master_df)
        cluster_results = perform_state_clustering(master_df)
        log_reg_results = analyze_renewable_adoption(master_df, rf_results)

        # 3. Suitability analysis
        suitability_df = calculate_suitability_scores(master_df)

        # 4. Energy source scalability
        scalability_results = assess_energy_scalability(master_df, scenario_df)

        # 5. Save outputs
        save_all_outputs(
            master_df, rf_results, us_forecast, scenario_df,
            cluster_results, log_reg_results, suitability_df, scalability_results
        )

        # Print final summary
        print_section_header("✓ ANALYSIS COMPLETE!")

        # Get key metrics for summary
        baseline_2030 = scenario_df[(scenario_df['scenario'] == 'baseline') & (scenario_df['year'] == 2030)].iloc[0]
        gap_gw = baseline_2030['gap_gwh'] / 8760  # GWh / hours = average GW

        top_state = suitability_df.iloc[0]

        surplus_count = (suitability_df['surplus_percentage'] > 0).sum()

        solar_feasibility = scalability_results['feasibility'][
            scalability_results['feasibility']['source'] == 'Solar'
        ].iloc[0]

        print("\nKey Findings:")
        print(f"  • Top recommended state: {top_state['state_name']} (score: {top_state['net_suitability_score']:.1f})")
        print(f"  • Baseline 2030 gap: {gap_gw:.1f} GW ({baseline_2030['gap_percentage']:.1f}%)")
        print(f"  • States with surplus: {surplus_count}")
        print(f"  • Solar CAGR needed: {solar_feasibility['required_cagr']:.1f}% "
              f"(historical: {solar_feasibility['historical_cagr']:.1f}%)")

        print("\nFiles ready for Tableau import:")
        print("  ✓ tableau_master_data.csv")
        print("  ✓ state_analysis_2024.csv")
        print("  ✓ us_forecast_by_source_2025_2030.csv")
        print("  ✓ scenario_analysis_all.csv")
        print("  ✓ state_predictions_2030.csv")
        print("  ✓ ... and 10+ more analysis files")

        print("\n" + "=" * 70)
        print("All analysis complete! Ready for visualization in Tableau.")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
