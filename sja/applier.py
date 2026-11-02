"""Cover letters, applying (manual and auto) and notifications.

How an application is sent depends on the job:
  * posted inside this app by a recruiter -> saved straight to the database (one click)
  * listing gives an HR email (most Infopark/Technopark jobs) -> email with cover letter + resume
  * only a link to a company site -> marked 'Open link'; you apply on that site yourself

Auto-apply safety rules (all must pass):
  match >= AUTO_APPLY_MIN_MATCH, fake risk not High, not applied before, not past the
  closing date, under MAX_APPLICATIONS_PER_DAY, and the job has no extra questions
  (if it does, the questions are emailed to you to answer first).
"""
from jinja2 import Environment, FileSystemLoader

import config
from sja import database as db
from sja.emailer import send_email
from sja.matcher import passes_preferences, rank_jobs

_env = Environment(loader=FileSystemLoader(str(config.TEMPLATE_DIR)), trim_blocks=True, lstrip_blocks=True)


def write_cover_letter(user, parsed, job, result=None, learning=()):
    matched = (result or {}).get("matched_skills") or [s for s in job.get("skills", []) if s in parsed.get("skills", [])]
    other = [s for s in parsed.get("skills", []) if s not in matched][:3]
    education = parsed.get("education") or []
    years = parsed.get("experience_years") or 0
    return _env.get_template("cover_letter.txt").render(
        job=job, name=parsed.get("name") or user["name"], email=user["email"], phone=parsed.get("phone", ""),
        linkedin=parsed.get("linkedin", ""), degree=education[0]["degree"] if education else "",
        experience_years=years, matched_skills=matched, other_skills=other, learning=list(learning)[:2]).strip()


def notify(user, subject, body):
    return send_email(user["id"], user["email"], subject, body)


def apply_to_job(user, profile, job, result, auto=False, answers=None, cover_letter=None):
    """Apply once. Returns (status, message for the user)."""
    parsed = profile["parsed"]
    if db.get_application(job["id"], user["id"]):
        return "skipped", "You have already applied to this job."
    if job.get("fake_level") == "High":
        return "blocked", "This job looks like a scam, so the app will not apply to it."

    letter = cover_letter or write_cover_letter(user, parsed, job, result)
    match = result["match"] if result else 0
    title = f"{job['title']} at {job['company'] or 'the company'}"

    # Extra questions: auto-apply stops and asks you first
    if job.get("questions") and not answers:
        if auto:
            db.add_application(job["id"], user["id"], "Needs your answers", match, "pending", auto=True,
                               cover_letter=letter)
            notify(user, f"Questions to answer before applying: {title}",
                   "This job asks extra questions, so it was not sent automatically.\n\n"
                   + "\n".join(f"- {q}" for q in job["questions"])
                   + "\n\nOpen Smart Job Assistant > My applications to answer them and send the application.")
            return "needs answers", "This job asks extra questions. They were emailed to you."
        return "needs answers", "Please answer the job's questions first."

    answers_text = ""
    if answers:
        answers_text = "\n\nAnswers to your questions:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())

    if job.get("posted_by"):                                     # posted in this app
        db.add_application(job["id"], user["id"], "Applied", match, "in-app", auto, letter + answers_text)
        recruiter = db.get_user(job["posted_by"])
        if recruiter:
            notify(recruiter, f"New applicant for {job['title']}: {user['name']} ({match:.0f}% match)",
                   f"{user['name']} applied for {job['title']}.\nMatch: {match:.0f}%\n\n"
                   "Open Smart Job Assistant > Applicants to review them.")
        status, how = "Applied", "inside the app"
    elif job.get("apply_email"):                                 # email the HR address from the listing
        subject = f"Application for {job['title']} - {parsed.get('name') or user['name']}"
        sent = send_email(user["id"], job["apply_email"], subject, letter + answers_text,
                          attachment=profile.get("resume_path"), reply_to=user["email"])
        if sent.startswith("failed"):
            return "failed", f"Email could not be sent ({sent})."
        db.add_application(job["id"], user["id"], "Applied", match, "email", auto, letter + answers_text)
        status, how = "Applied", f"by email to {job['apply_email']}" + (" (saved in outbox: dry run)" if sent == "saved" else "")
    else:                                                        # only a website link
        db.add_application(job["id"], user["id"], "Open link", match, "manual", auto, letter,
                           notes="Apply on the company website, then mark it Applied.")
        return "open link", f"This job is applied for on the company website: {job.get('url') or 'no link given'}"

    notify(user, f"Applied: {title}",
           f"Your application for {title} was sent {how}.\nMatch: {match:.0f}%\n\nCover letter:\n\n{letter}")
    return status, f"Applied {how}."


def auto_apply_for(user):
    """Run auto-apply for one job seeker. Returns a list of (job title, status, message)."""
    profile = db.get_profile(user["id"])
    if not profile or not profile.get("auto_apply") or not profile["parsed"].get("skills"):
        return []
    roles = [r.strip() for r in (profile.get("preferred_roles") or "").split(",") if r.strip()]
    jobs = [j for j in db.active_jobs() if passes_preferences(j, profile)]
    results = []
    for job, result in rank_jobs(profile["parsed"], jobs, roles):
        if result["match"] < config.AUTO_APPLY_MIN_MATCH:
            break                                               # list is sorted, so the rest are lower
        if db.applications_today(user["id"]) >= config.MAX_APPLICATIONS_PER_DAY:
            results.append((job["title"], "stopped", "Daily limit reached."))
            break
        if db.get_application(job["id"], user["id"]) or job.get("fake_level") == "High":
            continue
        status, message = apply_to_job(user, profile, job, result, auto=True)
        results.append((job["title"], status, message))
    return results


def auto_apply_everyone():
    log = []
    for user in db.all_seekers():
        for title, status, message in auto_apply_for(user):
            log.append(f"{user['email']}: {title} -> {status} ({message})")
    return log
