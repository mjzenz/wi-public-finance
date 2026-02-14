"""
Data Import and Cleaning Module for UW-Madison Salary Data
==========================================================

This module provides functions to load, clean, and normalize salary data from
UW-Madison's HR systems. It handles the complexity of working with data from
two different systems (UFAS and Workday) that use different formats and naming
conventions.

Key Capabilities:
-----------------
1. **File Discovery**: Automatically find salary data files by date pattern
2. **Format Detection**: Identify whether a file is UFAS or Workday format
3. **Column Normalization**: Standardize column names across formats
4. **Employee ID Generation**: Create stable IDs to track employees over time
5. **Data Enrichment**: Add job metadata, CPI adjustment, derived fields

Data Flow:
----------
1. Find Excel files with date patterns (e.g., "salaries-2024-03.xlsx")
2. Load each file and detect its format (UFAS or Workday)
3. Normalize column names to a common schema
4. Fix hire date inconsistencies between systems
5. Generate stable employee IDs from name + hire date
6. Normalize division names to UFAS conventions
7. Merge with job metadata for job group classifications
8. Calculate inflation-adjusted salaries using CPI data

Example Usage:
--------------
    from import_data import read_salary_file_names, clean_salary_data

    # Find all salary files in the data directory
    files = read_salary_file_names()
    print(f"Found {len(files)} salary files")

    # Load and clean all the data
    df = clean_salary_data(files)

    # Now you can analyze the data
    print(f"Total records: {len(df)}")
    print(f"Unique employees: {df['id'].nunique()}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")

Dependencies:
-------------
- pandas: Data manipulation
- config: Configuration settings and mappings
- fetch_cpi: CPI data for inflation adjustment

Notes:
------
- UFAS data typically has UPPERCASE names; Workday uses Title Case
- Employee IDs are generated from normalized (uppercase) names for consistency
- Hire dates may differ between systems; UFAS dates are preferred when available
- Jobcodes are normalized to 5 characters (suffixes like U, A, X, N are stripped)
"""
import pandas as pd
import re
import os
import hashlib

import config
from fetch_cpi import load_cpi_data


def read_salary_file_names(folder=None):
    """
    Find salary data files in a folder based on date pattern in filename.

    This function scans a directory for files containing a date pattern
    (YYYY-MM format) in their filename. This pattern is used to identify
    salary data snapshots, which are typically named like:
    - "salaries-2024-03.xlsx"
    - "uw_madison_2023-09_payroll.xlsx"

    Parameters
    ----------
    folder : str, optional
        Folder to search. Defaults to config.DATA_DIR (typically './data').

    Returns
    -------
    list of str
        List of full file paths matching the date pattern (YYYY-MM).
        Paths are sorted by default directory listing order.

    Example
    -------
    >>> files = read_salary_file_names()
    >>> print(files)
    ['./data/salaries-2023-03.xlsx', './data/salaries-2023-09.xlsx', ...]

    >>> files = read_salary_file_names('/custom/path')
    >>> print(len(files))
    24
    """
    if folder is None:
        folder = config.DATA_DIR

    file_names = os.listdir(folder)
    date_pattern = re.compile(r'\d{4}-\d{2}')
    filtered_file_names = [f for f in file_names if date_pattern.search(f)]
    paths = [os.path.join(folder, item) for item in filtered_file_names]
    return paths


# Alias for backward compatibility
read_ufas_file_names = read_salary_file_names


def detect_file_format(df):
    """
    Detect whether a DataFrame is from UFAS or Workday format.

    The two HR systems use different column names for similar data:

    - **Workday** (2025+): Uses 'compensation_basis' or 'pay_rate_type'
    - **UFAS** (pre-2025): Uses 'pay_basis' or 'appt_type_length'

    This detection happens BEFORE column normalization, so it looks at
    the original column names from the Excel file.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with original column names (before normalization).
        Column names are converted to lowercase for comparison.

    Returns
    -------
    str
        One of:
        - 'workday': Newer Workday format (2025 onwards)
        - 'ufas': Legacy UFAS format (pre-2025)
        - 'unknown': Could not determine format

    Example
    -------
    >>> df = pd.read_excel('salaries-2024-03.xlsx')
    >>> format_type = detect_file_format(df)
    >>> print(format_type)
    'ufas'
    """
    cols_lower = [c.lower() for c in df.columns]

    if 'compensation_basis' in cols_lower or 'pay_rate_type' in cols_lower:
        return 'workday'
    elif 'pay_basis' in cols_lower or 'appt_type_length' in cols_lower:
        return 'ufas'
    return 'unknown'


def generate_employee_id(row):
    """
    Generate a stable employee ID from name and hire date.

    Creates a unique identifier for each employee that remains consistent
    across different data snapshots and system formats. This is necessary
    because the raw data doesn't include a persistent employee ID.

    The ID is generated by:
    1. Normalizing names to uppercase (handles UFAS vs Workday case differences)
    2. Combining: "LASTNAME|FIRSTNAME|YYYY-MM-DD"
    3. Computing MD5 hash and taking first 12 hex characters

    Why this approach:
    - Names alone aren't unique (multiple "John Smith" employees)
    - Hire date adds uniqueness for most cases
    - MD5 hash creates a fixed-length, privacy-preserving ID
    - 12 hex chars = 48 bits = ~280 trillion possible values

    Parameters
    ----------
    row : pd.Series
        Row containing:
        - last_name: Employee's last name (any case)
        - first_name: Employee's first name (any case)
        - date_of_hire: Hire date (datetime, string, or NaN)

    Returns
    -------
    str
        12-character hexadecimal ID (e.g., "a1b2c3d4e5f6")

    Example
    -------
    >>> row = pd.Series({
    ...     'last_name': 'Smith',
    ...     'first_name': 'John',
    ...     'date_of_hire': '2020-01-15'
    ... })
    >>> generate_employee_id(row)
    '3f2a1b9c8d7e'

    Notes
    -----
    - Same person with different hire dates will get different IDs
    - This is why we fix hire date inconsistencies before ID generation
    """
    # Normalize names to uppercase and strip whitespace for consistent matching
    # (UFAS uses UPPERCASE, Workday uses Title Case, and whitespace can vary)
    last_name = str(row['last_name']).upper().strip()
    first_name = str(row['first_name']).upper().strip()

    # Handle missing date_of_hire and normalize to YYYY-MM-DD format
    hire_date = row.get('date_of_hire', '')
    if pd.isna(hire_date):
        hire_date = ''
    else:
        # Convert to string and take just the date part (YYYY-MM-DD)
        hire_date = str(hire_date)[:10]

    key = f"{last_name}|{first_name}|{hire_date}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def load_job_metadata(path=None):
    """
    Load job code metadata from the scraped job descriptions CSV.

    Job metadata provides additional context about each job classification:
    - job_group: Broad category (e.g., "Research", "Administrative")
    - job_subgroup: More specific category
    - education: Required education level
    - salary_range_summary: Min/max salary range
    - supervisory_required: Whether the role requires supervising others
    - institution_job: Whether it's an institution-wide vs unit-specific job

    This data was scraped from UW's official job classification system and
    is used to enrich the salary data with job-level attributes.

    Parameters
    ----------
    path : str, optional
        Path to the job descriptions CSV file.
        Defaults to config.JOB_DESCRIPTIONS_FILE.

    Returns
    -------
    pd.DataFrame
        Job metadata with columns:
        - jobcode: 5-character job classification code (uppercase)
        - job_group: Broad job category
        - job_subgroup: Specific job subcategory
        - education: Required education
        - salary_range_summary: Salary range string
        - supervisory_required: Boolean/string
        - institution_job: Boolean/string

    Raises
    ------
    FileNotFoundError
        If the job descriptions file doesn't exist.

    Example
    -------
    >>> job_meta = load_job_metadata()
    >>> job_meta[job_meta['jobcode'] == 'RE007']
       jobcode  job_group job_subgroup education ...
    0    RE007   Research    Scientist  Doctoral ...
    """
    if path is None:
        path = config.JOB_DESCRIPTIONS_FILE

    job_meta = pd.read_csv(path)
    job_meta['jobcode'] = job_meta['job_code'].str.upper()

    # Select relevant columns for enrichment
    columns_to_keep = [
        'jobcode', 'job_group', 'job_subgroup', 'education',
        'salary_range_summary', 'supervisory_required', 'institution_job'
    ]
    existing_cols = [c for c in columns_to_keep if c in job_meta.columns]

    return job_meta[existing_cols].drop_duplicates(subset=['jobcode'])


def normalize_columns(df, file_format):
    """
    Normalize column names based on file format.

    Different HR systems use different column names for the same data.
    This function standardizes column names so downstream code can use
    consistent field names regardless of the source format.

    Normalization steps:
    1. Convert all column names to lowercase
    2. Replace spaces with underscores
    3. Drop columns we don't need (defined in config.COLUMNS_TO_DROP)
    4. Rename format-specific columns to standard names

    Example column mappings:
    - 'Annual Full Salary' -> 'current_annual_contracted_salary'
    - 'Full-Time Equivalent' -> 'full_time_equivalent'
    - 'employee_contract_type' (Workday) -> 'appt_type_length'
    - 'appointment_type_and_length' (UFAS) -> 'appt_type_length'

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with original column names from the Excel file.
    file_format : str
        Either 'workday' or 'ufas', as returned by detect_file_format().

    Returns
    -------
    pd.DataFrame
        DataFrame with normalized column names. The returned DataFrame
        has consistent column names that can be used by all downstream
        processing functions.

    See Also
    --------
    config.UFAS_COLUMN_RENAMES : Mapping for UFAS column names
    config.WORKDAY_COLUMN_RENAMES : Mapping for Workday column names
    config.COLUMNS_TO_DROP : Columns to remove
    """
    # Lowercase and replace spaces with underscores
    df.columns = df.columns.str.lower().str.replace(' ', '_')

    # Drop columns we don't need
    for col in config.COLUMNS_TO_DROP:
        if col in df.columns:
            df = df.drop(columns=[col])

    # Apply format-specific renames
    if file_format == 'workday':
        df = df.rename(columns=config.WORKDAY_COLUMN_RENAMES)
    else:
        df = df.rename(columns=config.UFAS_COLUMN_RENAMES)

    return df


def clean_salary_data(filenames, job_metadata=None):
    """
    Clean and combine salary data from multiple Excel files.

    This is the main entry point for loading salary data. It handles all the
    complexity of working with multiple files from different HR systems and
    produces a clean, analysis-ready dataset.

    Processing steps:
    1. Load each Excel file and detect its format (UFAS or Workday)
    2. Normalize column names to a common schema
    3. Extract date from filename and add as 'Date' column
    4. Combine all files into a single DataFrame
    5. Fix hire date inconsistencies (use UFAS dates when available)
    6. Generate stable employee IDs
    7. Normalize employee categories and division names
    8. Normalize jobcodes (strip suffixes)
    9. Calculate derived fields (FTE-adjusted salary, division_department)
    10. Merge CPI data for inflation adjustment
    11. Merge job metadata for job classifications

    Output columns include:
    - id: Stable employee identifier
    - Date: Snapshot date (datetime)
    - last_name, first_name: Employee name
    - division, department: Organizational unit
    - title, jobcode: Job classification
    - current_annual_contracted_salary: Base annual salary
    - full_time_equivalent: FTE (0.0 to 1.0)
    - fte_adjusted_salary: Salary × FTE
    - Real_Salary_2021_Dollars: Inflation-adjusted salary (2021 dollars)
    - FTE_Adjusted_Salary_2021_Dollars: FTE × inflation-adjusted salary
    - employee_category: Faculty, Academic Staff, etc.
    - job_group, job_subgroup: From job metadata
    - And many more...

    Parameters
    ----------
    filenames : list of str
        List of Excel file paths to process. Files should have a date
        pattern (YYYY-MM) in the filename for date extraction.
    job_metadata : pd.DataFrame, optional
        Job metadata from load_job_metadata(). If None, will attempt to
        load automatically. If file not found, continues without metadata.

    Returns
    -------
    pd.DataFrame
        Cleaned and enriched salary data with all employees from all
        input files combined.

    Raises
    ------
    FileNotFoundError
        If CPI data file is not found. Run fetch_cpi.py first.

    Example
    -------
    >>> from import_data import read_salary_file_names, clean_salary_data
    >>>
    >>> # Load all salary data
    >>> files = read_salary_file_names()
    >>> df = clean_salary_data(files)
    >>>
    >>> # Basic analysis
    >>> print(f"Records: {len(df):,}")
    >>> print(f"Unique employees: {df['id'].nunique():,}")
    >>> print(f"Date range: {df['Date'].min():%Y-%m} to {df['Date'].max():%Y-%m}")
    >>>
    >>> # Filter to latest snapshot
    >>> latest = df[df['Date'] == df['Date'].max()]
    >>> print(f"Current employees: {latest['id'].nunique():,}")

    Notes
    -----
    - Processing can be memory-intensive for large datasets
    - CPI data must be available (run fetch_cpi.py to download)
    - Job metadata is optional but recommended for full analysis
    """
    # Load job metadata if not provided
    if job_metadata is None:
        try:
            job_metadata = load_job_metadata()
        except FileNotFoundError:
            print("Warning: Job descriptions file not found. Job metadata will not be merged.")
            job_metadata = None

    # Load CPI data
    try:
        cpi_data = load_cpi_data()
    except FileNotFoundError as e:
        raise FileNotFoundError(str(e))

    all_salaries = []

    for file in filenames:
        # Read Excel file
        df = pd.read_excel(file)

        # Detect format and normalize
        file_format = detect_file_format(df)
        df = normalize_columns(df, file_format)

        # Extract date from filename
        date_match = re.search(r'\d+-\d+', file)
        df['Date'] = date_match.group(0) if date_match else None

        all_salaries.append(df)

    # Combine all salary data
    salaries = pd.concat(all_salaries, ignore_index=True)

    # Convert Date to datetime early for comparison
    salaries['Date'] = pd.to_datetime(salaries['Date'])

    # Fix hire date inconsistencies between UFAS and Workday
    # Workday data (2025-09+) sometimes has different hire dates than UFAS
    # Normalize hire dates: use earliest hire date for each person across all records
    # This fixes inconsistencies where the same person has different hire dates in different snapshots

    # Create normalized name key for matching
    salaries['_name_key'] = (salaries['last_name'].str.upper().str.strip() + '|' +
                             salaries['first_name'].str.upper().str.strip())

    # For each name, get the earliest hire date across ALL records
    earliest_hire_dates = salaries.groupby('_name_key')['date_of_hire'].min().to_dict()

    # Apply earliest hire date to ALL records for each person
    salaries['date_of_hire'] = salaries['_name_key'].map(earliest_hire_dates)

    # Clean up temporary column
    salaries = salaries.drop(columns=['_name_key'])

    # Generate unique employee IDs using name and hire date
    salaries['id'] = salaries.apply(generate_employee_id, axis=1)

    # Map employee category codes to full names
    salaries['employee_category'] = salaries['employee_category'].replace(
        config.EMPLOYEE_CATEGORIES
    )

    # Normalize jobcodes to 5 characters (strip U, A, X, N suffixes)
    # These suffixes indicate variants but the base 5-char code is the actual job classification
    def normalize_jobcode(jc):
        if pd.isna(jc):
            return jc
        jc = str(jc)
        if len(jc) == 6 and jc[-1] in ('U', 'A', 'X', 'N'):
            return jc[:5]
        return jc

    salaries['jobcode'] = salaries['jobcode'].apply(normalize_jobcode)

    # Normalize division names (map Workday names to UFAS names for consistency)
    salaries['division'] = salaries['division'].replace(config.DIVISION_NAME_MAPPING)

    # Create derived fields
    salaries['division_department'] = salaries['division'] + ' - ' + salaries['department']

    # Calculate FTE adjusted salary
    salaries['fte_adjusted_salary'] = (
        salaries['current_annual_contracted_salary'] * salaries['full_time_equivalent']
    )

    salaries['id_jobcode'] = salaries['id'].astype(str) + '_' + salaries['jobcode']
    salaries['FullTime'] = salaries['full_time_equivalent'] == 1
    salaries['JobGroup'] = salaries['jobcode'].str[:2]
    salaries['JobNumber'] = salaries['jobcode'].str[2:]

    # Merge CPI data for inflation adjustment
    salaries = salaries.merge(cpi_data[['Date', 'CPI', 'CPI_2021_Index']], on='Date', how='left')
    salaries['2021_Index'] = salaries['CPI_2021_Index']
    salaries['FTE_Adjusted_Salary_2021_Dollars'] = (
        salaries['fte_adjusted_salary'] * salaries['2021_Index']
    )
    # Non-FTE-adjusted real salary (for apples-to-apples comparisons)
    salaries['Real_Salary_2021_Dollars'] = (
        salaries['current_annual_contracted_salary'] * salaries['2021_Index']
    )

    # Merge job metadata if available
    if job_metadata is not None:
        salaries = salaries.merge(job_metadata, on='jobcode', how='left')
        # Use job_group from metadata, falling back to derived JobGroup prefix
        if 'job_group' in salaries.columns:
            salaries['jobgroup'] = salaries['job_group']
        else:
            salaries['jobgroup'] = None
    else:
        salaries['jobgroup'] = None

    return salaries


# Backward compatibility alias
def clean_ufas_data(filenames, fred_api_key=None):
    """
    Legacy function name for backward compatibility.

    Note: fred_api_key parameter is ignored - CPI data is now loaded from cache.
    Run fetch_cpi.py to update CPI data.
    """
    if fred_api_key is not None:
        print("Note: fred_api_key parameter is deprecated. CPI data is loaded from cache.")
        print("Run 'python fetch_cpi.py' to update CPI data.")

    return clean_salary_data(filenames)
