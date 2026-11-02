"""Turn a raw job (from a website, an API or a recruiter) into a clean, checked job record."""
import hashlib
import re
from datetime import datetime

from sja.fake_detector import check_job
from sja.skills import find_skills

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s*\d{1,2})?\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
DATE_PATTERNS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"]


def make_id(title, company, url=""):
    key = f"{title.lower().strip()}|{company.lower().strip()}|{url.strip()}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def find_apply_email(text):
    """The HR email in the listing, skipping obvious no-reply addresses."""
    for email in EMAIL.findall(text or ""):
        email = email.rstrip(".")
        if not re.match(r"(no-?reply|donotreply)", email, re.IGNORECASE):
            return email
    return ""


def required_years(text):
    """Smallest 'N years' mentioned near the word experience (0 for fresher roles)."""
    low = (text or "").lower()
    if re.search(r"\b(fresher|freshers|entry[- ]level|0\s*-\s*\d\s*years?)\b", low):
        return 0.0
    years = []
    for m in YEARS.finditer(low):
        window = low[max(0, m.start() - 60): m.end() + 60]
        if "experience" in window or "exp" in window:
            n = int(m.group(1))
            if n <= 20:
                years.append(n)
    return float(min(years)) if years else 0.0


def find_questions(text):
    """Extra questions the employer wants answered (e.g. 'What is your notice period?')."""
    questions = []
    for line in (text or "").splitlines():
        line = line.strip(" -•*\t")
        if line.endswith("?") and 15 <= len(line) <= 200:
            questions.append(line)
    return questions[:10]


def parse_salary_lpa(text):
    """'4-6 LPA', '₹30,000/month' -> (min, max) in lakhs per year, or (None, None)."""
    t = (text or "").lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)?\s*(lpa|lakhs?|lacs?)", t)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        return lo, hi
    m = re.search(r"(?:₹|rs\.?|inr)\s*(\d{4,6})\s*(?:-|to)?\s*(?:₹|rs\.?|inr)?\s*(\d{4,6})?\s*(?:/|per)\s*month", t)
    if m:
        lo = float(m.group(1)) * 12 / 100000
        hi = float(m.group(2)) * 12 / 100000 if m.group(2) else lo
        return round(lo, 1), round(hi, 1)
    return None, None


def find_closing_date(text):
    m = re.search(r"(?:last date|closing date|apply before|apply by|deadline)\s*[:\-]?\s*([0-9A-Za-z ,/\-]{6,20})",
                  text or "", re.IGNORECASE)
    if not m:
        return ""
    raw = m.group(1).strip().rstrip(".")
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def build_job(title, company, description, source, url="", location="", remote=None, apply_email="",
              posted_by=None, salary_text="", closing_date="", created_at=None):
    """Return a job dict ready for database.save_job()."""
    text = f"{title}\n{description}"
    lo, hi = parse_salary_lpa(f"{salary_text} {description}")
    apply_email = apply_email or find_apply_email(description)
    risk, risk_level, reasons = check_job(title, company, description, apply_email)
    is_remote = remote if remote is not None else bool(
        re.search(r"\b(remote|work from home|wfh)\b", f"{title} {location} {description}", re.IGNORECASE))
    job = {
        "id": make_id(title, company, url),
        "title": title.strip(),
        "company": (company or "").strip(),
        "location": location.strip(),
        "remote": 1 if is_remote else 0,
        "description": description.strip(),
        "url": url,
        "apply_email": apply_email,
        "source": source,
        "posted_by": posted_by,
        "salary_min_lpa": lo,
        "salary_max_lpa": hi,
        "closing_date": closing_date or find_closing_date(description),
        "skills": find_skills(text),
        "min_years": required_years(description),
        "questions": find_questions(description),
        "fake_risk": risk,
        "fake_level": risk_level,
        "fake_reasons": reasons,
        "active": 1,
    }
    if created_at:
        job["created_at"] = created_at
    return job
