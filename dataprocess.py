import numpy as np
import pandas as pd
import keyring
import import_data

fred_api_key = keyring.get_password("fredapi","fredapi")

faculty_instruction_research_jobgroups = [
    'Instruction', 'Animal Care Services', 'Faculty','Research']

non_teaching_titles_TLA = [
    'Teach, Learn, & Tech Spec II',
       'Teach, Learn, & Tech Spec I',
       'Cont Edu Prog Dir', 'Early Child Edu Asst Teacher',
       'Teach, Learn & Tech Spec III', 'Early Child Edu Teacher',
       'Teaching, Learning, & Tech Dir',
       'Cont Edu Specialist', 'Teaching, Learning, & Tech Mgr',
       'Instructional Administrator', 'Academic Assessment Dir (Inst)',
       'Education Technical Consultant', 'Academic Assessment Specialist',
       'Athletics Learning Specialist', 'Cont Edu Prog Mgr',
       'Cont Edu Prog Instructor', 'Cont Edu Prog Dir (C)',
       'Psychometrician',  'Music Coach',
       'Academic Assessment Manager', 'Early Child Edu Dir',
       'Academic Assessment Coord', 'Assistant Teaching Professor',
       'Tutor', 'Early Child Edu Assoc Dir',
       'Cont Edu Prog Dir (B)', 'Preceptor',
        'Cont Edu Prog Assoc Dir',
        'Instructional & Media Designer',
       'Teaching & Learning Developer']


filenames = import_data.read_ufas_file_names("data")
#Basic Data Cleaning
salary_data = import_data.clean_ufas_data(filenames, fred_api_key)

#Remove 0 FTE appointments
salary_data = salary_data.loc[salary_data.full_time_equivalent > .01]
salary_data["jobgroup"] = import_data.job_group(salary_data.jobcode)

#List of divisions with faculty appointments
faculty_division_list = (
    salary_data
    .loc[salary_data.employee_category == "Faculty"]
    .division
    .unique())

salary_data['IsFacultyDivision'] = salary_data['division'].isin(faculty_division_list)

#New variable in salary_data to indicate that the jobgroup is in non_teaching_titles_TLA or

salary_data['IsFacResTeachingTitle'] = (
     salary_data['jobgroup'].isin(faculty_instruction_research_jobgroups) &
        ~((salary_data['jobgroup'] == 'Teaching and Learning') &
        salary_data['title'].isin(non_teaching_titles_TLA))

)




#Determine proprortions of each employment category
department_jobgroup_prop = (
    salary_data[['division','department','Date','jobgroup','full_time_equivalent']]
    .groupby([salary_data['division'],salary_data['department'], salary_data['Date'], salary_data['jobgroup']])
    .sum('full_time_equivalent'))

# Calculate total FTE per (division, department, Date)
department_jobgroup_prop['total_fte'] = (
    department_jobgroup_prop
    .groupby(['division', 'department', 'Date'])
    .sum('full_time_equivalent'))


# Calculate proportion
department_jobgroup_prop['fte_proportion'] = (
    department_jobgroup_prop['full_time_equivalent'] /
    department_jobgroup_prop['total_fte']
)

admin_ss_division_list = ['Div for Teaching and Learning',
       'Graduate School', 'General Educational Admin',
       'Recreation & Wellbeing', 'Collab Adv Learning & Teaching',
        'Division of Student Life', 'Wisconsin Union',  'Information Technology' ,
        'Enrollment Management', 'VC for Rsrch & Grad Education', 'General Services',
        'Facilities Planning & Mgmt']

dept_fte = (salary_data
            .groupby([salary_data['division'], salary_data['department'], salary_data['Date']])
            .sum('full_time_equivalent')
            .pivot_table(index = ['division', 'department'],columns = ['Date'], values = ['full_time_equivalent']))

# calculate change in FTE from the begining date for each date in salary_data grouped by IsFacultyDivision

# 1. Group and sum FTE by IsFacultyDivision and Date
fte_by_IsFacultyDivision = (
    salary_data
    .groupby(['IsFacultyDivision','jobgroup', 'Date'])['full_time_equivalent']
    .sum()
    .reset_index()
)

# 2. Get the starting FTE for each IsFacultyDivision
fte_by_IsFacultyDivision['start_fte'] = (
    fte_by_IsFacultyDivision
    .groupby(['IsFacultyDivision', 'jobgroup'])['full_time_equivalent']
    .transform('first')
)


fte_by_IsFacultyDivision['fte_change'] = (
    (fte_by_IsFacultyDivision['full_time_equivalent'] - fte_by_IsFacultyDivision['start_fte'])
)


# 3. Calculate percent change relative to starting FTE


fte_by_IsFacultyDivision['fte_pct_change'] = (
    (fte_by_IsFacultyDivision['full_time_equivalent'] - fte_by_IsFacultyDivision['start_fte']) /
    fte_by_IsFacultyDivision['start_fte'] * 100
)

#pivotable format for fte_by_IsFacultyDivision
fte_change_by_IsFacultyDivision = (
    fte_by_IsFacultyDivision
    .loc[fte_by_IsFacultyDivision['Date'] >= '2025-01-01']
    .pivot_table(index=['jobgroup'], columns='IsFacultyDivision', values='fte_change')
    .reset_index()
)

#pivotable format for fte_by_IsFacultyDivision
fte_prct_change_by_IsFacultyDivision = (
    fte_by_IsFacultyDivision
    .loc[fte_by_IsFacultyDivision['Date'] >= '2025-01-01']
    .pivot_table(index=['jobgroup'], columns='IsFacultyDivision', values='fte_pct_change')
    .reset_index()
)

# fte_by_group now contains the percent change in FTE for each group and date





# Find departments with transferred employees

# Sort by employee and date to track department changes
salary_data = salary_data.sort_values(['id_jobcode', 'Date'])

# Identify department changes for each employee in same jobcode
salary_data['prev_division_department'] = (
    salary_data.groupby('id_jobcode')['division_department'].shift(1)
)
salary_data['transferred'] = (
    (salary_data['division_department'] != salary_data['prev_division_department']) &
    salary_data['prev_division_department'].notna()
)

# Mark employees who have ever transferred
transferred_emps = salary_data.loc[salary_data['transferred'], 'id_jobcode'].unique()

# For each (department, date), count transferred employees present
dept_date_transfer_counts = (
    salary_data[salary_data['id_jobcode'].isin(transferred_emps)]
    .groupby(['division_department', 'Date'])['id_jobcode']
    .nunique()
    .reset_index()
    .rename(columns={'id_jobcode': 'num_transferred_emps'})
)

# Departments and dates with at least 4 transferred employees
dept_date_with_4plus = dept_date_transfer_counts.loc[
    dept_date_transfer_counts['num_transferred_emps'] >= 4, ['division_department', 'Date']
]

# Merge indicator into salary_data
salary_data = salary_data.merge(
    dept_date_with_4plus.assign(DeptHas4PlusTransfers=True),
    on=['division_department', 'Date'],
    how='left'
)
salary_data['DeptHas4PlusTransfers'] = salary_data['DeptHas4PlusTransfers'].fillna(False)

# Pairs of departments where at least 4 employees came from and went to
transferred_dept_pairs = (
    salary_data[salary_data['transferred']]
    .groupby(['prev_division_department', 'division_department'])
    .size()
    .reset_index(name='transfer_count')
)
