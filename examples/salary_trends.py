"""
Salary Trends Analysis Example
==============================

This script demonstrates how to analyze salary trends over time,
including inflation-adjusted (real) salaries.

Topics covered:
- Tracking salary changes over time
- Comparing nominal vs real (inflation-adjusted) salaries
- Analyzing trends by employee category or division

Usage:
    python examples/salary_trends.py
"""
import sys
import os

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from import_data import read_salary_file_names, clean_salary_data


def main():
    """Analyze salary trends over time."""

    # Load data
    print("Loading salary data...")
    files = read_salary_file_names()
    df = clean_salary_data(files)
    print(f"Loaded {len(df):,} records")
    print()

    # =========================================================================
    # ANALYSIS 1: University-wide salary trends
    # =========================================================================
    print("=" * 60)
    print("University-Wide Median Salary Trends")
    print("=" * 60)
    print()

    # Calculate median salary per date
    trends = df.groupby('Date').agg({
        'current_annual_contracted_salary': 'median',
        'FTE_Adjusted_Salary_2021_Dollars': 'median',
        'id': 'nunique'
    }).rename(columns={
        'current_annual_contracted_salary': 'Median Nominal',
        'FTE_Adjusted_Salary_2021_Dollars': 'Median Real (2021$)',
        'id': 'Employee Count'
    })

    print(trends.to_string())
    print()

    # Calculate overall change
    first_date = trends.index.min()
    last_date = trends.index.max()
    first_nominal = trends.loc[first_date, 'Median Nominal']
    last_nominal = trends.loc[last_date, 'Median Nominal']
    first_real = trends.loc[first_date, 'Median Real (2021$)']
    last_real = trends.loc[last_date, 'Median Real (2021$)']

    print(f"Overall Changes ({first_date:%Y-%m} to {last_date:%Y-%m}):")
    print(f"  Nominal salary: ${first_nominal:,.0f} -> ${last_nominal:,.0f} ({(last_nominal/first_nominal-1)*100:+.1f}%)")
    print(f"  Real salary:    ${first_real:,.0f} -> ${last_real:,.0f} ({(last_real/first_real-1)*100:+.1f}%)")
    print()

    # =========================================================================
    # ANALYSIS 2: Trends by employee category
    # =========================================================================
    print("=" * 60)
    print("Median Salary Trends by Employee Category")
    print("=" * 60)
    print()

    # Focus on main categories
    main_categories = ['Faculty', 'Academic Staff', 'University Staff', 'Limited Appointee']

    cat_trends = df[df['employee_category'].isin(main_categories)].groupby(
        ['Date', 'employee_category']
    )['current_annual_contracted_salary'].median().unstack()

    # Show latest values and percent change
    print("Latest Median Salaries:")
    latest = cat_trends.iloc[-1]
    first = cat_trends.iloc[0]
    for cat in main_categories:
        if cat in latest.index:
            pct_change = (latest[cat] / first[cat] - 1) * 100
            print(f"  {cat}: ${latest[cat]:,.0f} ({pct_change:+.1f}% since {first_date:%Y-%m})")
    print()

    # =========================================================================
    # ANALYSIS 3: Division-level analysis
    # =========================================================================
    print("=" * 60)
    print("Salary Trends for Selected Division")
    print("=" * 60)
    print()

    # Example: Look at one division
    example_division = "Sch of Med & Public Health"

    div_data = df[df['division'] == example_division]
    if len(div_data) > 0:
        div_trends = div_data.groupby('Date').agg({
            'current_annual_contracted_salary': 'median',
            'id': 'nunique',
            'full_time_equivalent': 'sum'
        }).rename(columns={
            'current_annual_contracted_salary': 'Median Salary',
            'id': 'Employees',
            'full_time_equivalent': 'Total FTE'
        })

        print(f"Division: {example_division}")
        print()
        print(div_trends.to_string())
    else:
        print(f"Division '{example_division}' not found in data.")
    print()

    # =========================================================================
    # ANALYSIS 4: Finding employees with largest salary increases
    # =========================================================================
    print("=" * 60)
    print("Employees with Largest Salary Increases")
    print("=" * 60)
    print()

    # Get first and last record for each employee
    first_records = df.sort_values('Date').drop_duplicates('id', keep='first')
    last_records = df.sort_values('Date').drop_duplicates('id', keep='last')

    # Merge to compare
    comparison = first_records[['id', 'Date', 'current_annual_contracted_salary', 'first_name', 'last_name']].merge(
        last_records[['id', 'Date', 'current_annual_contracted_salary', 'title', 'division']],
        on='id',
        suffixes=('_first', '_last')
    )

    # Filter to employees with at least 2 years of data
    comparison = comparison[comparison['Date_last'] > comparison['Date_first'] + pd.Timedelta(days=365*2)]

    # Calculate dollar and percent increase
    comparison['dollar_increase'] = comparison['current_annual_contracted_salary_last'] - comparison['current_annual_contracted_salary_first']
    comparison['pct_increase'] = (comparison['dollar_increase'] / comparison['current_annual_contracted_salary_first']) * 100

    # Show top 10 by percent increase (among those with reasonable starting salary)
    reasonable = comparison[comparison['current_annual_contracted_salary_first'] >= 30000]
    top_increases = reasonable.nlargest(10, 'pct_increase')

    print("Top 10 by Percent Increase (min 2 years, min $30k starting):")
    for _, row in top_increases.iterrows():
        print(f"  {row['first_name']} {row['last_name']}: "
              f"${row['current_annual_contracted_salary_first']:,.0f} -> "
              f"${row['current_annual_contracted_salary_last']:,.0f} "
              f"({row['pct_increase']:+.1f}%)")

    print()
    print("Note: Large increases often indicate promotions or title changes.")


if __name__ == "__main__":
    main()
