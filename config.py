"""
Configuration for UW-Madison Public Finance Data Pipeline
==========================================================

This module contains all configuration settings, mappings, and constants used
throughout the data pipeline. Centralizing these values here makes it easy to:

1. Update mappings when data formats change
2. Add new division or category mappings
3. Adjust CPI settings or file paths
4. Understand the business logic encoded in the mappings

Key Configuration Sections:
---------------------------
- **Paths**: File and directory locations
- **CPI Settings**: Consumer Price Index API configuration
- **Employee Categories**: Code-to-name mappings for employee types
- **Division Mappings**: Normalize division names across UFAS/Workday systems
- **Column Mappings**: Handle differences in column names between file formats
- **Analysis Groups**: Define which job groups/titles belong to certain categories

Data Source Background:
-----------------------
The data comes from two different HR systems:
- **UFAS** (University Financial Administration System): Used until ~2025
- **Workday**: New system starting 2025

These systems use different naming conventions, which is why we need extensive
mapping configurations to normalize the data for consistent analysis.

Usage:
------
    import config

    # Access file paths
    data_dir = config.DATA_DIR

    # Use mappings
    category_name = config.EMPLOYEE_CATEGORIES.get('AS', 'Unknown')

    # Check division normalization
    normalized_div = config.DIVISION_NAME_MAPPING.get(workday_name, workday_name)
"""
import os

# =============================================================================
# FILE PATHS
# =============================================================================
# These paths are relative to this config file's location

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Input/output files
JOB_DESCRIPTIONS_FILE = os.path.join(BASE_DIR, 'uw_madison_job_descriptions.csv')
CPI_CACHE_FILE = os.path.join(DATA_DIR, 'cpi_data.csv')

# =============================================================================
# CPI (CONSUMER PRICE INDEX) SETTINGS
# =============================================================================
# Used to calculate inflation-adjusted "real" salaries
# Data is fetched from the Federal Reserve Economic Data (FRED) API

CPI_SERIES_ID = "CPIAUCSL"      # All Urban Consumers, Seasonally Adjusted
CPI_BASE_DATE = "2021-11-01"    # Reference date for "2021 dollars" adjustment

# =============================================================================
# EMPLOYEE CATEGORY MAPPINGS
# =============================================================================
# Employee categories classify workers into groups like Faculty, Academic Staff,
# University Staff, etc. UFAS used short codes; Workday uses full text names.

# UFAS format: short codes (e.g., "AS" = Academic Staff)
EMPLOYEE_CATEGORY_CODES = {
    "AS": "Academic Staff",
    "FA": "Faculty",
    "CJ": "University Staff",
    "CL": "University Staff",
    "CP": "University Staff",
    "ET1": "Employee-In-Training",
    "ET2": "Employee-In-Training",
    "ET3": "Employee-In-Training",
    "ET4": "Employee-In-Training",
    "LI": "Limited Appointee",
    "OT1": "Other",
    "OT2": "Other",
    "OT3": "Other",
    "OT4": "Other",
    "OT5": "Other",
    "OT6": "Other",
}

# Employee category name normalization (for Workday format variations)
EMPLOYEE_CATEGORY_NORMALIZE = {
    # Workday uses different text than UFAS
    "Employees in Training": "Employee-In-Training",
    "Employee-in-Training": "Employee-In-Training",
    "Limited": "Limited Appointee",
}

# Combined mapping: codes + normalization
EMPLOYEE_CATEGORIES = {**EMPLOYEE_CATEGORY_CODES, **EMPLOYEE_CATEGORY_NORMALIZE}

# =============================================================================
# JOB GROUP CLASSIFICATIONS
# =============================================================================
# Job groups are broad categories based on job function (Research, Instruction,
# Administrative, etc.). These lists help filter and analyze specific populations.

# Job groups typically involved in teaching/research (for academic analysis)
FACULTY_INSTRUCTION_RESEARCH_JOBGROUPS = [
    'Instruction',
    'Animal Care Services',
    'Faculty',
    'Research'
]

# Titles in Teaching & Learning that are NOT teaching roles
NON_TEACHING_TITLES_TLA = [
    'Teach, Learn, & Tech Spec II',
    'Teach, Learn, & Tech Spec I',
    'Cont Edu Prog Dir',
    'Early Child Edu Asst Teacher',
    'Teach, Learn & Tech Spec III',
    'Early Child Edu Teacher',
    'Teaching, Learning, & Tech Dir',
    'Cont Edu Specialist',
    'Teaching, Learning, & Tech Mgr',
    'Instructional Administrator',
    'Academic Assessment Dir (Inst)',
    'Education Technical Consultant',
    'Academic Assessment Specialist',
    'Athletics Learning Specialist',
    'Cont Edu Prog Mgr',
    'Cont Edu Prog Instructor',
    'Cont Edu Prog Dir (C)',
    'Psychometrician',
    'Music Coach',
    'Academic Assessment Manager',
    'Early Child Edu Dir',
    'Academic Assessment Coord',
    'Assistant Teaching Professor',
    'Tutor',
    'Early Child Edu Assoc Dir',
    'Cont Edu Prog Dir (B)',
    'Preceptor',
    'Cont Edu Prog Assoc Dir',
    'Instructional & Media Designer',
    'Teaching & Learning Developer'
]

# Divisions primarily providing administrative or student services
ADMIN_SS_DIVISION_LIST = [
    'Div for Teaching and Learning',
    'Graduate School',
    'General Educational Admin',
    'Recreation & Wellbeing',
    'Collab Adv Learning & Teaching',
    'Division of Student Life',
    'Wisconsin Union',
    'Information Technology',
    'Enrollment Management',
    'VC for Rsrch & Grad Education',
    'General Services',
    'Facilities Planning & Mgmt'
]

# =============================================================================
# COLUMN NAME MAPPINGS
# =============================================================================
# UFAS and Workday use different column names for the same data. These mappings
# normalize column names so downstream code can use consistent field names.

# UFAS format column renames (original_name -> standardized_name)
UFAS_COLUMN_RENAMES = {
    'annual_full_salary': 'current_annual_contracted_salary',
    'full-time_equivalent': 'full_time_equivalent',
    'job_code': 'jobcode',
    'appointment_type_and_length': 'appt_type_length',
    'date_of_hire': 'date_of_hire',
}

WORKDAY_COLUMN_RENAMES = {
    'annual_full_salary': 'current_annual_contracted_salary',
    'annualized_rate_amount': 'current_annual_contracted_salary',
    'full-time_equivalent': 'full_time_equivalent',
    'fte': 'full_time_equivalent',
    'job_code': 'jobcode',
    'employee_contract_type': 'appt_type_length',
    'date_of_hire': 'date_of_hire',
}

# Maximum total FTE allowed per person per snapshot before deduplication kicks in
MAX_TOTAL_FTE = 1.4

# Columns to drop if present
COLUMNS_TO_DROP = ['annual_fte_adjusted_salary', 'pay_basis', 'compensation_basis']

# =============================================================================
# DIVISION NAME NORMALIZATION
# =============================================================================
# When UW-Madison switched from UFAS to Workday, many division names changed.
# For example, "Sch of Med & Public Health" became "School of Medicine and Public Health".
# Additionally, some divisions were split or merged during reorganizations.
#
# This mapping normalizes all names to the UFAS convention so we can track
# employees and spending consistently across the transition.
#
# Format: "Workday Name": "UFAS Name"

DIVISION_NAME_MAPPING = {
    # Direct renames: Workday name -> original UFAS name
    "School of Medicine and Public Health": "Sch of Med & Public Health",
    "Facilities Planning and Management": "Facilities Planning & Mgmt",
    "College of Agricultural and Life Sciences": "College of Ag & Life Science",
    "Division of Information Technology": "Information Technology",
    "Division of Extension": "UW - Madison Extension",
    "Division of Enrollment Management": "Enrollment Management",
    "Division for Teaching and Learning": "Div for Teaching and Learning",
    "University Recreation and Wellbeing": "Recreation & Wellbeing",
    "University Health Services": "Univ Health Services",
    "University Police Department": "University Police Dept",
    "Division of the Arts": "Division of The Arts",
    "Libraries": "General Library",
    "Wisconsin State Lab of Hygiene": "Wi State Laboratory Hygiene",
    "Wisconsin Veterinary Diagnostic Laboratory": "Wi Veterinary Diagnostic Lab",
    "IES Institute of Environmental Studies": "Nelson Inst Envrnmntal Study",

    # Research divisions that report to VC Research
    "Office of the Vice Chancellor for Research": "VC for Rsrch & Grad Education",
    "Global Health Institute": "VC for Rsrch & Grad Education",

    # New administrative divisions (created in Workday) -> closest UFAS equivalent
    "Office of Human Resources": "General Services",
    "Office of Strategic Consulting": "General Services",
    "Vice Chancellor for Finance and Administration": "General Services",
    "Vice Chancellor for Legal Affairs": "General Services",
    "Vice Chancellor for University Relations": "General Services",
    "Vice Chancellor for Strategic Communication": "General Services",
    "Associate Vice Chancellor for Finance": "Business Services",
    "Administrative Transformation Program": "General Services",
    "University Administration": "General Educational Admin",
    "Chazen Museum of Art": "General Services",
    "University of Wisconsin Press": "General Services",
    "Vice Provost of Data, Academic Planning & Institutional Research": "General Educational Admin",
    "Administration Innovation and Planning": "General Services",

    # Division of Student Life was split in Workday - map back to original
    "Vice Chancellor for Student Affairs": "Division of Student Life",
    "Associate Vice Chancellor for Student Advocacy": "Division of Student Life",
    # DDEEA was part of Division of Student Life in UFAS, then briefly its own division
    "Associate Vice Chancellor for Identity and Inclusion": "Division of Student Life",
    "Division of Diversity, Equity and Educational Achievement": "Division of Student Life",
}
