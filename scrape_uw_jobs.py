"""
Script to scrape UW-Madison Standard Job Descriptions
https://hr.wisc.edu/standard-job-descriptions/

Extracts all job information including expanded details:
- Job title, code, group, subgroup
- Salary range, employee category
- Job summary and responsibilities
- Education requirements, FLSA status
- Supervisory requirements, scaled job info
- Required knowledges and skills
"""

import requests
from bs4 import BeautifulSoup
import csv
import sys
import re


def clean_text(text):
    """Clean text by replacing newlines with spaces and normalizing whitespace."""
    if not text:
        return ''
    # Replace newlines and multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_field_value(li_element):
    """Extract the value from a field's li element, handling different structures."""
    # Check for nested ul (list of items)
    nested_ul = li_element.find('ul', recursive=False)
    if not nested_ul:
        # Also check inside a div
        div = li_element.find('div', recursive=False)
        if div:
            nested_ul = div.find('ul', recursive=False)

    if nested_ul:
        items = []
        for nested_li in nested_ul.find_all('li', recursive=False):
            # Check if it contains a link
            link = nested_li.find('a')
            if link:
                items.append(clean_text(link.get_text(strip=True)))
            else:
                items.append(clean_text(nested_li.get_text(strip=True)))
        return '; '.join(items)

    # Check for a div with text content
    div = li_element.find('div', recursive=False)
    if div:
        return clean_text(div.get_text(strip=True))

    # Fall back to getting text after the strong tag and button
    text = li_element.get_text(strip=True)
    # Remove the field label
    strong = li_element.find('strong')
    if strong:
        label = strong.get_text(strip=True)
        text = text.replace(label, '', 1).strip()
    return clean_text(text)


def scrape_job_descriptions():
    """Scrape job titles and positions from UW-Madison HR website."""

    url = "https://hr.wisc.edu/standard-job-descriptions/?sjd-sort=title&sjd-order=ASC&sjd-max-results=all&page_number=1"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Fetching data from: {url}")
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Failed to fetch page. Status code: {response.status_code}")
        sys.exit(1)

    print(f"Page fetched successfully. Content length: {len(response.text)} characters")

    soup = BeautifulSoup(response.text, 'html.parser')

    jobs = []

    # Find all details elements (each represents a job listing)
    details_elements = soup.find_all('details')
    print(f"Found {len(details_elements)} job entries")

    for details in details_elements:
        job = {}

        # Get the summary element which contains the header info
        summary = details.find('summary')
        if not summary:
            continue

        # Extract job title from h3
        title_elem = summary.find('h3')
        if title_elem:
            job['title'] = title_elem.get_text(strip=True)

        # Parse divs within summary for structured data
        divs = summary.find_all('div', recursive=False)

        for div in divs:
            div_text = div.get_text(separator=' ', strip=True)

            # Job Group - first div typically contains this
            if 'Job Group:' in div_text:
                group_match = re.search(r'Job Group:\s*(.+?)(?:\s*Job Subgroup:|$)', div_text)
                if group_match:
                    job['job_group'] = group_match.group(1).strip()

                subgroup_span = div.find('span')
                if subgroup_span:
                    job['job_subgroup'] = subgroup_span.get_text(strip=True)

            # Salary Range and Employee Category from summary
            if 'Salary Range' in div_text:
                salary_match = re.search(r'Salary Range \(Annual\):\s*(.+?)\s*Employee Category:', div_text)
                if salary_match:
                    job['salary_range_summary'] = salary_match.group(1).strip()

                category_match = re.search(r'Employee Category:\s*(.+?)$', div_text)
                if category_match:
                    job['employee_category'] = category_match.group(1).strip()

            # Job Code from summary
            if 'Job Code:' in div_text:
                code_match = re.search(r'Job Code:\s*([A-Z0-9]+)', div_text)
                if code_match:
                    job['job_code'] = code_match.group(1).strip()

        # Get the expanded details from sjd-inner
        sjd_inner = details.find('div', class_='sjd-inner')
        if sjd_inner:
            # Find all field items (li elements with strong labels)
            main_ul = sjd_inner.find('ul', recursive=False)
            if main_ul:
                for li in main_ul.find_all('li', recursive=False):
                    strong = li.find('strong')
                    if not strong:
                        continue

                    label = strong.get_text(strip=True).rstrip(':')
                    value = extract_field_value(li)

                    # Map labels to field names
                    field_map = {
                        'Job Summary': 'job_summary',
                        'Job Responsibilities': 'job_responsibilities',
                        'Education': 'education',
                        'FLSA Status': 'flsa_status',
                        'Institution Job': 'institution_job',
                        'Required Supervisory Duty of at Least 2.0 Full-Time Equivalent (FTE) Employees': 'supervisory_required',
                        'Employee Category': 'employee_category_detail',
                        'Scaled Job': 'scaled_job',
                        'Salary Range (Annual)': 'salary_range_detail',
                        'Job Code': 'job_codes_detail',
                    }

                    if label in field_map:
                        job[field_map[label]] = value

            # Get Knowledges and Skills from the second ul (after the h4)
            all_uls = sjd_inner.find_all('ul')
            for ul in all_uls[1:]:  # Skip the first main ul
                for li in ul.find_all('li', recursive=False):
                    strong = li.find('strong')
                    if not strong:
                        continue

                    label = strong.get_text(strip=True).rstrip(':')
                    if label == 'Knowledges':
                        job['knowledges'] = extract_field_value(li)
                    elif label == 'Skills':
                        job['skills'] = extract_field_value(li)

            # Get direct link
            link_div = sjd_inner.find('div', style=lambda x: x and 'border-top' in x if x else False)
            if link_div:
                link = link_div.find('a')
                if link:
                    job['direct_link'] = link.get('href', '')

        if job.get('title'):
            jobs.append(job)

    return jobs


def save_to_csv(jobs, filename='uw_madison_job_descriptions.csv'):
    """Save job data to CSV file."""
    if not jobs:
        print("No jobs to save.")
        return

    # Define column order
    fieldnames = [
        'job_code',
        'title',
        'job_group',
        'job_subgroup',
        'employee_category',
        'salary_range_summary',
        'salary_range_detail',
        'job_summary',
        'job_responsibilities',
        'education',
        'flsa_status',
        'institution_job',
        'supervisory_required',
        'scaled_job',
        'job_codes_detail',
        'knowledges',
        'skills',
        'direct_link'
    ]

    # Ensure all fields exist
    for job in jobs:
        for field in fieldnames:
            if field not in job:
                job[field] = ''

    print(f"Saving {len(jobs)} jobs to {filename}")

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Successfully saved to {filename}")


if __name__ == '__main__':
    jobs = scrape_job_descriptions()
    print(f"\nTotal jobs found: {len(jobs)}")

    if jobs:
        # Show first entry in detail
        print("\n=== First entry details ===")
        first = jobs[0]
        for key, value in first.items():
            if value:
                display_val = value[:100] + '...' if len(str(value)) > 100 else value
                print(f"  {key}: {display_val}")

        save_to_csv(jobs)

        # Show summary statistics
        print("\n=== Field coverage ===")
        for field in ['job_summary', 'job_responsibilities', 'education', 'flsa_status',
                      'knowledges', 'skills', 'supervisory_required']:
            count = sum(1 for j in jobs if j.get(field))
            print(f"  {field}: {count}/{len(jobs)} jobs")
