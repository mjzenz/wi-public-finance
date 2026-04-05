# UW-Madison Salary Data Explorer

A Python-based pipeline and web application for processing, analyzing, and
visualizing employee salary data from the University of Wisconsin-Madison.

**Live app:** [wiscdata.com](https://wiscdata.com)

## Data Source

All salary data is obtained and published by
**[United Faculty & Academic Staff (UFAS)](https://ufas223.org/)**, the union
representing UW-Madison faculty and academic staff. UFAS makes this data
available to promote pay transparency across the university. Their existing
salary tool is at [ufas223.github.io/salaries](https://ufas223.github.io/salaries/).

**If you are UW-Madison faculty or academic staff,
[consider joining UFAS](https://ufas223.org/).**

The data spans 9 snapshots from November 2021 through March 2026 and covers
the transition from the legacy HRS system to Workday in 2025.

## What This Project Does

### Interactive Web App (`salary_app.py`)

A Streamlit application deployed at wiscdata.com for exploring salary data:

- **Employee Search**: Find current and former employees by name, division,
  or department
- **Individual Profiles**: Salary history charts (nominal and
  inflation-adjusted), title change visualization, peer salary comparisons
- **Department View**: Employee rosters with salary growth metrics,
  distribution charts, and summary statistics

```bash
streamlit run salary_app.py
```

### Data Pipeline (`import_data.py`)

Loads salary data from Excel files, handles the HRS-to-Workday format
transition, and produces a clean, analysis-ready dataset:

- Detects file format (HRS vs Workday) and normalizes column names
- Generates stable employee IDs from name + hire date (no official ID in
  the raw data)
- Fixes hire date inconsistencies between systems
- Removes duplicate and over-allocated appointments (see below)
- Adjusts salaries for inflation using CPI data from FRED
- Merges job metadata from UW's Standard Job Descriptions

### Analysis Reports (`reports/`)

Quarto reports analyzing salary and FTE expenditure trends:

| Report | Description |
|--------|-------------|
| `uw_salary_expenditure_report.qmd` | University-wide FTE and salary trends, job group analysis, top 15 individual salary increases, administrative overhead ratio |
| `ls_salary_expenditure_report.qmd` | Same analysis scoped to College of Letters & Science, with department-level breakdowns |
| `art_salary_report.qmd` | L&S Administrative Regional Teams consolidation analysis |
| `LS_Blended_Layoff_Plan.md` | Budget cut scenario analysis |
| `LS_Budget_Cut_*.md` | Budget impact comparisons |

Render with: `cd reports && quarto render <file>.qmd`

### Supporting Modules

| Module | Purpose |
|--------|---------|
| `config.py` | All mappings, thresholds, and file paths |
| `dataprocess.py` | Transfer tracking, reorganization detection, FTE analysis |
| `fetch_cpi.py` | Downloads CPI data from FRED API for inflation adjustment |
| `scrape_uw_jobs.py` | Scrapes UW job descriptions for job group metadata |
| `extract_names.py` | Utility for matching positions to employees |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web app
streamlit run salary_app.py

# Or use the pipeline in Python
python -c "
from import_data import read_salary_file_names, clean_salary_data
df = clean_salary_data(read_salary_file_names())
print(f'{df[\"id\"].nunique():,} employees, {len(df):,} records')
"
```

## Project Structure

```
wi-public-finance/
├── salary_app.py                # Streamlit web app
├── import_data.py               # Data loading and cleaning pipeline
├── dataprocess.py               # Analysis functions
├── config.py                    # Configuration and mappings
├── fetch_cpi.py                 # CPI data from FRED API
├── scrape_uw_jobs.py            # UW job description scraper
├── extract_names.py             # Position-name matching utility
├── requirements.txt             # Python dependencies
├── data/                        # Salary Excel files and CPI cache
│   ├── *.xlsx                   # Salary snapshots (2021-11 through 2026-03)
│   └── cpi_data.csv             # Cached CPI data
├── reports/                     # Quarto analysis reports
│   ├── uw_salary_expenditure_report.qmd
│   ├── ls_salary_expenditure_report.qmd
│   ├── art_salary_report.qmd
│   └── LS_*.md
├── deploy/                      # AWS deployment files
│   ├── setup.sh                 # EC2 setup script
│   ├── wiscdata.service         # systemd service
│   ├── nginx-wiscdata.conf      # Nginx reverse proxy config
│   └── update-data.sh           # Data update helper
├── examples/                    # Example analysis scripts
│   ├── basic_analysis.py
│   └── salary_trends.py
└── uw_madison_job_descriptions.csv  # Scraped job metadata
```

## Data Pipeline Details

### HR System Transition

UW-Madison switched from **HRS** (a legacy homebrew system) to **Workday** in
2025. The two systems use different column names, name casing (HRS: UPPERCASE,
Workday: Title Case), and sometimes different hire dates for the same person.
The pipeline normalizes all of this.

### Data Cleaning

The pipeline applies several corrections during `clean_salary_data()`:

1. **Column normalization**: Maps HRS and Workday column names to a common
   schema. Handles format changes across Workday versions (e.g., 2025-09 uses
   `Annual_Full_Salary` while 2026-03 uses `Annualized_Rate_Amount`).

2. **Hire date reconciliation**: HRS hire dates are preferred for employees
   who appear in both systems. Only applied when a name is unambiguous (one
   person with that name) to avoid collapsing distinct employees.

3. **Appointment deduplication**: Removes exact duplicate rows and handles
   over-allocated FTE. When a person's total FTE exceeds 1.4 (e.g., a
   leadership appointment stacked on a permanent position):
   - If the person has a Limited (leadership) appointment, that is kept
   - Otherwise the highest-salary appointment is kept
   - Fractional appointments are preserved as long as total FTE stays under 1.4

4. **CPI forward-fill**: When the latest month's CPI isn't available yet
   from FRED, the most recent available value is used.

5. **Division name mapping**: 40+ Workday division names are mapped back to
   their HRS equivalents for consistent tracking across the transition.

### Key Output Fields

| Field | Description |
|-------|-------------|
| `id` | Stable 12-char hex ID (MD5 of name + hire date) |
| `current_annual_contracted_salary` | Base annual salary rate |
| `full_time_equivalent` | FTE (0.0 to 1.0) |
| `fte_adjusted_salary` | Salary x FTE |
| `Real_Salary_2021_Dollars` | Salary adjusted for inflation (2021 base) |
| `FTE_Adjusted_Salary_2021_Dollars` | FTE x inflation-adjusted salary |
| `employee_category` | Faculty, Academic Staff, University Staff, etc. |
| `job_group` | Functional area from UW job classification system |

### Known Limitations

- **Employee IDs are derived from name + hire date.** Two people with the
  same name and hire date will share an ID. This is rare but does occur
  (e.g., one known case across ~22,000 employees per snapshot).
- **Division mapping may be incomplete.** If Workday introduces new division
  names not yet in `config.DIVISION_NAME_MAPPING`, they will appear as-is
  rather than mapping to the HRS equivalent.

## Deployment

The app runs on a single EC2 instance behind Nginx with Let's Encrypt SSL.
See `deploy/` for all configuration files.

**Updating data (twice a year):**
```bash
scp "Updated YYYY-MM *.xlsx" ec2-user@wiscdata.com:/opt/wiscdata/app/data/
ssh ec2-user@wiscdata.com "sudo systemctl restart wiscdata"
```

## Requirements

- Python 3.9+
- See `requirements.txt` for packages: pandas, openpyxl, numpy, streamlit,
  plotly, itables, fredapi, keyring

## License

This project is for educational and research purposes related to public
finance analysis at UW-Madison.
