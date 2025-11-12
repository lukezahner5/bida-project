# EIA Data Collector for Data Center Energy Analysis

A comprehensive Python tool to collect US electricity data from the EIA (Energy Information Administration) API v2 for analyzing energy capacity vs. data center demand growth.

## Overview

This script collects 5 key datasets spanning 2010-2024:
1. **Annual Electricity Generation by Source** - Power generation broken down by fuel type
2. **Retail Sales by Sector** - Electricity consumption across different sectors
3. **Generation Capacity by Source** - Installed power generation capacity
4. **State Energy Data (SEDS)** - Comprehensive state-level energy statistics for all 50 states
5. **Electricity Prices** - Average retail electricity prices by state

## Quick Start

### Prerequisites

- Python 3.8 or higher
- EIA API Key (free at https://www.eia.gov/opendata/register.php)

### Installation

1. Install required packages:
```bash
pip install -r requirements.txt
```

2. Run the script:
```bash
python eia_data_collector.py
```

3. Enter your EIA API key when prompted

4. Wait for data collection (typically 2-5 minutes)

## Output Files

The script creates the following files:

### CSV Files (one per dataset):
- `eia_generation_by_source.csv` - Annual generation by fuel type
- `eia_retail_sales_by_sector.csv` - Sales by customer sector
- `eia_capacity_by_source.csv` - Installed capacity by fuel type
- `eia_state_energy_seds.csv` - State energy consumption and production
- `eia_electricity_prices.csv` - Average retail prices by state

### Excel File:
- `eia_master_data.xlsx` - All datasets in separate sheets with metadata

### Reports:
- `data_quality_report.txt` - Validation results and data quality metrics

## Data Dictionary

### 1. eia_generation_by_source.csv

Annual electricity generation by fuel type (2010-2024)

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `year` | int | Calendar year | - |
| `state` | str | State code (US, TX, CA, etc.) | - |
| `coal_generation_gwh` | float | Coal generation | Gigawatt-hours (GWh) |
| `gas_generation_gwh` | float | Natural gas generation | GWh |
| `nuclear_generation_gwh` | float | Nuclear generation | GWh |
| `hydro_generation_gwh` | float | Hydroelectric generation | GWh |
| `wind_generation_gwh` | float | Wind generation | GWh |
| `solar_generation_gwh` | float | Solar generation | GWh |
| `other_generation_gwh` | float | Other sources | GWh |
| `total_generation_gwh` | float | Total generation | GWh |

**Coverage:** US total + 10 priority states (TX, CA, FL, NY, PA, IL, OH, NC, GA, VA)

**Note:** 1 GWh = 1,000 MWh = 1,000,000 kWh

### 2. eia_retail_sales_by_sector.csv

Total electricity retail sales by customer sector (2010-2024)

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `year` | int | Calendar year | - |
| `state` | str | State code | - |
| `residential_sales_gwh` | float | Residential sector sales | GWh |
| `commercial_sales_gwh` | float | Commercial sector sales | GWh |
| `industrial_sales_gwh` | float | Industrial sector sales | GWh |
| `transportation_sales_gwh` | float | Transportation sector sales | GWh |
| `total_sales_gwh` | float | All sectors total | GWh |

**Coverage:** US total + 10 priority states

**Key Insight:** Commercial sector includes data centers

### 3. eia_capacity_by_source.csv

Installed electricity generation capacity by fuel type (2015-2024)

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `year` | int | Calendar year | - |
| `state` | str | State code | - |
| `coal_capacity_mw` | float | Coal capacity | Megawatts (MW) |
| `gas_capacity_mw` | float | Natural gas capacity | MW |
| `nuclear_capacity_mw` | float | Nuclear capacity | MW |
| `hydro_capacity_mw` | float | Hydroelectric capacity | MW |
| `wind_capacity_mw` | float | Wind capacity | MW |
| `solar_capacity_mw` | float | Solar capacity | MW |
| `other_capacity_mw` | float | Other sources | MW |
| `total_capacity_mw` | float | Total capacity | MW |

**Coverage:** US total + 10 priority states

**Note:** 1,000 MW = 1 GW (gigawatt)

### 4. eia_state_energy_seds.csv

State Energy Data System - comprehensive state energy statistics (2010-2023)

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `year` | int | Calendar year | - |
| `state` | str | State code | - |
| `state_name` | str | Full state name | - |
| `total_energy_consumption_btu` | float | Total energy consumed | Billion BTU |
| `total_energy_production_btu` | float | Total energy produced | Billion BTU |
| `total_electricity_consumption_btu` | float | Electricity consumed | Billion BTU |

**Coverage:** All 50 US states

**Note:** BTU = British Thermal Unit (energy measurement)

### 5. eia_electricity_prices.csv

Average retail electricity prices by state (2010-2024)

| Column | Type | Description | Units |
|--------|------|-------------|-------|
| `year` | int | Calendar year | - |
| `state` | str | State code | - |
| `avg_price_cents_per_kwh` | float | Average retail price | Cents per kWh |

**Coverage:** All 50 US states

**Note:** Prices are sector-averaged across all customer types

## Features

### Robust API Handling
- ✓ Automatic pagination for large datasets (>5,000 records)
- ✓ Rate limit detection and retry logic
- ✓ Exponential backoff for failed requests
- ✓ Comprehensive error messages

### Data Quality
- ✓ Automatic data validation
- ✓ Missing value detection
- ✓ Year range verification
- ✓ State coverage checks
- ✓ Detailed quality reports

### User Experience
- ✓ Real-time progress indicators
- ✓ Execution timing for each step
- ✓ Clear success/error messages
- ✓ Summary statistics

## Data Quality Notes

### Known Limitations

1. **Capacity Data:** Only available from 2015 onwards (not 2010)
2. **SEDS Data:** Typically lags by 1-2 years (latest is usually 2023)
3. **Missing Values:** Some states may have incomplete data for certain years
4. **State Coverage:** Not all datasets cover all 50 states (see individual dataset descriptions)

### Data Update Frequency

- **Annual Data:** Updated annually, typically 4-6 months after year end
- **Monthly Data:** Available but not collected by this script
- Check EIA website for latest update schedules

## Use Cases for Data Center Analysis

### 1. Baseline Energy Demand
- Compare commercial sector growth rates
- Identify high-growth states (TX, VA, GA)
- Analyze historical consumption trends

### 2. Capacity Planning
- Calculate reserve margins (capacity vs. demand)
- Identify capacity-constrained regions
- Project future capacity needs

### 3. Cost Analysis
- Compare electricity prices across states
- Identify cost-effective locations for data centers
- Factor in renewable energy availability

### 4. Goldman Sachs 50 GW Projection
- Use 2010-2024 data to validate growth rates
- Compare projected data center demand vs. total capacity
- Analyze if 50 GW by 2030 is feasible

### Example Analysis Questions:

**Q: What % of total US electricity would 50 GW represent?**
- Check `total_capacity_mw` for US in latest year
- Convert 50 GW = 50,000 MW
- Calculate percentage

**Q: Which states have fastest growing commercial demand?**
- Use `commercial_sales_gwh` column
- Calculate CAGR (Compound Annual Growth Rate) 2010-2024
- Rank states

**Q: Is renewable capacity growing fast enough?**
- Sum `wind_capacity_mw` + `solar_capacity_mw` over time
- Compare growth rate to projected data center demand

## Technical Details

### API Endpoints Used

1. `/electricity/electric-power-operational-data/data/` - Generation data
2. `/electricity/retail-sales/data/` - Sales and price data
3. `/electricity/operating-generator-capacity/data/` - Capacity data
4. `/seds/data/` - State Energy Data System

### Dependencies

- `requests` - API calls
- `pandas` - Data processing
- `numpy` - Numerical operations
- `openpyxl` - Excel file creation

### Error Handling

The script handles:
- Network timeouts (60 second timeout per request)
- HTTP errors (403 auth, 429 rate limit, etc.)
- Invalid API responses
- Missing data fields
- Pagination edge cases

### Performance

- **Typical Runtime:** 2-5 minutes
- **API Calls:** ~20-30 requests
- **Data Volume:** ~5,000-10,000 records total
- **Output Size:** ~2-5 MB total

## Troubleshooting

### Common Issues

**"Authentication failed" error:**
- Check your API key is correct
- Verify key is active at https://www.eia.gov/opendata/commands.php

**"No data retrieved" for a dataset:**
- EIA may have changed endpoint structure
- Check API documentation: https://www.eia.gov/opendata/documentation.php
- Some data may not be available for requested years

**"Rate limit" warnings:**
- Script will automatically retry
- If persistent, increase `time.sleep()` delays in code

**Missing recent years:**
- EIA data typically lags 4-6 months
- 2024 data may not be available until mid-2025

### Debug Mode

To see detailed API responses, modify the script:
```python
# Add after line with response.json()
print(json.dumps(response.json(), indent=2))
```

## Data Updates

To refresh data with latest EIA releases:

1. Simply re-run the script:
```bash
python eia_data_collector.py
```

2. Files will be overwritten with latest data

3. Compare `data_quality_report.txt` to check for new records

## Project Context

This tool was created to support analysis of US energy capacity vs. data center demand growth, specifically to evaluate Goldman Sachs' projection that data centers will require 50 GW by 2030.

**Key Research Questions:**
- Can the US grid support 50 GW of new data center demand?
- Which states are best positioned for data center growth?
- How fast is renewable capacity growing vs. demand?
- What are the cost implications across different states?

## Credits

- **Data Source:** U.S. Energy Information Administration (EIA)
- **API:** EIA Open Data API v2
- **Documentation:** https://www.eia.gov/opendata/

## License

This script is provided as-is for educational and research purposes. EIA data is public domain.

## Support

For EIA API issues:
- API Documentation: https://www.eia.gov/opendata/documentation.php
- Contact: https://www.eia.gov/about/contact.php

For script issues:
- Check the `data_quality_report.txt` for validation warnings
- Review console output for specific error messages
- Ensure all dependencies are installed

## Version History

**v1.0 (2025-11-12)**
- Initial release
- 5 core datasets
- Data validation and quality reporting
- Excel export with metadata
- Comprehensive documentation

---

**Ready to analyze US energy data? Run the script and start your analysis!**
