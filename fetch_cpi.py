"""
Fetch CPI data from FRED API and save to CSV.

Run this script periodically to update CPI data, or when you need
fresh inflation adjustment data. The main data pipeline will read
from the cached CSV file.

Usage:
    python fetch_cpi.py
"""
import pandas as pd
import config


def fetch_and_save_cpi(api_key=None, output_path=None):
    """
    Fetch CPI data from FRED and save to CSV.

    Parameters
    ----------
    api_key : str, optional
        FRED API key. If not provided, reads from keyring.
    output_path : str, optional
        Path to save CSV. Defaults to config.CPI_CACHE_FILE.

    Returns
    -------
    pd.DataFrame
        CPI data with Date and CPI columns.
    """
    import keyring
    from fredapi import Fred

    if api_key is None:
        api_key = keyring.get_password("fredapi", "fredapi")

    if output_path is None:
        output_path = config.CPI_CACHE_FILE

    print(f"Fetching CPI data (series: {config.CPI_SERIES_ID})...")
    fred = Fred(api_key=api_key)
    cpi_series = fred.get_series(config.CPI_SERIES_ID)

    cpi_data = cpi_series.reset_index()
    cpi_data.columns = ['Date', 'CPI']

    # Calculate the 2021 index factor for each date
    cpi_base = cpi_data.loc[cpi_data['Date'] == config.CPI_BASE_DATE, 'CPI']
    if len(cpi_base) > 0:
        cpi_base_value = cpi_base.iloc[0]
        cpi_data['CPI_2021_Index'] = cpi_base_value / cpi_data['CPI']
        print(f"Base CPI ({config.CPI_BASE_DATE}): {cpi_base_value:.2f}")
    else:
        print(f"Warning: Base date {config.CPI_BASE_DATE} not found in CPI data")
        cpi_data['CPI_2021_Index'] = None

    # Save to CSV
    cpi_data.to_csv(output_path, index=False)
    print(f"Saved {len(cpi_data)} CPI records to {output_path}")
    print(f"Date range: {cpi_data['Date'].min()} to {cpi_data['Date'].max()}")

    return cpi_data


def load_cpi_data(path=None):
    """
    Load CPI data from cached CSV file.

    Parameters
    ----------
    path : str, optional
        Path to CPI CSV. Defaults to config.CPI_CACHE_FILE.

    Returns
    -------
    pd.DataFrame
        CPI data with Date, CPI, and CPI_2021_Index columns.

    Raises
    ------
    FileNotFoundError
        If CPI cache file doesn't exist. Run fetch_cpi.py first.
    """
    if path is None:
        path = config.CPI_CACHE_FILE

    try:
        cpi_data = pd.read_csv(path, parse_dates=['Date'])
        return cpi_data
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CPI cache file not found at {path}. "
            "Run 'python fetch_cpi.py' to fetch CPI data first."
        )


if __name__ == '__main__':
    fetch_and_save_cpi()
