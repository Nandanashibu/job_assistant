"""Collect jobs from Infopark, Technopark, a public API and the offline sample file.

Rules followed (explain these in your viva):
  * Identify the bot with a User-Agent that includes a contact email.
  * Check robots.txt before reading any page; skip pages it disallows.
  * Wait a few seconds between requests and cap the number of pages.
  * Read only public listings; never log in or get around any protection.
  * Run at most once a day (scripts/collect_jobs.py or the scheduler).
"""
import json
import re
import time
from datetime import datetime, timedelta
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config
from sja import database as db
from sja.job_tools import build_job, find_apply_email

ROLE_WORDS = re.compile(
    r"\b(engineer|developer|programmer|tester|analyst|architect|designer|manager|executive|lead|intern|"
    r"trainee|consultant|administrator|admin|specialist|scientist|associate|officer|coordinator|"
    r"accountant|writer|support|devops|qa)s?\b", re.IGNORECASE)


class PoliteSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.last_request = 0.0
        self.robots = {}

    def allowed(self, url):
        root = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if root not in self.robots:
            parser = robotparser.RobotFileParser()
            try:
                r = self.session.get(root + "/robots.txt", timeout=config.REQUEST_TIMEOUT_SECONDS)
                parser.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                parser.parse([])
            self.robots[root] = parser
        return self.robots[root].can_fetch(config.USER_AGENT, url)

    def get(self, url, **kwargs):
        if not self.allowed(url):
            raise PermissionError(f"robots.txt does not allow {url}")
        wait = config.REQUEST_DELAY_SECONDS - (time.time() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.time()
        response = self.session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS, **kwargs)
        response.raise_for_status()
        return response


# ---------------------------------------------------------------------------
# IT park career pages (Infopark, Technopark)
# ---------------------------------------------------------------------------
def page_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    main = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [re.sub(r"\s+", " ", l).strip() for l in main.get_text("\n").splitlines()]
    return title, [l for l in lines if l]


def looks_like_title(line):
    return (5 <= len(line) <= 90 and ROLE_WORDS.search(line) and not line.endswith(".")
            and len(line.split()) <= 12 and "@" not in line)


def split_openings(lines):
    """A park page may list several openings. Split the text at lines that look like job titles."""
    starts = [i for i, l in enumerate(lines) if looks_like_title(l)]
    openings = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[start + 1:end]
        if len(" ".join(body)) >= 80:              # skip headings with almost no text under them
            openings.append((lines[start], "\n".join(body)))
    return openings


def guess_company(page_title, lines, park_name):
    for line in lines[:15]:
        m = re.match(r"(?:company|company name|organisation)\s*[:\-]\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    for line in lines[:8]:
        if re.search(r"\b(pvt|private|ltd|limited|technologies|solutions|systems|software|labs|inc)\b", line, re.I):
            return line[:80]
    name = re.split(r"\s[|\-–]\s", page_title)[0].strip()
    return name if name and park_name.lower() not in name.lower() else ""


def collect_from_park(park, http, log):
    listing = http.get(park["list_url"])
    pattern = re.compile(park["job_link_pattern"])
    links, pages = [], [park["list_url"]]
    soup = BeautifulSoup(listing.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(park["list_url"], a["href"])
        if pattern.search(href) and href not in links:
            links.append(href)
        elif re.search(r"[?&]page=\d+", href) and href not in pages and len(pages) < 5:
            pages.append(href)
    for page_url in pages[1:]:                          # a few more listing pages
        try:
            more = BeautifulSoup(http.get(page_url).text, "html.parser")
            for a in more.find_all("a", href=True):
                href = urljoin(page_url, a["href"])
                if pattern.search(href) and href not in links:
                    links.append(href)
        except Exception as exc:
            log.append(f"{park['name']}: listing page failed ({exc})")

    jobs = []
    for url in links[:config.MAX_PAGES_PER_SOURCE]:
        try:
            page_title, lines = page_lines(http.get(url).text)
        except Exception as exc:
            log.append(f"{park['name']}: {url} skipped ({exc})")
            continue
        company = guess_company(page_title, lines, park["name"])
        page_email = find_apply_email("\n".join(lines))
        openings = split_openings(lines) or [(page_title or "Job opening", "\n".join(lines))]
        for title, body in openings:
            jobs.append(build_job(title, company, body, source=park["name"], url=url, location=park["location"],
                                  apply_email=find_apply_email(body) or page_email))
    log.append(f"{park['name']}: {len(links)} job pages found, {len(jobs)} openings read")
    return jobs


# ---------------------------------------------------------------------------
# Public API and offline sample
# ---------------------------------------------------------------------------
def collect_from_remotive(http, log, search="", limit=50):
    params = {"limit": limit}
    if search:
        params["search"] = search
    data = http.get(config.REMOTIVE_API, params=params).json()
    jobs = []
    for j in data.get("jobs", []):
        description = BeautifulSoup(j.get("description", ""), "html.parser").get_text("\n")
        jobs.append(build_job(j.get("title", ""), j.get("company_name", ""), description, source="Remotive",
                              url=j.get("url", ""), location=j.get("candidate_required_location", "Remote"),
                              remote=True, salary_text=j.get("salary", "")))
    log.append(f"Remotive: {len(jobs)} jobs")
    return jobs


def collect_from_sample(log):
    """Offline demo jobs from data/sample_jobs.json, spread over the last few weeks."""
    with open(config.SAMPLE_JOBS_FILE, encoding="utf-8") as f:
        items = json.load(f)
    jobs = []
    for item in items:
        created = (datetime.now() - timedelta(days=item.get("days_ago", 0))).isoformat(timespec="seconds")
        closing = item.get("closing_date", "")
        if "closes_in_days" in item:
            closing = (datetime.now() + timedelta(days=item["closes_in_days"])).date().isoformat()
        jobs.append(build_job(item["title"], item["company"], item["description"], source=item.get("source", "Sample"),
                              url=item.get("url", ""), location=item.get("location", ""),
                              apply_email=item.get("apply_email", ""), salary_text=item.get("salary", ""),
                              closing_date=closing, created_at=created))
    log.append(f"Sample: {len(jobs)} jobs")
    return jobs


def collect_all(sources=("sample",), remotive_search=""):
    """Run the chosen sources, save new jobs, return (number of new jobs, log lines).
    sources: any of 'sample', 'infopark', 'technopark', 'remotive'."""
    db.init_db()
    http, log, jobs = PoliteSession(), [], []
    tasks = {
        "sample": lambda: collect_from_sample(log),
        "infopark": lambda: collect_from_park(config.INFOPARK, http, log),
        "technopark": lambda: collect_from_park(config.TECHNOPARK, http, log),
        "remotive": lambda: collect_from_remotive(http, log, remotive_search),
    }
    for name in sources:
        try:
            jobs += tasks[name]()
        except Exception as exc:                 # one broken source must not stop the others
            log.append(f"{name}: failed ({exc})")
    new = sum(1 for job in jobs if job["title"] and db.save_job(job))
    log.append(f"Saved {new} new jobs ({len(jobs)} collected).")
    return new, log
