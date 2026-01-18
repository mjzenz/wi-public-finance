# UW-Madison Public Finance Data Pipeline

A Python-based data pipeline for processing, analyzing, and visualizing employee salary data from the University of Wisconsin-Madison. The pipeline handles data from two different HR systems (UFAS and Workday) and provides tools for consistent analysis across the system transition.

## Overview

This project provides:

1. **Data Loading & Cleaning** (`import_data.py`): Load salary data from Excel files, normalize column names across formats, generate stable employee IDs, and enrich with CPI data for inflation adjustment.

2. **Analysis Functions** (`dataprocess.py`): Higher-level analysis including FTE calculations, transfer tracking, and reorganization detection.

3. **Interactive Web App** (`salary_app.py`): A Streamlit application for exploring employee salaries, viewing individual profiles, and comparing across departments.

4. **Configuration** (`config.py`): Centralized settings, mappings, and constants for the entire pipeline.

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Salary data files in Excel format (`.xlsx`) in the `data/` directory
- (Optional) FRED API key for updating CPI data

### Installation

1. Clone or download this repository:
   ```bash
   cd wi-public-finance
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. If you need to update CPI data, set up your FRED API key:
   ```bash
   python fetch_cpi.py
   ```
   (Follow the prompts to enter your API key)

### Running the Streamlit App

```bash
streamlit run salary_app.py
```

The app will open in your default web browser.

### Running Analysis Scripts

```bash
# Basic data exploration
python examples/basic_analysis.py

# Salary trends over time
python examples/salary_trends.py

# Full analysis pipeline
python dataprocess.py
```

## Project Structure

```
wi-public-finance/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── config.py                 # Configuration and mappings
├── import_data.py           # Data loading and cleaning
├── dataprocess.py           # Analysis functions
├── fetch_cpi.py             # CPI data fetching
├── salary_app.py            # Streamlit web application
├── data/                    # Data directory
│   ├── cpi_data.csv         # Cached CPI data
│   └── salaries-YYYY-MM.xlsx # Salary data files
├── examples/                # Example scripts
│   ├── basic_analysis.py
│   └── salary_trends.py
└── uw_madison_job_descriptions.csv  # Job metadata (optional)
```

## Data Format

### Input Data

The pipeline expects Excel files in the `data/` directory with a date pattern in the filename (e.g., `salaries-2024-03.xlsx`). The pipeline automatically detects whether each file is in UFAS or Workday format based on column names.

### Key Fields (After Processing)

| Field | Description |
|-------|-------------|
| `id` | Unique employee identifier (12-char hex) |
| `Date` | Data snapshot date |
| `first_name`, `last_name` | Employee name |
| `division`, `department` | Organizational unit |
| `title`, `jobcode` | Job classification |
| `current_annual_contracted_salary` | Base annual salary |
| `full_time_equivalent` | FTE (0.0 to 1.0) |
| `fte_adjusted_salary` | Salary × FTE |
| `FTE_Adjusted_Salary_2021_Dollars` | Inflation-adjusted salary |
| `employee_category` | Faculty, Academic Staff, etc. |
| `job_group`, `job_subgroup` | Job classification from metadata |

## Module Documentation

### config.py

Contains all configuration settings:

- **File Paths**: Locations of data files and output
- **CPI Settings**: FRED series ID and base date for inflation adjustment
- **Employee Categories**: Mapping of codes to category names
- **Division Mappings**: Normalization of division names across systems
- **Column Mappings**: Mapping of column names between formats

### import_data.py

Main data loading module with functions:

- `read_salary_file_names(folder)`: Find salary data files by date pattern
- `detect_file_format(df)`: Identify UFAS vs Workday format
- `generate_employee_id(row)`: Create stable employee IDs
- `normalize_columns(df, format)`: Standardize column names
- `clean_salary_data(filenames)`: Main entry point for loading data

### dataprocess.py

Analysis functions:

- `load_salary_data()`: Load and filter salary data
- `add_analysis_flags(df)`: Add faculty/research classification flags
- `calculate_fte_changes(df)`: Track FTE changes over time
- `track_employee_transfers(df)`: Detect transfers vs reorganizations
- `run_full_analysis()`: Execute complete analysis pipeline

### salary_app.py

Streamlit web application with three pages:

1. **Search**: Find employees by name, division, or department
2. **Individual Profile**: View salary history and peer comparisons
3. **Department View**: See aggregate statistics for a department

## Common Use Cases

### Load Data and Get Basic Statistics

```python
from import_data import read_salary_file_names, clean_salary_data

# Load all data
files = read_salary_file_names()
df = clean_salary_data(files)

# Get latest snapshot
latest = df[df['Date'] == df['Date'].max()]
print(f"Total employees: {len(latest):,}")
print(f"Median salary: ${latest['current_annual_contracted_salary'].median():,.0f}")
```

### Track an Employee Over Time

```python
# Find employee by name
emp_records = df[
    (df['last_name'].str.upper() == 'SMITH') &
    (df['first_name'].str.upper() == 'JOHN')
]

# Get their salary history
history = emp_records[['Date', 'title', 'current_annual_contracted_salary']].sort_values('Date')
print(history)
```

### Compare Salaries by Division

```python
# Get median salary by division (latest data only)
latest = df[df['Date'] == df['Date'].max()]
by_division = latest.groupby('division')['current_annual_contracted_salary'].median()
print(by_division.sort_values(ascending=False).head(10))
```

### Run Full Analysis Pipeline

```python
import dataprocess

results = dataprocess.run_full_analysis()

# Access various outputs
salary_data = results['salary_data']
transfer_pairs = results['transfer_pairs']
reorg_summary = results['reorg_summary']

# Filter to real transfers (excluding reorganizations)
real_transfers = transfer_pairs[~transfer_pairs['is_reorg']]
```

## Data Source Background

The salary data comes from two different HR systems used by UW-Madison:

- **UFAS** (University Financial Administration System): Used until approximately 2025. Data uses UPPERCASE names and short category codes (e.g., "FA" for Faculty).

- **Workday**: New system starting 2025. Uses Title Case names and full text for categories.

The pipeline normalizes these differences so data can be analyzed consistently across the transition period.

## Key Considerations

### Employee Identification

Since the raw data doesn't include persistent employee IDs, the pipeline generates IDs from a combination of name and hire date. This works well in most cases but may occasionally:
- Treat the same person as two different people if their hire date differs between systems
- Treat two different people as the same if they have identical names and hire dates

### Division Name Changes

Many divisions were renamed during the Workday transition. The `config.DIVISION_NAME_MAPPING` maps Workday names back to UFAS names for consistent tracking.

### Jobcode Normalization

Jobcodes should be 5 characters. Some records have 6-character codes with suffixes (U, A, X, N) that indicate variants. These suffixes are stripped during processing.

## Troubleshooting

### "CPI data file not found"

Run `python fetch_cpi.py` to download CPI data. You'll need a FRED API key (free from https://fred.stlouisfed.org/).

### "Job descriptions file not found"

This is a warning, not an error. Job metadata (job_group, supervisory_required, etc.) will not be available, but basic salary analysis will still work.

### Data loading is slow

The first load processes all Excel files, which can take time. The Streamlit app caches this data after the first load.

## License

This project is for educational and research purposes related to public finance analysis.

## Contributing

Contributions are welcome. Please ensure any changes maintain compatibility with both UFAS and Workday data formats.
