"""
Basic Analysis Example
======================

This script demonstrates how to use the UW-Madison salary data pipeline
for basic data exploration and analysis.

This is a good starting point for understanding the data structure and
available fields.

Usage:
    python examples/basic_analysis.py
"""
import sys
import os

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from import_data import read_salary_file_names, clean_salary_data


def main():
    """Run basic analysis on salary data."""

    # =========================================================================
    # STEP 1: Load the data
    # =========================================================================
    print("Loading salary data...")
    print("-" * 50)

    # Find all salary data files
    files = read_salary_file_names()
    print(f"Found {len(files)} salary data files")

    # Load and clean the data
    df = clean_salary_data(files)
    print(f"Loaded {len(df):,} total records")
    print()

    # =========================================================================
    # STEP 2: Basic overview
    # =========================================================================
    print("Data Overview")
    print("-" * 50)

    print(f"Date range: {df['Date'].min():%Y-%m} to {df['Date'].max():%Y-%m}")
    print(f"Unique employees: {df['id'].nunique():,}")
    print(f"Unique divisions: {df['division'].nunique()}")
    print(f"Unique departments: {df['department'].nunique()}")
    print(f"Unique job codes: {df['jobcode'].nunique()}")
    print()

    # =========================================================================
    # STEP 3: Latest snapshot summary
    # =========================================================================
    print("Latest Data Snapshot")
    print("-" * 50)

    latest_date = df['Date'].max()
    latest = df[df['Date'] == latest_date]

    print(f"As of: {latest_date:%B %Y}")
    print(f"Total employees: {len(latest):,}")
    print(f"Total FTE: {latest['full_time_equivalent'].sum():,.1f}")
    print()

    # Employee categories breakdown
    print("Employees by Category:")
    category_counts = latest.groupby('employee_category').size().sort_values(ascending=False)
    for cat, count in category_counts.items():
        print(f"  {cat}: {count:,}")
    print()

    # =========================================================================
    # STEP 4: Salary statistics
    # =========================================================================
    print("Salary Statistics (Latest Data)")
    print("-" * 50)

    salaries = latest['current_annual_contracted_salary']
    print(f"Median salary: ${salaries.median():,.0f}")
    print(f"Mean salary: ${salaries.mean():,.0f}")
    print(f"Min salary: ${salaries.min():,.0f}")
    print(f"Max salary: ${salaries.max():,.0f}")
    print()

    # Salary by employee category
    print("Median Salary by Category:")
    cat_salaries = latest.groupby('employee_category')['current_annual_contracted_salary'].median()
    cat_salaries = cat_salaries.sort_values(ascending=False)
    for cat, sal in cat_salaries.items():
        print(f"  {cat}: ${sal:,.0f}")
    print()

    # =========================================================================
    # STEP 5: Top divisions by headcount
    # =========================================================================
    print("Top 10 Divisions by Employee Count")
    print("-" * 50)

    div_counts = latest.groupby('division').size().sort_values(ascending=False).head(10)
    for div, count in div_counts.items():
        print(f"  {count:>5,}  {div}")
    print()

    # =========================================================================
    # STEP 6: Available columns
    # =========================================================================
    print("Available Data Columns")
    print("-" * 50)
    print(", ".join(sorted(df.columns)))


if __name__ == "__main__":
    main()
