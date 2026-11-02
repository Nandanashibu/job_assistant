"""SQLite storage: users, profiles, jobs, applications, emails.

SQLite is a database stored in ONE file (data/jobs.db). Python has it built in,
so there is nothing to install. Every function opens a short connection, does its
work and closes it.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('seeker', 'recruiter')),
    company       TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id          INTEGER PRIMARY KEY REFERENCES users(id),
    resume_path      TEXT DEFAULT '',
    parsed_json      TEXT DEFAULT '{}',   -- output of parse_resume()
    ats_score        INTEGER DEFAULT 0,
    phone            TEXT DEFAULT '',
    linkedin_url     TEXT DEFAULT '',
    naukri_url       TEXT DEFAULT '',
    github_url       TEXT DEFAULT '',
    preferred_roles  TEXT DEFAULT '',     -- comma separated
    locations        TEXT DEFAULT '',     -- comma separated
    remote_ok        INTEGER DEFAULT 1,
    willing_to_relocate INTEGER DEFAULT 0,
    min_salary_lpa   REAL DEFAULT 0,
    auto_apply       INTEGER DEFAULT 0,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    company       TEXT DEFAULT '',
    location      TEXT DEFAULT '',
    remote        INTEGER DEFAULT 0,
    description   TEXT DEFAULT '',
    url           TEXT DEFAULT '',
    apply_email   TEXT DEFAULT '',
    source        TEXT DEFAULT '',
    posted_by     INTEGER REFERENCES users(id),   -- set when a recruiter posts in the app
    salary_min_lpa REAL,
    salary_max_lpa REAL,
    closing_date  TEXT DEFAULT '',
    skills_json   TEXT DEFAULT '[]',
    min_years     REAL DEFAULT 0,
    questions_json TEXT DEFAULT '[]',
    fake_risk     INTEGER DEFAULT 0,
    fake_level    TEXT DEFAULT 'Low',
    fake_reasons  TEXT DEFAULT '[]',
    active        INTEGER DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT NOT NULL REFERENCES jobs(id),
    user_id      INTEGER NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL,      -- Applied, Needs your answers, Open link, Shortlisted, Interview, Offer, Rejected
    match_score  REAL DEFAULT 0,
    method       TEXT DEFAULT '',    -- email, in-app, manual
    auto         INTEGER DEFAULT 0,  -- 1 = applied by auto-apply
    cover_letter TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    applied_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (job_id, user_id)          -- never apply twice to the same job
);

CREATE TABLE IF NOT EXISTS emails (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    to_addr    TEXT,
    subject    TEXT,
    body       TEXT,
    attachment TEXT DEFAULT '',
    status     TEXT,                 -- saved (dry run), sent, failed
    created_at TEXT NOT NULL
);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dictionaries
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def _rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


# ------------------------------------------------------------------ users
def create_user(email, name, role, password_hash, salt, company=""):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, name, role, company, password_hash, salt, created_at) VALUES (?,?,?,?,?,?,?)",
            (email.lower().strip(), name.strip(), role, company.strip(), password_hash, salt, now()))
        return cur.lastrowid


def get_user_by_email(email):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_user(user_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def all_seekers():
    with connect() as conn:
        return _rows(conn.execute("SELECT * FROM users WHERE role = 'seeker'"))


# ------------------------------------------------------------------ profiles
PROFILE_FIELDS = ["resume_path", "parsed_json", "ats_score", "phone", "linkedin_url", "naukri_url",
                  "github_url", "preferred_roles", "locations", "remote_ok", "willing_to_relocate",
                  "min_salary_lpa", "auto_apply"]


def save_profile(user_id, **fields):
    fields = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
    if isinstance(fields.get("parsed_json"), dict):
        fields["parsed_json"] = json.dumps(fields["parsed_json"])
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO profiles (user_id, updated_at) VALUES (?, ?)", (user_id, now()))
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE profiles SET {sets}, updated_at = ? WHERE user_id = ?",
                         (*fields.values(), now(), user_id))


def get_profile(user_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    profile = dict(row)
    profile["parsed"] = json.loads(profile.get("parsed_json") or "{}")
    return profile


# ------------------------------------------------------------------ jobs
def save_job(job):
    """Insert a job, or update it if the same id already exists. Returns True if it was new."""
    job = dict(job)
    for key in ("skills", "questions", "fake_reasons"):
        if key in job and not isinstance(job[key], str):
            job[f"{key}_json" if key != "fake_reasons" else key] = json.dumps(job.pop(key))
    columns = ["id", "title", "company", "location", "remote", "description", "url", "apply_email", "source",
               "posted_by", "salary_min_lpa", "salary_max_lpa", "closing_date", "skills_json", "min_years",
               "questions_json", "fake_risk", "fake_level", "fake_reasons", "active", "created_at"]
    job.setdefault("created_at", now())
    values = {c: job.get(c) for c in columns if c in job}
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job["id"],)).fetchone()
        if exists:
            values.pop("created_at", None)
            sets = ", ".join(f"{k} = ?" for k in values if k != "id")
            conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?",
                         (*[v for k, v in values.items() if k != "id"], job["id"]))
            return False
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({marks})", tuple(values.values()))
        return True


def _decode_job(row):
    job = dict(row)
    job["skills"] = json.loads(job.pop("skills_json") or "[]")
    job["questions"] = json.loads(job.pop("questions_json") or "[]")
    job["fake_reasons"] = json.loads(job.get("fake_reasons") or "[]")
    return job


def get_job(job_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _decode_job(row) if row else None


def active_jobs():
    """Open jobs: active and not past their closing date."""
    today = date.today().isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE active = 1 AND (closing_date = '' OR closing_date IS NULL OR closing_date >= ?) "
            "ORDER BY created_at DESC", (today,)).fetchall()
    return [_decode_job(r) for r in rows]


def all_jobs():
    with connect() as conn:
        return [_decode_job(r) for r in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()]


def jobs_posted_by(user_id):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE posted_by = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [_decode_job(r) for r in rows]


def set_job_active(job_id, active):
    with connect() as conn:
        conn.execute("UPDATE jobs SET active = ? WHERE id = ?", (1 if active else 0, job_id))


# ------------------------------------------------------------------ applications
def get_application(job_id, user_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE job_id = ? AND user_id = ?", (job_id, user_id)).fetchone()
        return dict(row) if row else None


def add_application(job_id, user_id, status, match_score, method, auto=False, cover_letter="", notes=""):
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO applications (job_id, user_id, status, match_score, method, auto, cover_letter, notes, "
            "applied_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, user_id, status, match_score, method, 1 if auto else 0, cover_letter, notes, now(), now()))


def delete_application(app_id):
    with connect() as conn:
        conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))


def update_application_status(app_id, status, notes=None):
    with connect() as conn:
        if notes is None:
            conn.execute("UPDATE applications SET status = ?, updated_at = ? WHERE id = ?", (status, now(), app_id))
        else:
            conn.execute("UPDATE applications SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                         (status, notes, now(), app_id))


def applications_for_user(user_id):
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT a.*, j.title, j.company, j.location, j.url, j.apply_email FROM applications a "
            "JOIN jobs j ON j.id = a.job_id WHERE a.user_id = ? ORDER BY a.applied_at DESC", (user_id,)))


def applications_for_job(job_id):
    with connect() as conn:
        return _rows(conn.execute(
            "SELECT a.*, u.name, u.email FROM applications a JOIN users u ON u.id = a.user_id "
            "WHERE a.job_id = ? ORDER BY a.match_score DESC", (job_id,)))


def applications_today(user_id):
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM applications WHERE user_id = ? AND applied_at LIKE ? "
                           "AND method != 'manual'", (user_id, date.today().isoformat() + "%")).fetchone()
        return row[0]


# ------------------------------------------------------------------ emails
def log_email(user_id, to_addr, subject, body, attachment, status):
    with connect() as conn:
        conn.execute("INSERT INTO emails (user_id, to_addr, subject, body, attachment, status, created_at) "
                     "VALUES (?,?,?,?,?,?,?)", (user_id, to_addr, subject, body, attachment, status, now()))


def emails_for_user(user_id, limit=50):
    with connect() as conn:
        return _rows(conn.execute("SELECT * FROM emails WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)))
