import os
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from fpdf import FPDF


os.makedirs("jobs", exist_ok=True)

EXPERIENCE_YEARS = 5.5
MAX_EXPERIENCE_YEARS = 6
LOOKBACK_HOURS = 48
HEADERS = {"User-Agent": "Mozilla/5.0"}

KEYWORDS = [
    "devops",
    "platform engineer",
    "sre",
    "site reliability",
    "cloud",
    "infrastructure",
    "automation",
    "kubernetes",
    "docker",
    "aws",
    "azure",
    "gcp",
    "ci/cd",
    "continuous integration",
    "continuous delivery",
    "terraform",
    "ansible",
    "puppet",
    "chef",
    "cloud engineer",
    "systems engineer",
    "terraform engineer",

]

TOO_JUNIOR = ["intern", "internship", "junior", "entry level", "graduate", "trainee"]
TOO_SENIOR = ["principal", "staff", "architect", "director", "head of", "vp ", "vice president"]


def is_relevant(title):
    return any(keyword in title.lower() for keyword in KEYWORDS)


def fits_experience(title):
    title = title.lower()

    if any(term in title for term in TOO_JUNIOR):
        return False

    if any(term in title for term in TOO_SENIOR):
        return False

    return True


def is_within_experience_limit(text):
    if not text:
        return True

    numbers = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", text.lower())

    return all(float(number) <= MAX_EXPERIENCE_YEARS for number in numbers)


def clean_description(value):
    if not value:
        return ""

    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def parse_job_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_recent(posted_at):
    if not posted_at:
        return False

    now = datetime.now(timezone.utc)

    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    return now - timedelta(hours=LOOKBACK_HOURS) <= posted_at <= now


def fetch_remoteok():
    url = "https://remoteok.com/api"
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    data = res.json()

    jobs = []

    for job in data:
        if not isinstance(job, dict):
            continue

        title = job.get("position")
        company = job.get("company")
        link = job.get("url")
        posted_at = parse_job_date(job.get("date"))
        description = clean_description(job.get("description"))

        if (
            title
            and company
            and link
            and is_relevant(title)
            and fits_experience(title)
            and is_within_experience_limit(f"{title} {description}")
            and is_recent(posted_at)
        ):
            jobs.append({
                "title": title,
                "company": company,
                "link": link,
                "source": "RemoteOK",
                "posted_at": posted_at,
            })

    return jobs


def fetch_wwr():
    url = "https://weworkremotely.com/remote-jobs/search?term=devops"
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    jobs = []

    for job in soup.select("li"):
        title = job.select_one(".title")
        company = job.select_one(".company")
        link = job.find("a", href=True)
        time_tag = job.find("time")

        if not title or not company or not link or not time_tag:
            continue

        title_text = title.text.strip()
        listing_text = job.get_text(" ", strip=True)
        posted_at = parse_job_date(time_tag.get("datetime"))

        if is_relevant(title_text) and fits_experience(title_text) and is_within_experience_limit(listing_text) and is_recent(posted_at):
            jobs.append({
                "title": title_text,
                "company": company.text.strip(),
                "link": "https://weworkremotely.com" + link["href"],
                "source": "WeWorkRemotely",
                "posted_at": posted_at,
            })

    return jobs


def merge_jobs(*job_lists):
    seen = set()
    result = []

    for jobs in job_lists:
        for job in jobs:
            key = (job["title"].lower(), job["company"].lower())
            if key not in seen:
                seen.add(key)
                result.append(job)

    return sorted(result, key=lambda job: job["posted_at"], reverse=True)


def generate_pdf(jobs):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, f"DevOps / SRE Jobs - {EXPERIENCE_YEARS} yrs - Max {MAX_EXPERIENCE_YEARS} yrs - Last {LOOKBACK_HOURS} hours", ln=True)

    for i, job in enumerate(jobs, 1):
        pdf.multi_cell(0, 8, f"{i}. {job['title']} - {job['company']}")
        pdf.multi_cell(0, 8, f"Source: {job['source']} | Posted: {job['posted_at'].strftime('%Y-%m-%d %H:%M UTC')}")
        pdf.multi_cell(0, 8, job["link"])
        pdf.ln(3)

    file = f"jobs/jobs_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    pdf.output(file)

    print("PDF Created:", file)


if __name__ == "__main__":
    print("Fetching jobs...")
    print(f"Filters: {EXPERIENCE_YEARS} years experience, max {MAX_EXPERIENCE_YEARS} years required, posted in the last {LOOKBACK_HOURS} hours")

    r1 = fetch_remoteok()
    print("RemoteOK:", len(r1))

    try:
        r2 = fetch_wwr()
        print("WeWorkRemotely:", len(r2))
    except requests.RequestException as e:
        r2 = []
        print("WeWorkRemotely skipped:", e)

    all_jobs = merge_jobs(r1, r2)
    print("Total:", len(all_jobs))

    if all_jobs:
        generate_pdf(all_jobs)
    else:
        print("No jobs found")
