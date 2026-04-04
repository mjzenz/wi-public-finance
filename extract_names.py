import pandas as pd

df = pd.read_excel(r'data\Updated 2025-09 All Faculty and Staff Title and Salary Information.xlsx')
df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
ls = df[df['division'] == 'College of Letters & Science'].copy()

sal_col = 'annual_full_salary'

# All positions in the plan, identified by (department, title, salary)
plan_positions = [
    # Phase 1
    (1, 'Letters & Science Administration', 'Assoc Dean', 400269),
    (1, 'Letters & Science Administration', 'Innovation and Strategy Dir', 349626),
    (1, 'Letters & Science Administration', 'Innovation and Strategy Dir', 323186),
    (1, 'Letters & Science Administration', 'Assoc Dean', 289155),
    (1, 'Letters & Science Administration', 'Assoc Dean', 280440),
    (1, 'Letters & Science Administration', 'Assoc Dean', 256813),
    (1, 'Letters & Science Administration', 'Assoc Dean', 253732),
    (1, 'Letters & Science Administration', 'Associate Dean', 200015),
    # Phase 2
    (2, 'Letters & Science Administration', 'Associate Dean', 193128),
    (2, 'Letters & Science Administration', 'Associate Dean', 192591),
    (2, 'Letters & Science Administration', 'Facilities Director', 175000),
    (2, 'Letters & Science Administration', 'Finance Associate Director', 164195),
    (2, 'Letters & Science Administration', 'Advancement Director', 157718),
    (2, 'Letters & Science Administration', 'Finance Associate Director', 157590),
    (2, 'Letters & Science Administration', 'Bus Eng Assoc Dir', 157590),
    (2, 'Letters & Science Administration', 'Career Services Director', 157556),
    (2, 'Letters & Science Administration', 'External Relations Director', 152781),
    (2, 'Letters & Science Administration', 'Bus Eng Assoc Dir', 150380),
    # Phase 3
    (3, 'UW Survey Center', 'Research Program Director', 180283),
    (3, 'Institute for Research on Poverty', 'Center Associate Director', 168256),
    (3, 'LaFollette School of Public Affairs', 'Project Program Manager', 164800),
    (3, 'Center for Healthy Minds', 'Res Prog Assoc Dir', 160471),
    (3, 'UW Survey Center', 'IT Director I (MSN)', 156145),
    (3, 'Social Science Research Services (SSRS)', 'IT Director I (MSN)', 148361),
    (3, 'Student Academic Affairs', 'Assistant Dean', 142918),
    (3, 'Student Academic Affairs', 'Assistant Dean', 142262),
    (3, 'Student Academic Affairs', 'Assistant Dean', 141831),
    (3, 'Student Academic Affairs', 'Assistant Dean', 138898),
    (3, 'Social Science Research Services (SSRS)', 'Administrative Director', 129422),
    (3, 'Successworks', 'Career Svcs Assoc Dir', 108739),
    (3, 'Successworks', 'Career Svcs Assoc Dir', 107843),
    (3, 'Successworks', 'Teaching, Learning, & Tech Mgr', 105876),
    # Phase 4
    (4, 'Political Science', 'Department Administrator II', 142617),
    (4, 'Anthropology', 'Department Administrator I', 109776),
    (4, 'Art History', 'Department Administrator I', 101529),
    # Phase 5
    (5, 'Center for Limnology', 'Professor Emeritus', 243665),
    (5, 'Atmospheric & Oceanic Sciences', 'Professor Emeritus', 237030),
    (5, 'Geoscience', 'Professor Emeritus', 233221),
    (5, 'Psychology', 'Professor Emeritus', 228557),
    (5, 'Geoscience', 'Professor Emeritus', 223961),
    (5, 'Geoscience', 'Professor Emeritus', 223380),
    (5, 'Sandra Rosenbaum School of Social Work', 'Professor Emeritus', 222568),
    (5, 'Sandra Rosenbaum School of Social Work', 'Professor Emeritus', 215531),
    (5, 'Institute for Research on Poverty', 'Professor Emeritus', 214849),
    (5, 'Geoscience', 'Professor Emeritus', 211035),
    (5, 'Sandra Rosenbaum School of Social Work', 'Professor Emeritus', 210112),
    (5, 'Sociology', 'Professor Emeritus', 206323),
    # Phase 6
    (6, 'Letters & Science Administration', 'Teaching, Learning, & Tech Dir', 143392),
    (6, 'Letters & Science Administration', 'HR Associate Director', 142882),
    (6, 'Letters & Science Administration', 'Assistant Dean', 141593),
    (6, 'Letters & Science Administration', 'Assistant Dean', 140835),
    (6, 'Letters & Science Administration', 'Assistant Dean', 137548),
    (6, 'Letters & Science Administration', 'Academic Program Director', 136620),
    (6, 'Letters & Science Administration', 'Financial Manager', 133908),
    (6, 'Letters & Science Administration', 'IT Manager', 132426),
]

# Match each position to a name
# We need to handle cases where multiple people have the same title in the same dept
# by matching on salary (rounded to nearest dollar)
used = set()  # track indices already matched

for phase, dept, title, sal in plan_positions:
    candidates = ls[(ls['department'] == dept) & (ls['title'] == title)].copy()
    candidates['sal_diff'] = abs(candidates[sal_col] - sal)
    candidates = candidates.sort_values('sal_diff')

    matched = False
    for idx, row in candidates.iterrows():
        if idx not in used and row['sal_diff'] < 5:  # within $5 tolerance
            used.add(idx)
            print(f"{phase}|{dept}|{title}|{sal}|{row['first_name']}|{row['last_name']}|{row[sal_col]:.0f}")
            matched = True
            break

    if not matched:
        # Try wider tolerance
        for idx, row in candidates.iterrows():
            if idx not in used and row['sal_diff'] < 100:
                used.add(idx)
                print(f"{phase}|{dept}|{title}|{sal}|{row['first_name']}|{row['last_name']}|{row[sal_col]:.0f}")
                matched = True
                break

    if not matched:
        print(f"{phase}|{dept}|{title}|{sal}|NO MATCH|NO MATCH|0")
