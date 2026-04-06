"""
UW-Madison Employee Salary Profile and Comparison App
======================================================

A Streamlit web application for exploring UW-Madison employee salary data.

Features:
---------
1. **Employee Search**: Find current and former employees by name, division, or department
2. **Individual Profiles**: Salary history with inflation-adjusted charts,
   title change visualization, peer comparisons
3. **Department View**: Aggregate statistics, clickable employee roster,
   salary distribution charts

Running the App:
----------------
    streamlit run salary_app.py
"""
import os
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

# Colorblind-friendly palette (Wong palette)
WONG = [
    '#0072B2',  # blue
    '#E69F00',  # orange
    '#009E73',  # bluish green
    '#CC79A7',  # reddish purple
    '#D55E00',  # vermillion
    '#56B4E9',  # sky blue
    '#F0E442',  # yellow
]

MAX_SEARCH_RESULTS = 200


PARQUET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'salary_clean.parquet')


@st.cache_data
def load_data():
    """
    Load cleaned salary data from pre-built parquet file.

    The parquet file is created by running: python build_data.py
    This should be run whenever new salary Excel files are added.
    """
    if os.path.exists(PARQUET_PATH):
        df = pd.read_parquet(PARQUET_PATH)
        return df

    # Fallback: build from Excel files if parquet doesn't exist
    st.warning("Pre-built data not found. Loading from Excel files (this will be slow). "
               "Run `python build_data.py` to pre-build the data.")
    filenames = import_data.read_salary_file_names()
    df = import_data.clean_salary_data(filenames)
    df = df[df['current_annual_contracted_salary'] >= 1000].copy()
    return df


@st.cache_data
def build_employee_index(_df):
    """
    Build a lookup of each employee's most recent record for search.

    Includes departed employees so they can be found.
    Returns one row per employee (their latest primary appointment).
    """
    # For each employee, take their latest record (highest salary if multiple on same date)
    idx = (
        _df.sort_values(['Date', 'current_annual_contracted_salary'], ascending=[True, False])
        .drop_duplicates('id', keep='last')
    )
    latest_date = _df['Date'].max()
    idx['is_current'] = idx['Date'] == latest_date
    idx['last_seen'] = idx['Date']
    return idx


def get_primary_per_date(df, employee_id):
    """Get one row per date for an employee (highest salary appointment)."""
    emp = df[df['id'] == employee_id].copy()
    emp = emp.sort_values('current_annual_contracted_salary', ascending=False)
    emp = emp.drop_duplicates('Date', keep='first')
    return emp.sort_values('Date')


def calculate_growth_in_division(emp_data, current_division):
    """
    Calculate salary growth while in the current division.

    Parameters
    ----------
    emp_data : pd.DataFrame
        Pre-filtered, sorted data for one employee.
    current_division : str
        Division to calculate growth within.

    Returns
    -------
    tuple: (pct_growth, dollar_growth, first_salary, current_salary, first_date)
    """
    emp_in_div = emp_data[emp_data['division'] == current_division]

    if len(emp_in_div) < 1:
        return None, None, None, None, None

    first_salary = emp_in_div.iloc[0]['current_annual_contracted_salary']
    current_salary = emp_in_div.iloc[-1]['current_annual_contracted_salary']
    first_date = emp_in_div.iloc[0]['Date']

    if first_salary > 0:
        pct_growth = ((current_salary - first_salary) / first_salary) * 100
        dollar_growth = current_salary - first_salary
    else:
        pct_growth = None
        dollar_growth = None

    return pct_growth, dollar_growth, first_salary, current_salary, first_date


def calculate_peer_comparison(df, employee_id, jobcode, division, current_salary):
    """
    Calculate percentile ranks for salary compared to peers.

    Uses the employee's last available date for comparison, not the dataset's
    latest date. This makes comparisons meaningful for departed employees.

    Returns
    -------
    tuple: (comparisons_dict, comparison_date)
    """
    emp_records = df[df['id'] == employee_id].sort_values('Date')
    if len(emp_records) == 0:
        return {}, None

    emp_current = emp_records.iloc[-1]
    emp_last_date = emp_current['Date']
    dept = emp_current['division_department']

    # Compare against peers from the same date
    peers_df = df[df['Date'] == emp_last_date]

    def build_peer_data(peer_rows, label):
        """Build comparison dict for a set of peers, including seniority data."""
        if len(peer_rows) <= 1:
            return None
        salaries = peer_rows['current_annual_contracted_salary'].dropna()
        salary_percentile = (salaries < current_salary).sum() / len(salaries) * 100

        # Calculate years on staff for scatter plot
        peer_seniority = peer_rows[['current_annual_contracted_salary', 'date_of_hire']].copy()
        peer_seniority['date_of_hire'] = pd.to_datetime(peer_seniority['date_of_hire'], errors='coerce')
        peer_seniority['years_on_staff'] = (emp_last_date - peer_seniority['date_of_hire']).dt.days / 365.25
        peer_seniority = peer_seniority.dropna(subset=['years_on_staff', 'current_annual_contracted_salary'])
        peer_seniority = peer_seniority[peer_seniority['years_on_staff'] >= 0]

        return {
            'name': label,
            'peer_count': len(peer_rows),
            'salary_percentile': salary_percentile,
            'salary_median': salaries.median(),
            'salary_mean': salaries.mean(),
            'salaries': salaries.tolist(),
            'seniority_salaries': peer_seniority['current_annual_contracted_salary'].tolist(),
            'seniority_years': peer_seniority['years_on_staff'].tolist(),
        }

    comparisons = {}

    dept_data = build_peer_data(peers_df[peers_df['division_department'] == dept], dept)
    if dept_data:
        comparisons['department'] = dept_data

    div_title_peers = peers_df[(peers_df['division'] == division) & (peers_df['jobcode'] == jobcode)]
    div_data = build_peer_data(div_title_peers, f"{jobcode} in {division}")
    if div_data:
        comparisons['division_title'] = div_data

    univ_title_peers = peers_df[peers_df['jobcode'] == jobcode]
    univ_data = build_peer_data(univ_title_peers, f"{jobcode} University-wide")
    if univ_data:
        comparisons['university_title'] = univ_data

    return comparisons, emp_last_date


def build_salary_chart(chart_data, y_col, title, jobcode_colors, jobcode_labels, median_col):
    """Build a salary chart with individual + median lines, colored by jobcode."""
    fig = go.Figure()

    added_jc = set()
    for i in range(len(chart_data)):
        row = chart_data.iloc[i]
        jc = row['jobcode']
        color = jobcode_colors[jc]
        show_legend = jc not in added_jc
        added_jc.add(jc)

        fig.add_trace(go.Scatter(
            x=[row['Date']], y=[row[y_col]],
            mode='markers',
            name=jobcode_labels[jc] if show_legend else None,
            marker=dict(color=color, size=10),
            legendgroup=jc,
            showlegend=show_legend,
            legendrank=1
        ))

        if i < len(chart_data) - 1:
            nxt = chart_data.iloc[i + 1]
            fig.add_trace(go.Scatter(
                x=[row['Date'], nxt['Date']],
                y=[row[y_col], nxt[y_col]],
                mode='lines', line=dict(color=color, width=2),
                legendgroup=jc, showlegend=False
            ))

    # Median lines
    added_med = set()
    for i in range(len(chart_data)):
        row = chart_data.iloc[i]
        jc = row['jobcode']
        color = jobcode_colors[jc]
        show_legend = f"med_{jc}" not in added_med
        added_med.add(f"med_{jc}")

        if pd.notna(row[median_col]):
            fig.add_trace(go.Scatter(
                x=[row['Date']], y=[row[median_col]],
                mode='markers',
                name=f"Median ({jc})" if show_legend else None,
                marker=dict(color=color, size=6, symbol='diamond-open'),
                legendgroup=f"med_{jc}",
                showlegend=show_legend,
                legendrank=2
            ))
            if i < len(chart_data) - 1:
                nxt = chart_data.iloc[i + 1]
                if pd.notna(nxt[median_col]):
                    fig.add_trace(go.Scatter(
                        x=[row['Date'], nxt['Date']],
                        y=[row[median_col], nxt[median_col]],
                        mode='lines', line=dict(color=color, width=2, dash='dot'),
                        legendgroup=f"med_{jc}", showlegend=False
                    ))

    fig.update_layout(
        title=title,
        yaxis_tickformat='$,.0f',
        xaxis_title='Year',
        legend=dict(orientation="h", yanchor="top", y=-0.22,
                    xanchor="center", x=0.5, font=dict(size=10)),
        margin=dict(b=120)
    )
    return fig


def render_search_page(df, emp_index):
    """Render the employee search page."""
    st.header("Employee Search")

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
            depts = [''] + sorted(
                latest_df[latest_df['division'] == division]['department']
                .dropna().unique().tolist()
            )
        else:
            depts = [''] + sorted(latest_df['department'].dropna().unique().tolist())
        department = st.selectbox("Department", depts, key="search_department")

    # Search against ALL employees (current + departed)
    results = emp_index.copy()

    if first_name:
        results = results[results['first_name'].str.lower().str.contains(
            first_name.lower(), na=False)]
    if last_name:
        results = results[results['last_name'].str.lower().str.contains(
            last_name.lower(), na=False)]
    if division:
        results = results[results['division'] == division]
    if department:
        results = results[results['department'] == department]

    if first_name or last_name or division or department:
        total = len(results)
        results = results.sort_values('current_annual_contracted_salary', ascending=False)

        if total > MAX_SEARCH_RESULTS:
            st.warning(f"Showing first {MAX_SEARCH_RESULTS} of {total} results. "
                       "Narrow your search to see more specific results.")
            results = results.head(MAX_SEARCH_RESULTS)

        st.subheader(f"Results ({total} found)")

        if len(results) > 0:
            display_df = results[[
                'first_name', 'last_name', 'title', 'division', 'department',
                'current_annual_contracted_salary', 'is_current', 'last_seen', 'id'
            ]].copy().reset_index(drop=True)
            display_df['Salary'] = display_df['current_annual_contracted_salary'].apply(
                lambda x: f"${x:,.0f}" if pd.notna(x) else "")
            display_df['Status'] = display_df.apply(
                lambda r: "Current" if r['is_current']
                else f"Last seen {r['last_seen'].strftime('%Y-%m')}", axis=1)

            show_df = pd.DataFrame({
                'First Name': display_df['first_name'].values,
                'Last Name': display_df['last_name'].values,
                'Title': display_df['title'].values,
                'Division': display_df['division'].values,
                'Salary': display_df['Salary'].values,
                'Status': display_df['Status'].values,
            })

            st.caption("Click a row to select, then press View Profile.")
            event = st.dataframe(
                show_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="search_table",
            )

            selected_rows = event.selection.rows if event.selection else []
            if selected_rows:
                sel_idx = selected_rows[0]
                sel_name = f"{display_df.iloc[sel_idx]['first_name']} {display_df.iloc[sel_idx]['last_name']}"
                if st.button(f"View Profile: {sel_name}", key="search_view_btn"):
                    st.session_state.selected_employee = display_df.iloc[sel_idx]['id']
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
    emp_data = get_primary_per_date(df, employee_id)

    if len(emp_data) == 0:
        st.error("Employee not found.")
        return

    current = emp_data.iloc[-1]
    latest_date = df['Date'].max()
    is_departed = current['Date'] < latest_date

    # Header
    name = f"{current['first_name']} {current['last_name']}"
    if is_departed:
        st.header(f"{name}")
        st.caption(f"Last seen in {current['Date'].strftime('%B %Y')} data")
    else:
        st.header(name)

    # Basic info
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
            hire_dt = pd.to_datetime(hire_date)
            ref_date = current['Date']
            years_on_staff = (ref_date - hire_dt).days / 365.25
            st.write(f"**Hire Date:** {str(hire_date)[:10]}")
            if years_on_staff >= 0:
                st.write(f"**Years on Staff:** {years_on_staff:.1f}")
        else:
            years_on_staff = None
            st.write("**Hire Date:** N/A")

        job_group = current.get('job_group', current.get('jobgroup', None))
        st.write(f"**Job Group:** {job_group if pd.notna(job_group) else 'N/A'}")

        supervisory = current.get('supervisory_required', None)
        st.write(f"**Supervisory:** {supervisory if pd.notna(supervisory) and supervisory != '' else 'N/A'}")

    # Check for split appointments at latest date
    all_appts = df[(df['id'] == employee_id) & (df['Date'] == current['Date'])]
    if len(all_appts) > 1:
        st.info(f"This employee has {len(all_appts)} concurrent appointments "
                f"(total FTE: {all_appts['full_time_equivalent'].sum():.2f}). "
                f"Showing primary appointment (highest salary).")

    st.divider()

    # Salary History Charts
    st.subheader("Salary History")

    chart_data = emp_data[['Date', 'current_annual_contracted_salary',
                           'Real_Salary_2021_Dollars', 'title', 'jobcode']].copy()

    unique_jobcodes = chart_data['jobcode'].unique()
    jobcode_colors = {jc: WONG[i % len(WONG)] for i, jc in enumerate(unique_jobcodes)}
    jobcode_labels = {}
    for jc in unique_jobcodes:
        title_desc = chart_data[chart_data['jobcode'] == jc]['title'].iloc[0]
        jobcode_labels[jc] = f"{title_desc} ({jc})"

    # Compute medians via merge instead of row-by-row loop
    medians = (
        df.groupby(['Date', 'jobcode'])
        .agg(
            Median_Nominal=('current_annual_contracted_salary', 'median'),
            Median_Real=('Real_Salary_2021_Dollars', 'median'),
        )
        .reset_index()
    )
    chart_data = chart_data.merge(medians, on=['Date', 'jobcode'], how='left')

    col1, col2 = st.columns(2)
    with col1:
        fig_nom = build_salary_chart(
            chart_data, 'current_annual_contracted_salary',
            'Nominal Salary Over Time',
            jobcode_colors, jobcode_labels, 'Median_Nominal')
        st.plotly_chart(fig_nom, use_container_width=True)

    with col2:
        fig_real = build_salary_chart(
            chart_data, 'Real_Salary_2021_Dollars',
            'Real Salary (2021 Dollars)',
            jobcode_colors, jobcode_labels, 'Median_Real')
        st.plotly_chart(fig_real, use_container_width=True)

    # Overall salary changes
    first_nominal = chart_data.iloc[0]['current_annual_contracted_salary']
    current_nominal = chart_data.iloc[-1]['current_annual_contracted_salary']
    first_real = chart_data.iloc[0]['Real_Salary_2021_Dollars']
    current_real = chart_data.iloc[-1]['Real_Salary_2021_Dollars']

    st.markdown("**Overall Salary Change (All Positions)**")
    col1, col2 = st.columns(2)
    with col1:
        if pd.notna(first_nominal) and first_nominal > 0:
            pct = ((current_nominal - first_nominal) / first_nominal) * 100
            st.metric("Nominal Salary Change", f"{pct:+.1f}%",
                      f"${current_nominal - first_nominal:+,.0f}")
    with col2:
        if pd.notna(first_real) and first_real > 0:
            pct = ((current_real - first_real) / first_real) * 100
            st.metric("Real Salary Change (2021 $)", f"{pct:+.1f}%",
                      f"${current_real - first_real:+,.0f}")

    st.divider()

    # Salary Growth in Current Division
    st.subheader("Salary Growth")

    current_division = current['division']
    pct_growth, dollar_growth, first_salary, curr_salary, first_date = \
        calculate_growth_in_division(emp_data, current_division)

    if pct_growth is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Growth in Division", f"{pct_growth:+.1f}%",
                      f"${dollar_growth:+,.0f}")
        with col2:
            st.metric("Starting Salary", f"${first_salary:,.0f}",
                      f"as of {first_date.strftime('%Y-%m')}")
        with col3:
            st.metric("Current Salary", f"${curr_salary:,.0f}")
    else:
        st.info("Insufficient data to calculate salary growth.")

    st.divider()

    # Peer Comparisons
    st.subheader("Peer Comparisons")

    comparisons, comp_date = calculate_peer_comparison(
        df, employee_id, current['jobcode'], current['division'],
        current['current_annual_contracted_salary']
    )

    if comp_date is not None and comp_date < latest_date:
        st.caption(f"Comparing against peers as of {comp_date.strftime('%B %Y')} "
                   f"(employee's last snapshot)")

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
                        help="Percentage of peers earning less"
                    )
                    st.write(f"**Peer Median:** ${comp_data['salary_median']:,.0f}")
                    st.write(f"**Peer Mean:** ${comp_data['salary_mean']:,.0f}")

                with col2:
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=comp_data['salaries'], nbinsx=20,
                        name='Peer Salaries', marker_color='lightblue'
                    ))
                    fig.add_vline(
                        x=current['current_annual_contracted_salary'],
                        line_dash="dash", line_color="red",
                        annotation_text="This employee",
                        annotation_position="top"
                    )
                    fig.update_layout(
                        title=f"Salary Distribution: {comp_data['name']}",
                        xaxis_title="Salary", yaxis_title="Count",
                        xaxis_tickformat='$,.0f', showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Salary vs seniority scatter plot
                if comp_data['seniority_years'] and len(comp_data['seniority_years']) > 2:
                    fig_seniority = go.Figure()
                    fig_seniority.add_trace(go.Scatter(
                        x=comp_data['seniority_years'],
                        y=comp_data['seniority_salaries'],
                        mode='markers',
                        marker=dict(color=WONG[0], size=7, opacity=0.6),
                        name='Peers',
                    ))
                    # Highlight this employee
                    emp_hire = current.get('date_of_hire', None)
                    if pd.notna(emp_hire):
                        emp_years = (current['Date'] - pd.to_datetime(emp_hire)).days / 365.25
                        if emp_years >= 0:
                            fig_seniority.add_trace(go.Scatter(
                                x=[emp_years],
                                y=[current['current_annual_contracted_salary']],
                                mode='markers',
                                marker=dict(color='red', size=14, symbol='star'),
                                name='This employee',
                            ))
                    # Trend line
                    t_arr = np.array(comp_data['seniority_years'])
                    s_arr = np.array(comp_data['seniority_salaries'])
                    if len(t_arr) > 2 and t_arr.std() > 0:
                        z = np.polyfit(t_arr, s_arr, 1)
                        x_line = np.array([t_arr.min(), t_arr.max()])
                        y_line = z[0] * x_line + z[1]
                        fig_seniority.add_trace(go.Scatter(
                            x=x_line, y=y_line, mode='lines',
                            line=dict(color='gray', dash='dash', width=1),
                            name=f'Trend (${z[0]:+,.0f}/yr)',
                        ))
                    fig_seniority.update_layout(
                        title=f"Salary vs Years on Staff: {comp_data['name']}",
                        xaxis_title="Years on Staff",
                        yaxis_title="Salary",
                        yaxis_tickformat='$,.0f',
                        height=350,
                        legend=dict(orientation="h", yanchor="top", y=-0.2,
                                    xanchor="center", x=0.5),
                    )
                    st.plotly_chart(fig_seniority, use_container_width=True)
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

    latest_date = df['Date'].max()
    latest_df = df[df['Date'] == latest_date]

    col1, col2 = st.columns(2)
    with col1:
        divisions = sorted(latest_df['division'].dropna().unique().tolist())
        division = st.selectbox("Select Division", divisions, key="dept_division")
    with col2:
        if division:
            depts = sorted(
                latest_df[latest_df['division'] == division]['department']
                .dropna().unique().tolist()
            )
            department = st.selectbox("Select Department", depts, key="dept_department")
        else:
            department = None

    if not (division and department):
        return

    # Get latest data for this department (keep all appointments for accurate FTE)
    dept_all = latest_df[
        (latest_df['division'] == division) &
        (latest_df['department'] == department)
    ]

    # Primary appointment per person for the roster display
    dept_primary = (
        dept_all.sort_values('current_annual_contracted_salary', ascending=False)
        .drop_duplicates('id', keep='first')
        .copy()
    )

    st.subheader(f"{department} ({len(dept_primary)} employees)")

    if len(dept_primary) == 0:
        st.info("No employees found in this department.")
        return

    # Vectorized growth calculation for all employees in dept
    emp_ids = dept_primary['id'].tolist()
    emp_history = df[df['id'].isin(emp_ids) & (df['division'] == division)]

    # For each employee, get their first and last salary in this division
    first_in_div = (
        emp_history.sort_values('Date')
        .drop_duplicates('id', keep='first')[['id', 'current_annual_contracted_salary', 'Date']]
        .rename(columns={'current_annual_contracted_salary': 'first_salary', 'Date': 'first_date'})
    )
    last_in_div = (
        emp_history.sort_values('Date')
        .drop_duplicates('id', keep='last')[['id', 'current_annual_contracted_salary']]
        .rename(columns={'current_annual_contracted_salary': 'last_salary'})
    )

    growth = first_in_div.merge(last_in_div, on='id')
    growth['pct_growth'] = np.where(
        growth['first_salary'] > 0,
        ((growth['last_salary'] - growth['first_salary']) / growth['first_salary']) * 100,
        np.nan
    )
    growth['dollar_growth'] = growth['last_salary'] - growth['first_salary']

    dept_primary = dept_primary.merge(
        growth[['id', 'pct_growth', 'dollar_growth']], on='id', how='left')

    # Calculate years on staff
    dept_primary['date_of_hire'] = pd.to_datetime(dept_primary['date_of_hire'], errors='coerce')
    dept_primary['years_on_staff'] = (
        (latest_date - dept_primary['date_of_hire']).dt.days / 365.25
    )

    # Build display table
    display_cols = {
        'first_name': 'First Name',
        'last_name': 'Last Name',
        'title': 'Title',
        'current_annual_contracted_salary': 'Salary',
        'years_on_staff': 'Years',
        'pct_growth': 'Growth %',
        'dollar_growth': 'Growth $',
        'full_time_equivalent': 'FTE',
        'date_of_hire': 'Hire Date',
    }
    available = [c for c in display_cols if c in dept_primary.columns]
    show_df = dept_primary[available].copy()
    show_df = show_df.rename(columns={c: display_cols[c] for c in available})

    if 'Salary' in show_df.columns:
        show_df['Salary'] = show_df['Salary'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "")
    if 'Years' in show_df.columns:
        show_df['Years'] = show_df['Years'].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) and x >= 0 else "")
    if 'Growth %' in show_df.columns:
        show_df['Growth %'] = show_df['Growth %'].apply(
            lambda x: f"{x:+.1f}%" if pd.notna(x) else "")
    if 'Growth $' in show_df.columns:
        show_df['Growth $'] = show_df['Growth $'].apply(
            lambda x: f"${x:+,.0f}" if pd.notna(x) else "")
    if 'FTE' in show_df.columns:
        show_df['FTE'] = show_df['FTE'].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) else "")
    if 'Hire Date' in show_df.columns:
        show_df['Hire Date'] = show_df['Hire Date'].apply(
            lambda x: str(x)[:10] if pd.notna(x) else "")

    dept_primary = dept_primary.reset_index(drop=True)
    id_list = dept_primary['id'].tolist()

    st.caption("Click a row to select, then press View Profile.")
    event = st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="dept_table",
    )

    selected_rows = event.selection.rows if event.selection else []
    if selected_rows:
        sel_idx = selected_rows[0]
        sel_name = f"{dept_primary.iloc[sel_idx]['first_name']} {dept_primary.iloc[sel_idx]['last_name']}"
        if st.button(f"View Profile: {sel_name}", key="dept_view_btn"):
            st.session_state.selected_employee = id_list[sel_idx]
            st.session_state.page = 'individual'
            st.rerun()

    # Summary statistics
    st.divider()
    st.subheader("Department Summary")

    col1, col2, col3, col4 = st.columns(4)
    salaries = dept_primary['current_annual_contracted_salary'].dropna()
    with col1:
        st.metric("Median Salary", f"${salaries.median():,.0f}")
    with col2:
        st.metric("Mean Salary", f"${salaries.mean():,.0f}")
    with col3:
        st.metric("Employees", len(dept_primary))
    with col4:
        # Use all appointments for accurate FTE total
        total_fte = dept_all['full_time_equivalent'].sum()
        st.metric("Total FTE", f"{total_fte:.1f}")

    fig = px.histogram(
        dept_primary, x='current_annual_contracted_salary',
        nbins=20, title=f"Salary Distribution: {department}"
    )
    fig.update_layout(
        xaxis_title="Salary", yaxis_title="Count",
        xaxis_tickformat='$,.0f'
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main application entry point."""
    with st.spinner("Loading salary data..."):
        df = load_data()
        emp_index = build_employee_index(df)

    # Sidebar navigation
    st.sidebar.title("UW-Madison Salary Explorer")
    st.sidebar.divider()

    if 'page' not in st.session_state:
        st.session_state.page = 'search'

    page = st.sidebar.radio(
        "Navigate",
        ['Search', 'Individual Profile', 'Department View'],
        index=['search', 'individual', 'department'].index(st.session_state.page)
        if st.session_state.page in ['search', 'individual', 'department'] else 0
    )

    page_map = {
        'Search': 'search',
        'Individual Profile': 'individual',
        'Department View': 'department'
    }
    st.session_state.page = page_map[page]

    if st.session_state.page == 'search':
        render_search_page(df, emp_index)
    elif st.session_state.page == 'individual':
        render_individual_page(df)
    elif st.session_state.page == 'department':
        render_department_page(df)

    # Footer — data attribution and UFAS credit
    st.sidebar.divider()
    st.sidebar.caption(f"Data as of: {df['Date'].max().strftime('%B %Y')}")
    st.sidebar.caption(f"Total employees: {df['id'].nunique():,}")
    st.sidebar.divider()
    st.sidebar.markdown(
        "**Data provided by [United Faculty & Academic Staff (UFAS)](https://ufas223.org/)**\n\n"
        "UFAS is the union representing UW-Madison faculty and academic staff. "
        "They obtain and publish this salary data to promote transparency.\n\n"
        "Explore their salary tool: [ufas223.github.io/salaries](https://ufas223.github.io/salaries/)\n\n"
        "**[Consider joining UFAS](https://ufas223.org/)**"
    )


if __name__ == "__main__":
    main()
