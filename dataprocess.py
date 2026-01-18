"""
Data Processing and Analysis Module for UW-Madison Salary Data
===============================================================

This module provides higher-level analysis functions that build on the cleaned
data from import_data.py. While import_data.py handles data loading and
normalization, this module focuses on analytical transformations and metrics.

Key Capabilities:
-----------------
1. **FTE Analysis**: Calculate full-time equivalent counts by division,
   department, and job group
2. **Transfer Tracking**: Identify employees who moved between departments
3. **Reorganization Detection**: Distinguish real transfers from organizational
   restructuring (department renames, mergers, etc.)
4. **Faculty Classification**: Identify divisions with faculty appointments
5. **Time Series Analysis**: Track changes in FTE over time

Why Reorganization Detection Matters:
-------------------------------------
When UW-Madison transitioned from UFAS to Workday in 2025, many departments
were renamed or reorganized. Without proper detection, these could appear as
mass employee transfers when in fact people simply stayed in their renamed
departments. This module uses name similarity analysis to identify:

- **Name changes**: "Sch of Med & Public Health" → "School of Medicine and Public Health"
- **Division renames**: Same department under differently-named division
- **Mass restructuring**: Large groups moving between similar-named units

Analysis Output:
----------------
The run_full_analysis() function returns a dictionary containing:
- salary_data: Enhanced salary data with analysis flags
- dept_jobgroup_prop: FTE proportions by job group within departments
- dept_fte_pivot: Pivot table of FTE by department and date
- fte_changes: FTE changes relative to baseline
- fte_change_pivot: Pivoted view of FTE changes
- transfer_counts: Real transfer counts (excluding reorgs)
- transfer_pairs: Department pairs with transfer and reorg flags
- reorg_summary: Summary of detected reorganizations

Example Usage:
--------------
    import dataprocess

    # Run full analysis pipeline
    results = dataprocess.run_full_analysis()

    # Access the enhanced salary data
    df = results['salary_data']
    print(f"Total records: {len(df):,}")

    # See reorganization detection results
    print(results['reorg_summary'])

    # Get departments with significant transfers
    transfers = results['transfer_pairs']
    real_transfers = transfers[~transfers['is_reorg']]
    print(f"Real transfer pairs: {len(real_transfers)}")

    # Or run individual functions for specific analyses
    salary_data = dataprocess.load_salary_data()
    salary_data = dataprocess.add_analysis_flags(salary_data)
    fte_by_group = dataprocess.calculate_fte_changes(salary_data)

Running as Script:
------------------
This module can be run directly to perform a full analysis and print
summary statistics:

    python dataprocess.py

Dependencies:
-------------
- pandas: Data manipulation
- import_data: Data loading (this project)
- config: Configuration settings (this project)
- difflib: Name similarity calculations (standard library)
"""
import pandas as pd
import re
from difflib import SequenceMatcher
import import_data
import config


# =============================================================================
# Reorganization Detection Functions
# =============================================================================

def normalize_dept_name(name):
    """
    Normalize department name for comparison.

    Standardizes abbreviations and removes minor variations to help
    identify when two department names refer to the same unit.

    Parameters
    ----------
    name : str
        Department name (division - department format).

    Returns
    -------
    str
        Normalized name for comparison.
    """
    if not isinstance(name, str):
        return ""

    # Convert to lowercase
    s = name.lower()

    # Common abbreviations and their expansions
    replacements = [
        (r'\bsch\b', 'school'),
        (r'\bmed\b', 'medicine'),
        (r'\bmgmt\b', 'management'),
        (r'\badmin\b', 'administration'),
        (r'\brsrch\b', 'research'),
        (r'\bvc\b', 'vice chancellor'),
        (r'\bavc\b', 'associate vice chancellor'),
        (r'\bedu\b', 'education'),
        (r'\bsci\b', 'science'),
        (r'\beng\b', 'engineering'),
        (r'\bctr\b', 'center'),
        (r'\bsrvcs?\b', 'services'),
        (r'\bsvcs?\b', 'services'),
        (r'\bdept\b', 'department'),
        (r'\bprog\b', 'program'),
        (r'\binst\b', 'institute'),
        (r'\binfo\b', 'information'),
        (r'\btech\b', 'technology'),
        (r'\bcomm\b', 'communication'),
        (r'\bdev\b', 'development'),
        (r'\bop\b', 'operation'),
        (r'\bops\b', 'operations'),
        (r'\bmaint\b', 'maintenance'),
        (r'\bfac\b', 'facilities'),
        (r'\bpp\b', 'physical plant'),
        (r'\bag\b', 'agricultural'),
    ]

    for pattern, replacement in replacements:
        s = re.sub(pattern, replacement, s)

    # Remove punctuation and extra whitespace
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()

    return s


def calculate_name_similarity(name1, name2):
    """
    Calculate similarity between two department names.

    Uses normalized names and SequenceMatcher for fuzzy matching.

    Parameters
    ----------
    name1, name2 : str
        Department names to compare.

    Returns
    -------
    float
        Similarity score between 0 and 1.
    """
    norm1 = normalize_dept_name(name1)
    norm2 = normalize_dept_name(name2)

    if not norm1 or not norm2:
        return 0.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def detect_reorganizations(transfer_pairs, similarity_threshold=0.7, min_transfers=20):
    """
    Detect reorganizations vs real transfers based on name similarity and volume.

    A reorganization is identified when:
    - Many employees (>= min_transfers) move between two departments
    - The department names are similar (>= similarity_threshold)

    Parameters
    ----------
    transfer_pairs : pd.DataFrame
        DataFrame with prev_division_department, division_department, transfer_count.
    similarity_threshold : float, optional
        Minimum name similarity to consider a reorganization. Default 0.7.
    min_transfers : int, optional
        Minimum transfers to consider a reorganization. Default 20.

    Returns
    -------
    pd.DataFrame
        Transfer pairs with additional columns:
        - name_similarity: similarity score between dept names
        - is_reorg: True if this appears to be a reorganization
        - reorg_reason: explanation of why flagged as reorg
    """
    df = transfer_pairs.copy()

    # Calculate name similarity for each pair
    df['name_similarity'] = df.apply(
        lambda row: calculate_name_similarity(
            row['prev_division_department'],
            row['division_department']
        ),
        axis=1
    )

    # Identify reorganizations
    df['is_reorg'] = False
    df['reorg_reason'] = ''

    # High similarity + high volume = reorganization (name change)
    mask_similar = (
        (df['name_similarity'] >= similarity_threshold) &
        (df['transfer_count'] >= min_transfers)
    )
    df.loc[mask_similar, 'is_reorg'] = True
    df.loc[mask_similar, 'reorg_reason'] = 'name_change'

    # Very high volume even with lower similarity = likely restructuring
    mask_mass = (
        (df['transfer_count'] >= 100) &
        (df['name_similarity'] >= 0.5) &
        (~df['is_reorg'])
    )
    df.loc[mask_mass, 'is_reorg'] = True
    df.loc[mask_mass, 'reorg_reason'] = 'mass_restructure'

    # Check for division-level reorganizations (same department, different division naming)
    def check_dept_match(row):
        if row['is_reorg']:
            return row['is_reorg'], row['reorg_reason']

        # Extract department part (after " - ")
        prev_parts = row['prev_division_department'].split(' - ', 1)
        curr_parts = row['division_department'].split(' - ', 1)

        if len(prev_parts) == 2 and len(curr_parts) == 2:
            prev_dept = prev_parts[1]
            curr_dept = curr_parts[1]
            dept_similarity = calculate_name_similarity(prev_dept, curr_dept)

            if dept_similarity >= 0.85 and row['transfer_count'] >= min_transfers:
                return True, 'division_rename'

        return row['is_reorg'], row['reorg_reason']

    results = df.apply(check_dept_match, axis=1, result_type='expand')
    df['is_reorg'] = results[0]
    df['reorg_reason'] = results[1]

    return df


def build_reorg_mapping(reorg_pairs):
    """
    Build a mapping of old department names to new department names.

    Parameters
    ----------
    reorg_pairs : pd.DataFrame
        Transfer pairs where is_reorg is True.

    Returns
    -------
    dict
        Mapping of old_dept_name -> new_dept_name for reorganizations.
    """
    mapping = {}
    for _, row in reorg_pairs[reorg_pairs['is_reorg']].iterrows():
        old_name = row['prev_division_department']
        new_name = row['division_department']
        # If multiple mappings, keep the one with highest transfer count
        if old_name not in mapping:
            mapping[old_name] = new_name
    return mapping


def load_salary_data(min_fte=0.01):
    """
    Load and prepare salary data for analysis.

    Parameters
    ----------
    min_fte : float, optional
        Minimum FTE to include. Defaults to 0.01 (excludes 0 FTE appointments).

    Returns
    -------
    pd.DataFrame
        Cleaned salary data with job group information.
    """
    filenames = import_data.read_salary_file_names()
    salary_data = import_data.clean_salary_data(filenames)

    # Remove very low FTE appointments
    salary_data = salary_data.loc[salary_data['full_time_equivalent'] > min_fte].copy()

    return salary_data


def identify_faculty_divisions(salary_data):
    """
    Identify divisions that have faculty appointments.

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data with employee_category and division columns.

    Returns
    -------
    list
        List of division names that have faculty.
    """
    faculty_divisions = (
        salary_data
        .loc[salary_data['employee_category'] == "Faculty", 'division']
        .unique()
        .tolist()
    )
    return faculty_divisions


def add_analysis_flags(salary_data):
    """
    Add analysis flags to salary data.

    Adds:
    - IsFacultyDivision: whether division has any faculty
    - IsFacResTeachingTitle: whether job is faculty/research/teaching

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data to enhance.

    Returns
    -------
    pd.DataFrame
        Salary data with additional flag columns.
    """
    df = salary_data.copy()

    # Identify faculty divisions
    faculty_division_list = identify_faculty_divisions(df)
    df['IsFacultyDivision'] = df['division'].isin(faculty_division_list)

    # Identify faculty/research/teaching titles
    df['IsFacResTeachingTitle'] = (
        df['jobgroup'].isin(config.FACULTY_INSTRUCTION_RESEARCH_JOBGROUPS) &
        ~(
            (df['jobgroup'] == 'Teaching and Learning') &
            df['title'].isin(config.NON_TEACHING_TITLES_TLA)
        )
    )

    return df


def calculate_department_jobgroup_proportions(salary_data):
    """
    Calculate FTE proportions by job group within each department.

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data with division, department, Date, jobgroup, and full_time_equivalent.

    Returns
    -------
    pd.DataFrame
        Proportions of FTE by job group for each division/department/date.
    """
    # Group and sum FTE
    grouped = (
        salary_data
        .groupby(['division', 'department', 'Date', 'jobgroup'], as_index=False)
        ['full_time_equivalent']
        .sum()
    )

    # Calculate total FTE per division/department/date
    totals = (
        grouped
        .groupby(['division', 'department', 'Date'], as_index=False)
        ['full_time_equivalent']
        .sum()
        .rename(columns={'full_time_equivalent': 'total_fte'})
    )

    # Merge and calculate proportions
    result = grouped.merge(totals, on=['division', 'department', 'Date'])
    result['fte_proportion'] = result['full_time_equivalent'] / result['total_fte']

    return result


def calculate_department_fte_pivot(salary_data):
    """
    Create a pivot table of FTE by department and date.

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data.

    Returns
    -------
    pd.DataFrame
        Pivot table with divisions/departments as rows and dates as columns.
    """
    grouped = (
        salary_data
        .groupby(['division', 'department', 'Date'], as_index=False)
        ['full_time_equivalent']
        .sum()
    )

    pivot = grouped.pivot_table(
        index=['division', 'department'],
        columns='Date',
        values='full_time_equivalent'
    )

    return pivot


def calculate_fte_changes(salary_data, start_date=None):
    """
    Calculate FTE changes relative to a starting date.

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data with IsFacultyDivision flag.
    start_date : str or datetime, optional
        Date to use as baseline. If None, uses earliest date in data.

    Returns
    -------
    pd.DataFrame
        FTE by faculty division status and job group with change metrics.
    """
    # Group by faculty division status, job group, and date
    fte_by_group = (
        salary_data
        .groupby(['IsFacultyDivision', 'jobgroup', 'Date'], as_index=False)
        ['full_time_equivalent']
        .sum()
    )

    # Sort to ensure first value is the baseline
    fte_by_group = fte_by_group.sort_values(['IsFacultyDivision', 'jobgroup', 'Date'])

    # Calculate starting FTE for each group
    fte_by_group['start_fte'] = (
        fte_by_group
        .groupby(['IsFacultyDivision', 'jobgroup'])
        ['full_time_equivalent']
        .transform('first')
    )

    # Calculate absolute and percent change
    fte_by_group['fte_change'] = (
        fte_by_group['full_time_equivalent'] - fte_by_group['start_fte']
    )

    fte_by_group['fte_pct_change'] = (
        fte_by_group['fte_change'] / fte_by_group['start_fte'] * 100
    )

    return fte_by_group


def create_fte_change_pivot(fte_changes, min_date='2025-01-01', value_column='fte_change'):
    """
    Create a pivot table of FTE changes.

    Parameters
    ----------
    fte_changes : pd.DataFrame
        Output from calculate_fte_changes().
    min_date : str, optional
        Minimum date to include. Defaults to '2025-01-01'.
    value_column : str, optional
        Column to pivot ('fte_change' or 'fte_pct_change').

    Returns
    -------
    pd.DataFrame
        Pivot table with job groups as rows and faculty division status as columns.
    """
    filtered = fte_changes.loc[fte_changes['Date'] >= min_date]

    pivot = filtered.pivot_table(
        index='jobgroup',
        columns='IsFacultyDivision',
        values=value_column
    ).reset_index()

    return pivot


def track_employee_transfers(salary_data, similarity_threshold=0.7, min_reorg_transfers=20):
    """
    Track employees who have transferred between departments.

    Distinguishes between real transfers and reorganizations (department renames
    or restructuring) using name similarity analysis.

    Parameters
    ----------
    salary_data : pd.DataFrame
        Salary data with id_jobcode and division_department columns.
    similarity_threshold : float, optional
        Minimum name similarity to consider a reorganization. Default 0.7.
    min_reorg_transfers : int, optional
        Minimum transfers to consider a reorganization. Default 20.

    Returns
    -------
    tuple
        (salary_data_with_flags, transfer_counts, transfer_pairs, reorg_summary)
        - salary_data_with_flags: original data with transfer tracking columns
        - transfer_counts: count of transferred employees by dept/date (real only)
        - transfer_pairs: pairs of departments with transfer counts and reorg flags
        - reorg_summary: summary of detected reorganizations
    """
    df = salary_data.copy()

    # Sort by employee ID and date to track changes (use 'id' not 'id_jobcode')
    df = df.sort_values(['id', 'Date'])

    # Identify department changes for each employee
    df['prev_division_department'] = (
        df.groupby('id')['division_department'].shift(1)
    )

    df['dept_changed'] = (
        (df['division_department'] != df['prev_division_department']) &
        df['prev_division_department'].notna()
    )

    # Calculate all transfer pairs (from -> to)
    all_transfer_pairs = (
        df[df['dept_changed']]
        .groupby(['prev_division_department', 'division_department'])
        .size()
        .reset_index(name='transfer_count')
    )

    # Detect reorganizations
    transfer_pairs = detect_reorganizations(
        all_transfer_pairs,
        similarity_threshold=similarity_threshold,
        min_transfers=min_reorg_transfers
    )

    # Build reorg mapping for flagging individual records
    reorg_mapping = build_reorg_mapping(transfer_pairs)

    # Create a set of reorg transfer pairs for fast lookup
    reorg_pairs_set = set(
        zip(
            transfer_pairs[transfer_pairs['is_reorg']]['prev_division_department'],
            transfer_pairs[transfer_pairs['is_reorg']]['division_department']
        )
    )

    # Flag each transfer as reorg or real
    def classify_transfer(row):
        if not row['dept_changed']:
            return False, False
        pair = (row['prev_division_department'], row['division_department'])
        is_reorg = pair in reorg_pairs_set
        return is_reorg, not is_reorg

    classifications = df.apply(classify_transfer, axis=1, result_type='expand')
    df['is_reorg_transfer'] = classifications[0]
    df['is_real_transfer'] = classifications[1]

    # Count real transfers only (excluding reorgs)
    real_transfer_emps = df.loc[df['is_real_transfer'], 'id'].unique()

    transfer_counts = (
        df[df['id'].isin(real_transfer_emps)]
        .groupby(['division_department', 'Date'], as_index=False)
        ['id']
        .nunique()
        .rename(columns={'id': 'num_real_transfers'})
    )

    # Flag departments with significant real transfers (10+)
    depts_with_transfers = transfer_counts.loc[
        transfer_counts['num_real_transfers'] >= 10,
        ['division_department', 'Date']
    ].copy()
    depts_with_transfers['has_significant_transfers'] = True

    df = df.merge(depts_with_transfers, on=['division_department', 'Date'], how='left')
    df['has_significant_transfers'] = df['has_significant_transfers'].fillna(False).infer_objects(copy=False).astype(bool)

    # Create reorg summary
    reorg_summary = transfer_pairs[transfer_pairs['is_reorg']].groupby('reorg_reason').agg({
        'transfer_count': ['count', 'sum'],
        'name_similarity': 'mean'
    }).round(2)
    reorg_summary.columns = ['num_pairs', 'total_employees', 'avg_similarity']
    reorg_summary = reorg_summary.reset_index()

    # Keep old column name for backward compatibility
    df['transferred'] = df['dept_changed']
    df['DeptHas4PlusTransfers'] = df['has_significant_transfers']  # Renamed but kept for compatibility

    return df, transfer_counts, transfer_pairs, reorg_summary


def run_full_analysis(min_fte=0.01):
    """
    Run the full analysis pipeline.

    Parameters
    ----------
    min_fte : float, optional
        Minimum FTE threshold.

    Returns
    -------
    dict
        Dictionary containing all analysis outputs:
        - salary_data: full enriched salary data
        - dept_jobgroup_prop: department job group proportions
        - dept_fte_pivot: department FTE pivot table
        - fte_changes: FTE changes over time
        - fte_change_pivot: pivoted FTE changes
        - fte_pct_change_pivot: pivoted FTE percent changes
        - transfer_counts: transfer counts by department (real transfers only)
        - transfer_pairs: transfer pairs with reorg detection flags
        - reorg_summary: summary of detected reorganizations
    """
    # Load data
    salary_data = load_salary_data(min_fte=min_fte)

    # Add analysis flags
    salary_data = add_analysis_flags(salary_data)

    # Calculate various metrics
    dept_jobgroup_prop = calculate_department_jobgroup_proportions(salary_data)
    dept_fte_pivot = calculate_department_fte_pivot(salary_data)
    fte_changes = calculate_fte_changes(salary_data)
    fte_change_pivot = create_fte_change_pivot(fte_changes, value_column='fte_change')
    fte_pct_change_pivot = create_fte_change_pivot(fte_changes, value_column='fte_pct_change')

    # Track transfers with reorganization detection
    salary_data, transfer_counts, transfer_pairs, reorg_summary = track_employee_transfers(salary_data)

    return {
        'salary_data': salary_data,
        'dept_jobgroup_prop': dept_jobgroup_prop,
        'dept_fte_pivot': dept_fte_pivot,
        'fte_changes': fte_changes,
        'fte_change_pivot': fte_change_pivot,
        'fte_pct_change_pivot': fte_pct_change_pivot,
        'transfer_counts': transfer_counts,
        'transfer_pairs': transfer_pairs,
        'reorg_summary': reorg_summary,
    }


# Only run if executed directly (not imported)
if __name__ == '__main__':
    print("Running full salary data analysis...")
    results = run_full_analysis()

    print(f"\nLoaded {len(results['salary_data'])} salary records")
    print(f"Date range: {results['salary_data']['Date'].min()} to {results['salary_data']['Date'].max()}")
    print(f"Unique employees: {results['salary_data']['id'].nunique()}")

    # Show reorganization detection results
    print("\n--- Reorganization Detection Summary ---")
    print(results['reorg_summary'].to_string(index=False))

    # Show transfer pair statistics
    tp = results['transfer_pairs']
    print(f"\n--- Transfer Pair Statistics ---")
    print(f"Total transfer pairs: {len(tp)}")
    print(f"Reorganization pairs: {tp['is_reorg'].sum()}")
    print(f"Real transfer pairs: {(~tp['is_reorg']).sum()}")
    print(f"Employees in reorg transfers: {tp[tp['is_reorg']]['transfer_count'].sum():,}")
    print(f"Employees in real transfers: {tp[~tp['is_reorg']]['transfer_count'].sum():,}")

    # Show sample real transfers
    print("\n--- Top Real Transfer Pairs (not reorganizations) ---")
    real_transfers = tp[~tp['is_reorg']].nlargest(10, 'transfer_count')
    for _, row in real_transfers.iterrows():
        print(f"  {row['transfer_count']:>3}: {row['prev_division_department'][:40]}")
        print(f"       -> {row['division_department'][:40]}")

    # Show sample outputs
    print("\n--- FTE Change by Job Group (since 2025) ---")
    print(results['fte_change_pivot'].head(10).to_string())
