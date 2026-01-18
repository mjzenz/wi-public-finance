"""
UW-Madison Employee Salary Profile and Comparison App
======================================================

A Streamlit web application for exploring UW-Madison employee salary data.
This app provides an interactive interface for searching employees, viewing
individual salary profiles, and comparing salaries across departments and titles.

Features:
---------
1. **Employee Search**: Find employees by name, division, or department
2. **Individual Profiles**: View detailed salary history with:
   - Nominal and real (inflation-adjusted) salary charts
   - Visual indication of title changes using color coding
   - Comparison to median salary for each job code
   - Salary growth calculations (within current division)
   - Peer comparisons with salary percentile rankings
3. **Department View**: Aggregate statistics for departments including:
   - Employee roster with growth metrics
   - Salary distribution charts
   - Summary statistics (median, mean, FTE totals)

Data Processing Notes:
----------------------
The app applies several filters to the raw data:
- Excludes appointments with salary < $1000 (typically courtesy or student roles)
- Keeps only primary appointment per person per date (highest FTE)
- If FTE is tied, keeps highest salary appointment

Chart Features:
---------------
- Uses colorblind-friendly Wong palette for accessibility
- Individual salary shown with solid lines, colored by job code
- Title median shown with dotted lines for comparison
- Legend positioned below charts to avoid overlap
- X-axis labeled "Year" for clarity

Running the App:
----------------
    # From command line
    streamlit run salary_app.py

    # Or with specific port
    streamlit run salary_app.py --server.port 8501

The app will open in your default web browser. Data loading may take
a few moments on first launch as the salary files are processed.

Dependencies:
-------------
- streamlit: Web application framework
- pandas: Data manipulation
- plotly: Interactive charts
- import_data: Data loading (this project)

Session State:
--------------
The app uses Streamlit session state to track:
- page: Current navigation page ('search', 'individual', 'department')
- selected_employee: ID of employee to view in individual profile

URL Parameters:
---------------
Navigation is managed through session state, not URL parameters.
Use the sidebar navigation to switch between pages.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import import_data


# Page config
st.set_page_config(
    page_title="UW-Madison Salary Explorer",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data
def load_data():
    """
    Load and cache the salary data with Streamlit caching.

    Uses Streamlit's cache_data decorator to avoid reloading data on every
    interaction. Data is only reloaded when the app restarts.

    Processing applied:
    1. Loads all salary files via import_data.clean_salary_data()
    2. Filters out appointments with salary < $1000
    3. Keeps only primary appointment per person per date (highest FTE)

    Returns
    -------
    pd.DataFrame
        Cleaned salary data ready for display and analysis.
    """
    filenames = import_data.read_salary_file_names()
    df = import_data.clean_salary_data(filenames)

    # Filter out near-zero salary appointments (less than $1000)
    df = df[df['current_annual_contracted_salary'] >= 1000].copy()

    # For each person-date combination, keep only the primary appointment (highest FTE)
    # If FTE is tied, keep the highest salary
    df = df.sort_values(['id', 'Date', 'full_time_equivalent', 'current_annual_contracted_salary'],
                        ascending=[True, True, False, False])
    df = df.drop_duplicates(subset=['id', 'Date'], keep='first')

    return df


def get_employee_department_history(df, employee_id):
    """
    Get an employee's department history to determine when they joined current department.

    Parameters
    ----------
    df : pd.DataFrame
        Full salary data with all employees.
    employee_id : str
        The 12-character employee ID to look up.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: Date, division, department, division_department
        showing the employee's organizational history over time.
    """
    emp_data = df[df['id'] == employee_id].sort_values('Date')
    return emp_data[['Date', 'division', 'department', 'division_department']].drop_duplicates()


def calculate_growth_in_division(df, employee_id, current_division):
    """
    Calculate salary growth only while in the current division.

    Returns (pct_growth, dollar_growth, first_salary, current_salary, first_date)
    """
    emp_data = df[df['id'] == employee_id].sort_values('Date')

    # Find when they joined the current division
    emp_in_div = emp_data[emp_data['division'] == current_division]

    if len(emp_in_div) < 1:
        return None, None, None, None, None

    first_record = emp_in_div.iloc[0]
    last_record = emp_in_div.iloc[-1]

    first_salary = first_record['current_annual_contracted_salary']
    current_salary = last_record['current_annual_contracted_salary']
    first_date = first_record['Date']

    if first_salary > 0:
        pct_growth = ((current_salary - first_salary) / first_salary) * 100
        dollar_growth = current_salary - first_salary
    else:
        pct_growth = None
        dollar_growth = None

    return pct_growth, dollar_growth, first_salary, current_salary, first_date


def calculate_peer_comparison(df, employee_id, jobcode, division, current_salary, growth_pct):
    """
    Calculate percentile ranks for salary and growth compared to peers.

    Returns dict with comparison stats for department, division-title, and university-title.
    """
    # Get current employee info
    emp_current = df[(df['id'] == employee_id) & (df['Date'] == df['Date'].max())].iloc[0]
    dept = emp_current['division_department']
    latest_date = df['Date'].max()

    # Get latest data for all employees
    latest_df = df[df['Date'] == latest_date]

    comparisons = {}

    # 1. Department comparison (all employees in same department)
    dept_peers = latest_df[latest_df['division_department'] == dept]
    if len(dept_peers) > 1:
        dept_salaries = dept_peers['current_annual_contracted_salary'].dropna()
        salary_percentile = (dept_salaries < current_salary).sum() / len(dept_salaries) * 100
        comparisons['department'] = {
            'name': dept,
            'peer_count': len(dept_peers),
            'salary_percentile': salary_percentile,
            'salary_median': dept_salaries.median(),
            'salary_mean': dept_salaries.mean(),
            'salaries': dept_salaries.tolist()
        }

    # 2. Division + Title comparison (same job code within division)
    div_title_peers = latest_df[(latest_df['division'] == division) & (latest_df['jobcode'] == jobcode)]
    if len(div_title_peers) > 1:
        div_salaries = div_title_peers['current_annual_contracted_salary'].dropna()
        salary_percentile = (div_salaries < current_salary).sum() / len(div_salaries) * 100
        comparisons['division_title'] = {
            'name': f"{jobcode} in {division}",
            'peer_count': len(div_title_peers),
            'salary_percentile': salary_percentile,
            'salary_median': div_salaries.median(),
            'salary_mean': div_salaries.mean(),
            'salaries': div_salaries.tolist()
        }

    # 3. University-wide title comparison (same job code across university)
    univ_title_peers = latest_df[latest_df['jobcode'] == jobcode]
    if len(univ_title_peers) > 1:
        univ_salaries = univ_title_peers['current_annual_contracted_salary'].dropna()
        salary_percentile = (univ_salaries < current_salary).sum() / len(univ_salaries) * 100
        comparisons['university_title'] = {
            'name': f"{jobcode} University-wide",
            'peer_count': len(univ_title_peers),
            'salary_percentile': salary_percentile,
            'salary_median': univ_salaries.median(),
            'salary_mean': univ_salaries.mean(),
            'salaries': univ_salaries.tolist()
        }

    return comparisons


def render_search_page(df):
    """Render the employee search page."""
    st.header("Employee Search")

    # Use only latest data for dropdowns
    latest_date = df['Date'].max()
    latest_df = df[df['Date'] == latest_date]

    col1, col2 = st.columns(2)

    with col1:
        first_name = st.text_input("First Name", key="search_first")
    with col2:
        last_name = st.text_input("Last Name", key="search_last")

    col3, col4 = st.columns(2)

    with col3:
        divisions = [''] + sorted(latest_df['division'].dropna().unique().tolist())
        division = st.selectbox("Division", divisions, key="search_division")
    with col4:
        if division:
            depts = [''] + sorted(latest_df[latest_df['division'] == division]['department'].dropna().unique().tolist())
        else:
            depts = [''] + sorted(latest_df['department'].dropna().unique().tolist())
        department = st.selectbox("Department", depts, key="search_department")

    # Filter based on search criteria
    results = latest_df.copy()

    if first_name:
        results = results[results['first_name'].str.lower().str.contains(first_name.lower(), na=False)]
    if last_name:
        results = results[results['last_name'].str.lower().str.contains(last_name.lower(), na=False)]
    if division:
        results = results[results['division'] == division]
    if department:
        results = results[results['department'] == department]

    # Show results
    if first_name or last_name or division or department:
        st.subheader(f"Results ({len(results)} found)")

        if len(results) > 0:
            # Create display dataframe
            display_df = results[['first_name', 'last_name', 'title', 'division',
                                  'department', 'current_annual_contracted_salary', 'id']].copy()
            display_df.columns = ['First Name', 'Last Name', 'Title', 'Division',
                                  'Department', 'Salary', 'ID']
            display_df['Salary'] = display_df['Salary'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "")

            # Show as clickable table
            for idx, row in display_df.iterrows():
                col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
                with col1:
                    st.write(f"**{row['First Name']} {row['Last Name']}**")
                with col2:
                    st.write(f"{row['Title']}")
                with col3:
                    st.write(f"{row['Salary']}")
                with col4:
                    if st.button("View", key=f"view_{row['ID']}_{idx}"):
                        st.session_state.selected_employee = row['ID']
                        st.session_state.page = 'individual'
                        st.rerun()
        else:
            st.info("No employees found matching your search criteria.")
    else:
        st.info("Enter search criteria above to find employees.")


def render_individual_page(df):
    """Render the individual employee profile page."""
    if 'selected_employee' not in st.session_state:
        st.warning("No employee selected. Please search for an employee first.")
        if st.button("Go to Search"):
            st.session_state.page = 'search'
            st.rerun()
        return

    employee_id = st.session_state.selected_employee
    emp_data = df[df['id'] == employee_id].sort_values('Date')

    if len(emp_data) == 0:
        st.error("Employee not found.")
        return

    # Get current (latest) record
    current = emp_data.iloc[-1]

    # Header with employee name
    st.header(f"{current['first_name']} {current['last_name']}")

    # Basic info section
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Current Salary", f"${current['current_annual_contracted_salary']:,.0f}")
        st.write(f"**Title:** {current['title']}")
        st.write(f"**Job Code:** {current['jobcode']}")

    with col2:
        st.write(f"**Division:** {current['division']}")
        st.write(f"**Department:** {current['department']}")
        st.write(f"**FTE:** {current['full_time_equivalent']:.2f}")

    with col3:
        hire_date = current.get('date_of_hire', None)
        if pd.notna(hire_date):
            st.write(f"**Hire Date:** {str(hire_date)[:10]}")

        job_group = current.get('job_group', current.get('jobgroup', 'N/A'))
        st.write(f"**Job Group:** {job_group if pd.notna(job_group) else 'N/A'}")

        supervisory = current.get('supervisory_required', None)
        if pd.notna(supervisory) and supervisory != '':
            st.write(f"**Supervisory:** {supervisory}")
        else:
            st.write("**Supervisory:** N/A")

    st.divider()

    # Salary History Charts
    st.subheader("Salary History")

    # Colorblind-friendly palette (Wong palette)
    COLORBLIND_PALETTE = [
        '#0072B2',  # blue
        '#E69F00',  # orange
        '#009E73',  # bluish green
        '#CC79A7',  # reddish purple
        '#D55E00',  # vermillion
        '#56B4E9',  # sky blue
        '#F0E442',  # yellow
    ]

    # Prepare chart data with title info
    chart_data = emp_data[['Date', 'current_annual_contracted_salary',
                           'FTE_Adjusted_Salary_2021_Dollars', 'title', 'jobcode']].copy()
    chart_data = chart_data.sort_values('Date')

    # Get unique jobcodes and assign colors (use jobcode for change detection, not title description)
    unique_jobcodes = chart_data['jobcode'].unique()
    jobcode_colors = {jc: COLORBLIND_PALETTE[i % len(COLORBLIND_PALETTE)]
                      for i, jc in enumerate(unique_jobcodes)}

    # Create display labels for legend (title description with jobcode)
    jobcode_labels = {}
    for jc in unique_jobcodes:
        title_desc = chart_data[chart_data['jobcode'] == jc]['title'].iloc[0]
        jobcode_labels[jc] = f"{title_desc} ({jc})"

    # Calculate median salaries by date for each job code the employee held
    chart_data['Median Nominal'] = None
    chart_data['Median Real'] = None
    for idx, row in chart_data.iterrows():
        jc = row['jobcode']
        dt = row['Date']
        jc_data = df[(df['jobcode'] == jc) & (df['Date'] == dt)]
        if len(jc_data) > 0:
            chart_data.loc[idx, 'Median Nominal'] = jc_data['current_annual_contracted_salary'].median()
            chart_data.loc[idx, 'Median Real'] = jc_data['FTE_Adjusted_Salary_2021_Dollars'].median()

    # Create side-by-side charts
    col1, col2 = st.columns(2)

    with col1:
        fig_nominal = go.Figure()

        # Add salary line segments colored by jobcode (individual salaries first for legend ordering)
        added_jobcodes = set()
        for i in range(len(chart_data)):
            row = chart_data.iloc[i]
            jc = row['jobcode']
            color = jobcode_colors[jc]
            show_legend = jc not in added_jobcodes
            added_jobcodes.add(jc)

            # Add marker for this point
            fig_nominal.add_trace(go.Scatter(
                x=[row['Date']], y=[row['current_annual_contracted_salary']],
                mode='markers',
                name=jobcode_labels[jc] if show_legend else None,
                marker=dict(color=color, size=10),
                legendgroup=jc,
                showlegend=show_legend,
                legendrank=1  # Salaries appear first (left side)
            ))

            # Add line segment to next point
            if i < len(chart_data) - 1:
                next_row = chart_data.iloc[i + 1]
                fig_nominal.add_trace(go.Scatter(
                    x=[row['Date'], next_row['Date']],
                    y=[row['current_annual_contracted_salary'], next_row['current_annual_contracted_salary']],
                    mode='lines',
                    line=dict(color=color, width=2),
                    legendgroup=jc,
                    showlegend=False
                ))

        # Add median line segments (dotted, colored by jobcode) - medians second for legend ordering
        added_median_jc = set()
        for i in range(len(chart_data)):
            row = chart_data.iloc[i]
            jc = row['jobcode']
            color = jobcode_colors[jc]
            show_legend = f"median_{jc}" not in added_median_jc
            added_median_jc.add(f"median_{jc}")

            if pd.notna(row['Median Nominal']):
                # Add median marker
                fig_nominal.add_trace(go.Scatter(
                    x=[row['Date']], y=[row['Median Nominal']],
                    mode='markers',
                    name=f"Median ({jc})" if show_legend else None,
                    marker=dict(color=color, size=6, symbol='diamond-open'),
                    legendgroup=f"median_{jc}",
                    showlegend=show_legend,
                    legendrank=2  # Medians appear second (right side)
                ))

                # Add dotted line segment to next point
                if i < len(chart_data) - 1:
                    next_row = chart_data.iloc[i + 1]
                    if pd.notna(next_row['Median Nominal']):
                        fig_nominal.add_trace(go.Scatter(
                            x=[row['Date'], next_row['Date']],
                            y=[row['Median Nominal'], next_row['Median Nominal']],
                            mode='lines',
                            line=dict(color=color, width=2, dash='dot'),
                            legendgroup=f"median_{jc}",
                            showlegend=False
                        ))

        fig_nominal.update_layout(
            title='Nominal Salary Over Time',
            yaxis_tickformat='$,.0f',
            xaxis_title='Year',
            legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5, font=dict(size=10)),
            margin=dict(b=120)
        )
        st.plotly_chart(fig_nominal, use_container_width=True)

    with col2:
        fig_real = go.Figure()

        # Add salary line segments colored by jobcode (individual salaries first for legend ordering)
        added_jobcodes = set()
        for i in range(len(chart_data)):
            row = chart_data.iloc[i]
            jc = row['jobcode']
            color = jobcode_colors[jc]
            show_legend = jc not in added_jobcodes
            added_jobcodes.add(jc)

            # Add marker for this point
            fig_real.add_trace(go.Scatter(
                x=[row['Date']], y=[row['FTE_Adjusted_Salary_2021_Dollars']],
                mode='markers',
                name=jobcode_labels[jc] if show_legend else None,
                marker=dict(color=color, size=10),
                legendgroup=jc,
                showlegend=show_legend,
                legendrank=1  # Salaries appear first (left side)
            ))

            # Add line segment to next point
            if i < len(chart_data) - 1:
                next_row = chart_data.iloc[i + 1]
                fig_real.add_trace(go.Scatter(
                    x=[row['Date'], next_row['Date']],
                    y=[row['FTE_Adjusted_Salary_2021_Dollars'], next_row['FTE_Adjusted_Salary_2021_Dollars']],
                    mode='lines',
                    line=dict(color=color, width=2),
                    legendgroup=jc,
                    showlegend=False
                ))

        # Add median line segments (dotted, colored by jobcode) - medians second for legend ordering
        added_median_jc = set()
        for i in range(len(chart_data)):
            row = chart_data.iloc[i]
            jc = row['jobcode']
            color = jobcode_colors[jc]
            show_legend = f"median_{jc}" not in added_median_jc
            added_median_jc.add(f"median_{jc}")

            if pd.notna(row['Median Real']):
                # Add median marker
                fig_real.add_trace(go.Scatter(
                    x=[row['Date']], y=[row['Median Real']],
                    mode='markers',
                    name=f"Median ({jc})" if show_legend else None,
                    marker=dict(color=color, size=6, symbol='diamond-open'),
                    legendgroup=f"median_{jc}",
                    showlegend=show_legend,
                    legendrank=2  # Medians appear second (right side)
                ))

                # Add dotted line segment to next point
                if i < len(chart_data) - 1:
                    next_row = chart_data.iloc[i + 1]
                    if pd.notna(next_row['Median Real']):
                        fig_real.add_trace(go.Scatter(
                            x=[row['Date'], next_row['Date']],
                            y=[row['Median Real'], next_row['Median Real']],
                            mode='lines',
                            line=dict(color=color, width=2, dash='dot'),
                            legendgroup=f"median_{jc}",
                            showlegend=False
                        ))

        fig_real.update_layout(
            title='Real Salary (2021 Dollars)',
            yaxis_tickformat='$,.0f',
            xaxis_title='Year',
            legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5, font=dict(size=10)),
            margin=dict(b=120)
        )
        st.plotly_chart(fig_real, use_container_width=True)

    # Calculate overall salary changes (first to current, all positions)
    first_nominal = chart_data.iloc[0]['current_annual_contracted_salary']
    current_nominal = chart_data.iloc[-1]['current_annual_contracted_salary']
    first_real = chart_data.iloc[0]['FTE_Adjusted_Salary_2021_Dollars']
    current_real = chart_data.iloc[-1]['FTE_Adjusted_Salary_2021_Dollars']

    if first_nominal > 0:
        pct_nominal_change = ((current_nominal - first_nominal) / first_nominal) * 100
    else:
        pct_nominal_change = None

    if first_real > 0:
        pct_real_change = ((current_real - first_real) / first_real) * 100
    else:
        pct_real_change = None

    # Display overall salary changes
    st.markdown("**Overall Salary Change (All Positions)**")
    col1, col2 = st.columns(2)
    with col1:
        if pct_nominal_change is not None:
            st.metric("Nominal Salary Change", f"{pct_nominal_change:+.1f}%",
                      f"${current_nominal - first_nominal:+,.0f}")
    with col2:
        if pct_real_change is not None:
            st.metric("Real Salary Change (2021 $)", f"{pct_real_change:+.1f}%",
                      f"${current_real - first_real:+,.0f}")

    st.divider()

    # Salary Growth in Current Division
    st.subheader("Salary Growth")

    current_division = current['division']
    pct_growth, dollar_growth, first_salary, curr_salary, first_date = calculate_growth_in_division(
        df, employee_id, current_division
    )

    if pct_growth is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Growth in Division", f"{pct_growth:+.1f}%", f"${dollar_growth:+,.0f}")
        with col2:
            st.metric("Starting Salary", f"${first_salary:,.0f}", f"as of {first_date.strftime('%Y-%m')}")
        with col3:
            st.metric("Current Salary", f"${curr_salary:,.0f}")
    else:
        st.info("Insufficient data to calculate salary growth.")

    st.divider()

    # Peer Comparisons
    st.subheader("Peer Comparisons")

    comparisons = calculate_peer_comparison(
        df, employee_id, current['jobcode'], current['division'],
        current['current_annual_contracted_salary'], pct_growth
    )

    if comparisons:
        tabs = st.tabs(list(comparisons.keys()))

        for tab, (comp_type, comp_data) in zip(tabs, comparisons.items()):
            with tab:
                col1, col2 = st.columns([1, 2])

                with col1:
                    st.write(f"**Comparing to:** {comp_data['name']}")
                    st.write(f"**Peer Count:** {comp_data['peer_count']}")
                    st.metric(
                        "Salary Percentile",
                        f"{comp_data['salary_percentile']:.0f}th",
                        help="Percentage of peers earning less than you"
                    )
                    st.write(f"**Peer Median:** ${comp_data['salary_median']:,.0f}")
                    st.write(f"**Peer Mean:** ${comp_data['salary_mean']:,.0f}")

                with col2:
                    # Distribution chart
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=comp_data['salaries'],
                        nbinsx=20,
                        name='Peer Salaries',
                        marker_color='lightblue'
                    ))
                    fig.add_vline(
                        x=current['current_annual_contracted_salary'],
                        line_dash="dash",
                        line_color="red",
                        annotation_text="You",
                        annotation_position="top"
                    )
                    fig.update_layout(
                        title=f"Salary Distribution: {comp_data['name']}",
                        xaxis_title="Salary",
                        yaxis_title="Count",
                        xaxis_tickformat='$,.0f',
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No peer comparison data available.")

    # Back button
    st.divider()
    if st.button("← Back to Search"):
        st.session_state.page = 'search'
        st.rerun()


def render_department_page(df):
    """Render the department/division view page."""
    st.header("Department View")

    # Use only latest data for dropdowns to avoid showing historical divisions/departments
    latest_date = df['Date'].max()
    latest_df = df[df['Date'] == latest_date]

    # Division/Department selection
    col1, col2 = st.columns(2)

    with col1:
        divisions = sorted(latest_df['division'].dropna().unique().tolist())
        division = st.selectbox("Select Division", divisions, key="dept_division")

    with col2:
        if division:
            depts = sorted(latest_df[latest_df['division'] == division]['department'].dropna().unique().tolist())
            department = st.selectbox("Select Department", depts, key="dept_department")
        else:
            department = None

    if division and department:
        # Get latest data for this department
        dept_df = latest_df[(latest_df['division'] == division) &
                            (latest_df['department'] == department)].copy()

        st.subheader(f"{department} ({len(dept_df)} employees)")

        # Calculate growth for each employee (by division)
        if len(dept_df) > 0:
            growth_data = []
            for _, row in dept_df.iterrows():
                emp_id = row['id']
                current_division = row['division']
                pct_growth, dollar_growth, _, _, first_date = calculate_growth_in_division(
                    df, emp_id, current_division
                )
                growth_data.append({
                    'id': emp_id,
                    'pct_growth': pct_growth,
                    'dollar_growth': dollar_growth,
                    'first_date': first_date
                })

            growth_df = pd.DataFrame(growth_data)
            if len(growth_df) > 0 and 'id' in growth_df.columns:
                dept_df = dept_df.merge(growth_df, on='id', how='left')
            else:
                dept_df['pct_growth'] = None
                dept_df['dollar_growth'] = None
        else:
            st.info("No employees found in this department.")
            return

        # Prepare display columns
        display_cols = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'title': 'Title',
            'job_group': 'Job Group',
            'current_annual_contracted_salary': 'Current Salary',
            'pct_growth': 'Growth %',
            'dollar_growth': 'Growth $',
            'full_time_equivalent': 'FTE',
            'supervisory_required': 'Supervisory',
            'date_of_hire': 'Hire Date',
            'id': 'ID'
        }

        # Select and rename columns that exist
        available_cols = [c for c in display_cols.keys() if c in dept_df.columns]
        display_df = dept_df[available_cols].copy()
        display_df = display_df.rename(columns={c: display_cols[c] for c in available_cols})

        # Format columns
        if 'Current Salary' in display_df.columns:
            display_df['Current Salary'] = display_df['Current Salary'].apply(
                lambda x: f"${x:,.0f}" if pd.notna(x) else ""
            )
        if 'Growth %' in display_df.columns:
            display_df['Growth %'] = display_df['Growth %'].apply(
                lambda x: f"{x:+.1f}%" if pd.notna(x) else ""
            )
        if 'Growth $' in display_df.columns:
            display_df['Growth $'] = display_df['Growth $'].apply(
                lambda x: f"${x:+,.0f}" if pd.notna(x) else ""
            )
        if 'FTE' in display_df.columns:
            display_df['FTE'] = display_df['FTE'].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else ""
            )
        if 'Supervisory' in display_df.columns:
            display_df['Supervisory'] = display_df['Supervisory'].apply(
                lambda x: x if pd.notna(x) and x != '' else ""
            )
        if 'Hire Date' in display_df.columns:
            display_df['Hire Date'] = display_df['Hire Date'].apply(
                lambda x: str(x)[:10] if pd.notna(x) else ""
            )

        # Remove ID column from display but keep for click handling
        if 'ID' in display_df.columns:
            ids = display_df['ID'].tolist()
            display_df = display_df.drop(columns=['ID'])
        else:
            ids = None

        # Display as interactive dataframe
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # Summary statistics
        st.divider()
        st.subheader("Department Summary")

        col1, col2, col3, col4 = st.columns(4)

        salaries = dept_df['current_annual_contracted_salary'].dropna()
        with col1:
            st.metric("Median Salary", f"${salaries.median():,.0f}")
        with col2:
            st.metric("Mean Salary", f"${salaries.mean():,.0f}")
        with col3:
            st.metric("Total Employees", len(dept_df))
        with col4:
            total_fte = dept_df['full_time_equivalent'].sum()
            st.metric("Total FTE", f"{total_fte:.1f}")

        # Salary distribution chart
        fig = px.histogram(
            dept_df, x='current_annual_contracted_salary',
            nbins=20,
            title=f"Salary Distribution: {department}"
        )
        fig.update_layout(
            xaxis_title="Salary",
            yaxis_title="Count",
            xaxis_tickformat='$,.0f'
        )
        st.plotly_chart(fig, use_container_width=True)


def main():
    """Main application entry point."""
    # Load data
    with st.spinner("Loading salary data..."):
        df = load_data()

    # Sidebar navigation
    st.sidebar.title("UW-Madison Salary Explorer")
    st.sidebar.divider()

    # Navigation
    if 'page' not in st.session_state:
        st.session_state.page = 'search'

    page = st.sidebar.radio(
        "Navigate",
        ['Search', 'Individual Profile', 'Department View'],
        index=['search', 'individual', 'department'].index(st.session_state.page)
        if st.session_state.page in ['search', 'individual', 'department'] else 0
    )

    # Update page state
    page_map = {
        'Search': 'search',
        'Individual Profile': 'individual',
        'Department View': 'department'
    }
    st.session_state.page = page_map[page]

    # Render appropriate page
    if st.session_state.page == 'search':
        render_search_page(df)
    elif st.session_state.page == 'individual':
        render_individual_page(df)
    elif st.session_state.page == 'department':
        render_department_page(df)

    # Footer
    st.sidebar.divider()
    st.sidebar.caption(f"Data as of: {df['Date'].max().strftime('%B %Y')}")
    st.sidebar.caption(f"Total records: {len(df):,}")


if __name__ == "__main__":
    main()
