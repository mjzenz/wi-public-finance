"""
Build cleaned salary data for the Streamlit app.

Run this script after adding new salary Excel files to data/.
It processes all files through the pipeline and saves a single
parquet file that the app loads on startup.

Usage:
    python build_data.py
"""
import os
import sys
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from import_data import read_salary_file_names, clean_salary_data
import config

OUTPUT_PATH = os.path.join(config.DATA_DIR, 'salary_clean.parquet')


def build():
    print("Loading and cleaning salary data...")
    start = time.time()

    filenames = read_salary_file_names()
    print(f"  Found {len(filenames)} salary files")

    df = clean_salary_data(filenames)

    # Filter out near-zero salary appointments (courtesy/student roles)
    df = df[df['current_annual_contracted_salary'] >= 1000].copy()

    # Coerce mixed-type columns to string for parquet compatibility
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).replace('nan', pd.NA)

    df.to_parquet(OUTPUT_PATH, index=False)

    elapsed = time.time() - start
    print(f"\nSaved {len(df):,} rows to {OUTPUT_PATH}")
    print(f"  Unique employees: {df['id'].nunique():,}")
    print(f"  Date range: {df['Date'].min():%Y-%m} to {df['Date'].max():%Y-%m}")
    print(f"  File size: {os.path.getsize(OUTPUT_PATH) / 1024 / 1024:.1f} MB")
    print(f"  Build time: {elapsed:.1f}s")


if __name__ == '__main__':
    build()
