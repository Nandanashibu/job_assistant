"""Demo data: sample jobs + demo accounts (password demo1234).

Used by scripts/seed_demo.py, and automatically by app.py when the database is empty
(for example the first time the app starts on a hosting service, where files reset on restart).
"""
import shutil

import config
from sja import applier, auth, database as db
from sja.ats import full_ats
from sja.collector import collect_all
from sja.job_tools import build_job
from sja.resume_parser import parse_resume

SEEKERS = [
    ("ananya@demo.com", "Ananya Menon", "data_analyst_resume.pdf", "Data Analyst", "Kochi, Thiruvananthapuram", 1),
    ("rahul@demo.com", "Rahul Nair", "ros_engineer_resume.pdf", "Robotics Engineer", "Thiruvananthapuram", 0),
    ("fathima@demo.com", "Fathima Rasheed", "python_developer_fresher_resume.pdf", "Python Developer", "Kozhikode, Kochi", 0),
]


def seed(log=print):
    db.init_db()
    log("\n".join(collect_all(["sample"])[1]))
    for email, name, resume, roles, locations, auto in SEEKERS:
        source = config.DATA_DIR / resume
        if not source.exists():
            log(f"Skipping {name}: {resume} not found in data/")
            continue
        auth.sign_up(email, name, "demo1234", "seeker")
        user = db.get_user_by_email(email)
        target = config.UPLOAD_DIR / f"user{user['id']}_{resume}"
        shutil.copy(source, target)
        parsed = parse_resume(target)
        db.save_profile(user["id"], resume_path=str(target), parsed_json=parsed,
                        ats_score=full_ats(parsed, target, db.active_jobs(), [roles])["score"],
                        phone=parsed["phone"], linkedin_url=parsed["linkedin"], github_url=parsed["github"],
                        preferred_roles=roles, locations=locations, remote_ok=1, auto_apply=auto, min_salary_lpa=0)
        log(f"Seeker ready: {email}")
    auth.sign_up("hr@demo.com", "Priya HR", "demo1234", "recruiter", "Demo Analytics Pvt Ltd")
    recruiter = db.get_user_by_email("hr@demo.com")
    db.save_job(build_job("Data Analyst (Python, SQL, Power BI)", recruiter["company"],
                          "We need a Data Analyst with 1-3 years experience in SQL, Python, Pandas and Power BI. "
                          "You will build dashboards, clean data and present insights to business teams. "
                          "Excel and statistics knowledge expected.\nWhat is your notice period?",
                          source="Posted in app", location="Infopark, Kochi", posted_by=recruiter["id"], salary_text="5-7 LPA"))
    log("Recruiter ready: hr@demo.com (1 job posted)")
    log("\n".join(applier.auto_apply_everyone()) or "Auto-apply: nothing.")


def seed_if_empty():
    """Fill an empty database with demo data. Returns True if it seeded."""
    db.init_db()
    with db.connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return False
    seed(log=lambda *_: None)
    return True
