"""All settings for Smart Job Assistant live here. Change values here, not inside the modules."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file():
    """Read KEY=VALUE lines from a .env file (keeps passwords out of the code)."""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

# ---------------------------------------------------------------- folders and files
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"          # resumes uploaded through the website
OUTBOX_DIR = DATA_DIR / "outbox"           # copies of every email (.eml files)
MODEL_DIR = BASE_DIR / "models"
TEMPLATE_DIR = BASE_DIR / "templates"

DB_PATH = DATA_DIR / "jobs.db"
SKILLS_FILE = DATA_DIR / "skills.json"
SAMPLE_JOBS_FILE = DATA_DIR / "sample_jobs.json"
PROJECT_IDEAS_FILE = DATA_DIR / "project_ideas.json"
FAKE_MODEL_FILE = MODEL_DIR / "fake_job_model.joblib"

for _folder in (UPLOAD_DIR, OUTBOX_DIR, MODEL_DIR):
    _folder.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- applying
AUTO_APPLY_MIN_MATCH = 80        # auto-apply only at or above this match %
SHOW_MIN_MATCH = 30              # hide jobs below this match % in the feed
MAX_APPLICATIONS_PER_DAY = 10    # safety cap per user per day

# ---------------------------------------------------------------- email
# EMAIL_DRY_RUN=true  -> emails are NOT sent; they are saved in data/outbox as .eml files
# EMAIL_DRY_RUN=false -> emails are really sent through Gmail (set the values in .env)
EMAIL_DRY_RUN = os.getenv("EMAIL_DRY_RUN", "true").lower() != "false"
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")                    # your Gmail address
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")    # a Gmail App Password, not your normal password

# ---------------------------------------------------------------- job collection
# Be polite: say who you are, go slowly, respect robots.txt, collect at most once a day.
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "your-email@example.com")
USER_AGENT = f"SmartJobAssistant/1.0 (student project; contact: {CONTACT_EMAIL})"
REQUEST_DELAY_SECONDS = 3
REQUEST_TIMEOUT_SECONDS = 20
MAX_PAGES_PER_SOURCE = 40

# The park websites can change their layout. If collection finds 0 jobs,
# open the listing page in your browser and update these two values.
INFOPARK = {
    "name": "Infopark",
    "list_url": "https://infopark.in/company-jobs",
    "job_link_pattern": r"/company-jobs/\d+",
    "location": "Infopark, Kochi",
}
TECHNOPARK = {
    "name": "Technopark",
    "list_url": "https://technopark.org/job-search",
    "job_link_pattern": r"/job-details/\d+",
    "location": "Technopark, Thiruvananthapuram",
}
REMOTIVE_API = "https://remotive.com/api/remote-jobs"

# ---------------------------------------------------------------- matching
WEIGHT_SKILLS = 0.55       # share of required skills the candidate has
WEIGHT_TEXT = 0.30         # TF-IDF similarity between resume and job text
WEIGHT_EXPERIENCE = 0.15   # candidate years vs years the job asks for
ROLE_BONUS = 5             # extra points when the job title matches a preferred role

# ---------------------------------------------------------------- fake job detection
FAKE_HIGH = 50             # risk score at or above this = High (hidden, never auto-applied)
FAKE_MEDIUM = 25
