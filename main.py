import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
from datetime import datetime
import os

os.makedirs("jobs", exist_ok=True)

# -------------------------
# KEYWORDS
# -------------------------
KEYWORDS = ["devops", "platform engineer", "site reliability", "sre"]
REMOTEOK_API_URL = "https://remoteok.com/api?tag=devops"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

# -------------------------
# FILTER FUNCTION
# -------------------------
def is_relevant(title):
    title = title.lower()
    return any(k in title for k in KEYWORDS)

# -------------------------
# FETCH INDEED
# -------------------------
def fetch_indeed():
    print("Fetching Indeed jobs...")
    jobs = []

    try:
        url = "https://www.indeed.com/jobs?q=devops&l=Bangalore"
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 403:
            print("Indeed skipped: returned 403 security check")
            print(f"Indeed jobs: {len(jobs)}")
            return jobs

        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for job in soup.select(".job_seen_beacon")[:10]:
            title = job.select_one("h2 span")
            company = job.select_one(".companyName")
            link = job.select_one("a")

            if title and company and link:
                job_title = title.text.strip()

                if is_relevant(job_title):
                    jobs.append({
                        "title": job_title,
                        "company": company.text.strip(),
                        "link": "https://www.indeed.com" + link.get("href")
                    })

    except Exception as e:
        print("Indeed Error:", e)

    print(f"Indeed jobs: {len(jobs)}")
    return jobs


# -------------------------
# FETCH REMOTEOK
# -------------------------
def fetch_remoteok():
    print("Fetching RemoteOK jobs...")
    jobs = []

    try:
        res = requests.get(REMOTEOK_API_URL, headers=HEADERS, timeout=20)
        res.raise_for_status()

        for job in res.json():
            if not isinstance(job, dict):
                continue

            title = job.get("position")
            company = job.get("company")
            link = job.get("url")
            tags = job.get("tags") or []
            haystack = " ".join([title or "", *tags])

            if title and company and link and is_relevant(haystack):
                jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "link": link
                })

            if len(jobs) == 10:
                break

    except Exception as e:
        print("RemoteOK Error:", e)

    print(f"RemoteOK jobs: {len(jobs)}")
    return jobs


# -------------------------
# MERGE + DEDUP
# -------------------------
def merge_jobs(*lists):
    unique = []
    seen = set()

    for job_list in lists:
        for job in job_list:
            key = job["title"] + job["company"]
            if key not in seen:
                seen.add(key)
                unique.append(job)

    print(f"Total jobs after merge: {len(unique)}")
    return unique


# -------------------------
# GENERATE PDF
# -------------------------
def generate_pdf(jobs):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    pdf.cell(200, 10, txt="DevOps / Platform / SRE Jobs", ln=True)
    pdf.cell(200, 10, txt=f"Generated on: {today}", ln=True)
    pdf.ln(5)

    if not jobs:
        pdf.cell(200, 10, txt="No jobs found today", ln=True)
    else:
        for i, job in enumerate(jobs, 1):
            pdf.multi_cell(0, 10, txt=f"{i}. {job['title']} - {job['company']}")
            pdf.multi_cell(0, 10, txt=f"Link: {job['link']}")
            pdf.ln(3)

    filename = f"jobs/jobs_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.pdf"
    pdf.output(filename)

    print(f"PDF Generated: {filename}")


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    print("Starting job automation...")

    indeed = fetch_indeed()
    remote = fetch_remoteok()

    all_jobs = merge_jobs(indeed, remote)

    generate_pdf(all_jobs)

    print("Job automation completed.")
