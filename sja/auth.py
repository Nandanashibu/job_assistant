"""Sign up and log in. Passwords are never stored; only a salted hash is.

hashlib.pbkdf2_hmac runs SHA-256 many times over password + random salt, so even
if someone copies the database they cannot read the passwords back.
"""
import hashlib
import hmac
import re
import secrets

from sja import database as db

ITERATIONS = 200_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return digest.hex(), salt


def sign_up(email, name, password, role, company=""):
    """Return (user_id, None) on success or (None, error message)."""
    if not re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", email or ""):
        return None, "Enter a valid email address."
    if len(password or "") < 8:
        return None, "Password must be at least 8 characters."
    if role not in ("seeker", "recruiter"):
        return None, "Choose job seeker or recruiter."
    if role == "recruiter" and not company.strip():
        return None, "Recruiters must enter their company name."
    if db.get_user_by_email(email):
        return None, "An account with this email already exists. Log in instead."
    password_hash, salt = hash_password(password)
    return db.create_user(email, name or email.split("@")[0], role, password_hash, salt, company), None


def log_in(email, password):
    """Return the user dict if the email and password are right, otherwise None."""
    user = db.get_user_by_email(email or "")
    if not user:
        return None
    attempt, _ = hash_password(password or "", user["salt"])
    return user if hmac.compare_digest(attempt, user["password_hash"]) else None
