"""Fake / scam job detection.

Layer 1 - rules (always on): red flags common in scams aimed at freshers in India,
          e.g. registration fees, WhatsApp-only contact, asking for Aadhaar or OTP.
Layer 2 - machine learning (optional): run scripts/train_fake_model.py once on the
          public EMSCAD dataset. If models/fake_job_model.joblib exists, its
          prediction is blended with the rule score.
"""
import re
from functools import lru_cache

import config

# (pattern, points, reason shown to the user)
RULES = [
    (r"(registration|joining|processing|training|security|refundable|onboarding|kit)\s*(fee|charge|deposit|amount)",
     45, "Asks for a fee or deposit. Genuine employers never charge you to get a job."),
    (r"\b(pay|deposit|transfer)\b.{0,40}\b(rs\.?|₹|inr|amount|fee)", 35, "Mentions paying money as part of hiring."),
    (r"\b(upi|google pay|gpay|phonepe|paytm)\b", 25, "Mentions UPI or payment apps."),
    (r"\b(whats\s?app|telegram)\b", 20, "Asks you to contact the recruiter on WhatsApp or Telegram."),
    (r"\b(bank (account|details)|account number|ifsc|otp|aadha+r|pan card|cvv)\b", 30,
     "Asks for bank, OTP or ID details."),
    (r"\b(earn|income)\b.{0,30}\d[\d,]*\s*(per|a|/)\s*(day|week)\b", 25, "Promises big daily or weekly earnings."),
    (r"\bno (interview|experience|skills?) (required|needed)\b", 15, "Says no interview or experience is needed."),
    (r"\b(guaranteed|100%)\s*(job|placement|selection|income)\b", 25, "Guarantees a job or income."),
    (r"\b(limited seats|urgent(ly)? hiring|immediate joining|hurry)\b", 10, "Uses pressure words (urgent, limited seats)."),
    (r"\b(data entry|typing|form filling|copy paste|captcha)\b.{0,60}\b(home|daily|part[- ]time)\b",
     15, "Looks like a 'work from home typing job' scam."),
    (r"\b(bit\.ly|tinyurl|t\.me|wa\.me)/", 15, "Uses short links or chat links instead of a company website."),
    (r"\b(mlm|network marketing|refer and earn|investment required)\b", 25, "Looks like MLM or an investment scheme."),
]
FREE_EMAIL = re.compile(r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|rediffmail)\.com", re.IGNORECASE)


def level(risk):
    if risk >= config.FAKE_HIGH:
        return "High"
    if risk >= config.FAKE_MEDIUM:
        return "Medium"
    return "Low"


@lru_cache(maxsize=1)
def _model():
    """Load the trained model once. Returns (pipeline, threshold) or None if not trained yet."""
    if not config.FAKE_MODEL_FILE.exists():
        return None
    try:
        import joblib
        saved = joblib.load(config.FAKE_MODEL_FILE)
        if isinstance(saved, dict):
            return saved["model"], saved.get("threshold", 0.5)
        return saved, 0.5
    except Exception:
        return None


def suspicious_words(text, top=5):
    """The words that pushed the ML model most towards 'fake' (explains the prediction)."""
    loaded = _model()
    if not loaded:
        return []
    pipeline = loaded[0]
    try:
        words = pipeline.named_steps["features"].transformer_list[0][1]
        coefs = pipeline.named_steps["clf"].coef_[0][: len(words.vocabulary_)]
        row = words.transform([text]).tocoo()
        contrib = sorted(((v * coefs[c], c) for c, v in zip(row.col, row.data)), reverse=True)
        names = words.get_feature_names_out()
        return [names[c] for score, c in contrib[:top] if score > 0]
    except Exception:
        return []


def ml_probability(title, company, description):
    loaded = _model()
    if not loaded:
        return None
    return float(loaded[0].predict_proba([f"{title}. {description}"])[0][1])


def check_job(title, company, description, apply_email=""):
    """Return (risk 0-100, level, list of reasons). Rules and the ML model are combined:
    the higher of the two risks wins, so a scam caught by either one is flagged."""
    text = f"{title}\n{description}".lower()
    risk, reasons = 0, []
    for pattern, points, reason in RULES:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            risk += points
            reasons.append(reason)
    if FREE_EMAIL.search(f"{description} {apply_email}"):
        risk += 15
        reasons.append("Recruiter uses a free email (gmail, yahoo) instead of a company email.")
    if not company or company.strip().lower() in {"confidential", "n/a", "company", "hiring company"}:
        risk += 15
        reasons.append("Company name is missing or hidden.")
    if len(description or "") < 200:
        risk += 10
        reasons.append("Very short, vague description.")
    risk = min(risk, 100)

    probability = ml_probability(title, company, description)
    if probability is not None:
        threshold = _model()[1]
        ml_risk = int(round(probability * 100))
        if probability >= threshold:
            words = suspicious_words(f"{title}. {description}")
            reasons.append(f"The trained model rates this {ml_risk}% likely to be fake"
                           + (f" (suspicious words: {', '.join(words)})." if words else "."))
            risk = max(risk, ml_risk, config.FAKE_HIGH)     # above the model's threshold = High
        elif probability >= 0.35:
            reasons.append(f"The trained model finds some unusual wording ({ml_risk}% likely fake). Check the company.")
            risk = max(risk, config.FAKE_MEDIUM)
    return risk, level(risk), reasons
