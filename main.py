import requests
import ast
import pandas as pd
import os
import requests

# Store your API key securely (environment variable is best)
#API key for DeepSeek
DEEPSEEK_API_KEY = "Insert Deepseek API Key, I removed it before submitting"

def ask_deepseek(question):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",   # or "deepseek-reasoner"
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    if "choices" in result:
        return result["choices"][0]["message"]["content"]
    else:
        return f"Error: {result}"
#Ask user for their potential college major
college_major = input("Enter Your Potential College Major: ")

#Ask DeepSeek for relevant entry-level job titles to find insight data
question = (
    f"Suggest 10 of the most relevant entry-level job titles I can apply for "
    f"with a degree in {college_major}. "
    "Return ONLY a valid Python list of strings (no explanations)."
)

response_text = ask_deepseek(question)

try:
    job_titles = ast.literal_eval(response_text)
    print("\nParsed job titles as list:\n", job_titles)
except Exception as e:
    print("\nCould not parse response:\n", response_text, "\nError:", e)

APP_ID = "Information is in in IceRynk Submission"
APP_KEY = "Information is linked in IceRynk Submission"
url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

all_jobs = []
state=input("What state would you like to search for(OR say UNITED STATES to get National Statistics): ")
for title in job_titles:
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": 50,   # 50 is max per request
        "what": title,
        "where": state  # country already in URL, but you can filter to city/state
    }

    response = requests.get(url, params=params)
    data = response.json()

    for job in data.get("results", []):
        all_jobs.append({
            "Search Title": title,   # the query we searched
            "Job Title": job.get("title"),
            "Company": job.get("company", {}).get("display_name"),
            "Location": job.get("location", {}).get("display_name"),
            "Salary Min": job.get("salary_min"),
            "Salary Max": job.get("salary_max"),
            "Category": job.get("category", {}).get("label"),
            "Created": job.get("created"),
            "URL": job.get("redirect_url")
        })

# Create DataFrame
df = pd.DataFrame(all_jobs)
print(len(df))
print(df.head())
print("\nAverage Salary Max across all roles:", df["Salary Max"].mean())
#Provides Information about which relevant job will make a professional the most money on average, based on the data provided
salary_by_job = (
    df.groupby(["Search Title"])["Salary Max"]
      .mean()
      .reset_index()
      .rename(columns={"Salary Max": "Average Salary Max"})
      .sort_values(by="Average Salary Max", ascending=False)
)

print(salary_by_job)
df.to_csv("jobs.csv", index=False)

#Northeastern Majors Webscraper

import requests
from bs4 import BeautifulSoup
import csv
import time
import re
from urllib.parse import urljoin
import random

def get_headers():
    """Get headers to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]

    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1'
    }

def extract_college_from_url(url, text=''):
    """Extract college/school name from URL or text"""
    combined = (url + ' ' + text).lower()

    college_mappings = {
        'business': 'D\'Amore-McKim School of Business',
        'engineering': 'College of Engineering',
        'computer': 'Khoury College of Computer Sciences',
        'arts': 'College of Arts, Media and Design',
        'science': 'College of Science',
        'social': 'College of Social Sciences and Humanities',
        'health': 'Bouvé College of Health Sciences',
        'law': 'School of Law',
        'education': 'College of Professional Studies',
        'public': 'School of Public Policy and Urban Affairs',
        'architecture': 'School of Architecture'
    }

    for key, full_name in college_mappings.items():
        if key in combined:
            return full_name

    return 'Northeastern University'

def clean_major_name(name):
    """Clean and validate major names"""
    if not name:
        return None

    name = re.sub(r'\s+', ' ', name.strip())

    # Skip obvious non-major text
    skip_patterns = [
        r'^(home|about|contact|search|menu|login|apply|admissions)$',
        r'^(view|see|read|learn)\s+(all|more)',
        r'^(back\s+to|skip\s+to)',
        r'^(toggle|show|hide)',
        r'^(majors?|programs?|degrees?|areas?\s+of\s+study)$',
        r'^\d+\s+(majors?|programs?)',
        r'^combined\s+majors?$'
    ]

    name_lower = name.lower()
    if any(re.match(pattern, name_lower) for pattern in skip_patterns):
        return None

    # Remove campus indicators and degree info
    name = re.sub(r'\s*\*\s*$', '', name)  # Remove asterisk
    name = re.sub(r'\s*\((B\.?[AS]\.?|M\.?[AS]\.?|Ph\.?D\.?|MBA|BS|BA|MS|MA)\)$', '', name)
    name = re.sub(r'\s*-\s*(Boston|Oakland)\s*$', '', name)

    # Filter by length and content
    if 3 <= len(name) <= 100 and not name.isdigit():
        return name

    return None

def extract_majors_from_page(soup, base_url, session):
    """Extract individual majors from a page"""
    majors_found = []
    processed_majors = set()

    # Strategy 1: Look for structured major/program listings
    major_selectors = [
        'a[href*="major"]',
        'a[href*="program"]',
        'a[href*="degree"]',
        'a[href*="/undergraduate/"]',
        'a[href*="/academics/"]',
        '.major-link',
        '.program-link',
        '[data-major]',
        '[data-program]'
    ]

    for selector in major_selectors:
        elements = soup.select(selector)
        if elements:
            print(f"   🔍 Found {len(elements)} elements with selector: {selector}")

            for element in elements:
                href = element.get('href', '')
                text = element.get_text(strip=True)

                if href and text:
                    full_url = urljoin(base_url, href)
                    clean_name = clean_major_name(text)

                    if clean_name and clean_name.lower() not in processed_majors:
                        college = extract_college_from_url(full_url, text)
                        majors_found.append({
                            'major': clean_name,
                            'college': college,
                            'url': full_url
                        })
                        processed_majors.add(clean_name.lower())

    # Strategy 2: Look for all links that might contain majors
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href', '')
        text = link.get_text(strip=True)

        if href and text:
            full_url = urljoin(base_url, href)

            # Filter for academic program URLs
            if ('northeastern.edu' in full_url.lower() and
                any(keyword in full_url.lower() for keyword in [
                    'major', 'program', 'degree', 'study', 'academic',
                    'undergraduate', 'bachelor', 'college', 'school'
                ])):

                clean_name = clean_major_name(text)
                if clean_name and clean_name.lower() not in processed_majors and len(clean_name) > 3:
                    college = extract_college_from_url(full_url, text)
                    majors_found.append({
                        'major': clean_name,
                        'college': college,
                        'url': full_url
                    })
                    processed_majors.add(clean_name.lower())

    # Strategy 3: Look for specific known majors from Northeastern
    known_majors = [
        'Africana Studies', 'American Sign Language', 'Anthropology', 'Applied Physics',
        'Architecture', 'Art', 'Behavioral Neuroscience', 'Biochemistry', 'Biology',
        'Bioengineering', 'Business Administration', 'Chemical Engineering',
        'Chemistry', 'Civil Engineering', 'Communication Studies', 'Computer Engineering',
        'Computer Science', 'Criminal Justice', 'Data Science', 'Economics',
        'Electrical Engineering', 'English', 'Environmental Engineering',
        'Environmental Science', 'Finance', 'History', 'Industrial Engineering',
        'Information Science', 'International Affairs', 'Journalism', 'Linguistics',
        'Marketing', 'Mathematics', 'Mechanical Engineering', 'Music', 'Nursing',
        'Philosophy', 'Physics', 'Political Science', 'Psychology', 'Public Health',
        'Sociology', 'Theatre', 'Urban Planning', 'Graphic Design', 'Game Design',
        'Media and Screen Studies', 'Public Relations', 'International Business',
        'Entrepreneurship', 'Accounting', 'Supply Chain Management', 'Cybersecurity'
    ]

    # Check if any known majors appear in the page text
    page_text = soup.get_text().lower()
    for major in known_majors:
        if major.lower() in page_text and major.lower() not in processed_majors:
            # Try to find the specific link for this major
            major_link = None
            for link in soup.find_all('a', href=True):
                if major.lower() in link.get_text().lower():
                    major_link = urljoin(base_url, link.get('href'))
                    break

            if not major_link:
                major_link = base_url

            college = extract_college_from_url(major_link, major)
            majors_found.append({
                'major': major,
                'college': college,
                'url': major_link
            })
            processed_majors.add(major.lower())

    return majors_found

def scrape_northeastern_majors():
    """Main scraping function for Northeastern University"""
    # Try multiple pages to get comprehensive major listings
    urls_to_try = [
        "https://admissions.northeastern.edu/academics/areas-of-study/",
        "https://catalog.northeastern.edu/undergraduate/",
        "https://www.northeastern.edu/academics/"
    ]

    majors_data = []

    print("🚀 Starting Northeastern University Majors Scraper")
    print("=" * 55)
    print("Goal: Extract each major as a separate row with school and link")

    try:
        session = requests.Session()
        session.headers.update(get_headers())

        for base_url in urls_to_try:
            print(f"\n📡 Fetching: {base_url}")
            time.sleep(2)  # Be respectful

            try:
                response = session.get(base_url, timeout=15)
                response.raise_for_status()

                print(f"✅ Page loaded successfully! (Status: {response.status_code})")

                soup = BeautifulSoup(response.content, 'html.parser')
                print(f"📄 Page title: {soup.find('title').get_text() if soup.find('title') else 'Unknown'}")

                # Extract majors from this page
                page_majors = extract_majors_from_page(soup, base_url, session)
                majors_data.extend(page_majors)
                print(f"   Found {len(page_majors)} majors on this page")

            except Exception as e:
                print(f"   ❌ Failed to load {base_url}: {e}")
                continue

        # Remove duplicates based on major name
        unique_majors = []
        seen_majors = set()

        for major in majors_data:
            major_key = major['major'].lower().strip()
            if major_key not in seen_majors:
                seen_majors.add(major_key)
                unique_majors.append(major)

        print(f"\n🎯 Total unique majors found: {len(unique_majors)}")

        if unique_majors:
            # Save to CSV - each major in its own row
            filename = 'northeastern_majors.csv'
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Major', 'School', 'Link']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for major in unique_majors:
                    writer.writerow({
                        'Major': major['major'],
                        'School': major['college'],
                        'Link': major['url']
                    })

            print(f"✅ Successfully saved {len(unique_majors)} individual majors to {filename}")

            # Show exact format you requested
            print("\n📋 Sample rows (exactly as saved):")
            print("Major,School,Link")
            print("-" * 80)
            for major in unique_majors[:15]:  # Show first 15
                school_short = major['college'][:30] + "..." if len(major['college']) > 30 else major['college']
                link_short = major['url'][:40] + "..." if len(major['url']) > 40 else major['url']
                print(f"{major['major']},{school_short},{link_short}")

            if len(unique_majors) > 15:
                print(f"... and {len(unique_majors)-15} more rows")

            # Show breakdown by school
            print(f"\n📊 Majors by School:")
            school_counts = {}
            for major in unique_majors:
                school = major['college']
                school_counts[school] = school_counts.get(school, 0) + 1

            for school, count in sorted(school_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"   {count:3d} majors - {school}")

        else:
            print("❌ No majors found")
            print("The page structure might be different than expected")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    print("🎓 Northeastern University (Boston) Majors Scraper")
    print("Located in the heart of Boston, Massachusetts!")
    print("Output: Each major in separate row with school and link")
    print()

    # Check requirements
    try:
        import requests
        import bs4
    except ImportError:
        print("❌ Missing packages! Install with:")
        print("pip install requests beautifulsoup4")
        exit(1)

    scrape_northeastern_majors()

northeastern = pd.read_csv("northeastern_majors.csv")
NE_Majors=northeastern["Major"].tolist()
question_data = (
    "Create a Python list of which items in this list do not look like valid college majors: "
    + str(NE_Majors)
)

response_text = ask_deepseek(question_data)
print(response_text)

import re, ast

# Find the first [...] block in the response
match = re.search(r"\[.*\]", response_text, re.DOTALL)
if match:
    list_str = match.group(0)
    non_majors = ast.literal_eval(list_str)
else:
    non_majors = []

print(non_majors)

if college_major in northeastern["Major"].values:
    print(college_major + " is available at Northeastern")
else:
    print(college_major + " is not available at Northeastern")
