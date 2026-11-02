"""Match % between a resume and a job. Used both ways:
  * job seekers: rank jobs for one resume
  * recruiters:  rank applicants for one job

match % = 55% skill overlap + 30% text similarity + 15% experience fit (+5 if the title is a preferred role)

  skill overlap   = share of the job's required skills that the resume has
  text similarity = TF-IDF cosine similarity (scikit-learn); no training needed
  experience fit  = 1.0 if the candidate has the years asked for, lower if not
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config


def text_similarity(resume_text, job_texts):
    """One number between 0 and 1 per job."""
    if not job_texts:
        return []
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform([resume_text] + job_texts)
    scores = cosine_similarity(matrix[0], matrix[1:])[0]
    return [float(min(1.0, s * 2.5)) for s in scores]       # raw TF-IDF cosines are small, so stretch them


def role_matches(roles, title):
    title = title.lower()
    for role in roles:
        words = [w for w in re.findall(r"[a-z+#./]+", role.lower()) if len(w) > 2 or w in {"ai", "ml", "qa", "ui", "ux"}]
        if words and all(w in title for w in words):
            return True
    return False


def score_one(candidate_skills, candidate_years, job, similarity, roles=()):
    """Return a dict with the match % and its parts for one job."""
    have = set(candidate_skills)
    needed = job.get("skills", [])
    matched = [s for s in needed if s in have]
    missing = [s for s in needed if s not in have]
    skill_part = len(matched) / len(needed) if needed else similarity
    need_years = job.get("min_years") or 0
    if candidate_years >= need_years:
        experience_part = 1.0
    else:
        experience_part = max(0.0, 1 - (need_years - candidate_years) / 3)
    score = 100 * (config.WEIGHT_SKILLS * skill_part + config.WEIGHT_TEXT * similarity
                   + config.WEIGHT_EXPERIENCE * experience_part)
    if roles and role_matches(roles, job.get("title", "")):
        score += config.ROLE_BONUS
    return {
        "match": round(float(min(score, 100)), 1),
        "skill_part": round(skill_part * 100),
        "text_part": round(similarity * 100),
        "experience_part": round(experience_part * 100),
        "matched_skills": matched,
        "missing_skills": missing,
    }


def rank_jobs(parsed_resume, jobs, roles=()):
    """Return [(job, result), ...] best match first."""
    sims = text_similarity(parsed_resume.get("text", ""), [f"{j['title']}\n{j['description']}" for j in jobs])
    ranked = [(job, score_one(parsed_resume.get("skills", []), parsed_resume.get("experience_years", 0), job, sim, roles))
              for job, sim in zip(jobs, sims)]
    return sorted(ranked, key=lambda pair: pair[1]["match"], reverse=True)


def rank_applicants(job, candidates):
    """candidates: [(user, parsed_resume), ...]  ->  [(user, parsed_resume, result), ...] best first."""
    if not candidates:
        return []
    job_text = f"{job['title']}\n{job['description']}"
    results = []
    for user, parsed in candidates:
        sim = text_similarity(parsed.get("text", ""), [job_text])[0]
        results.append((user, parsed, score_one(parsed.get("skills", []), parsed.get("experience_years", 0), job, sim)))
    return sorted(results, key=lambda r: r[2]["match"], reverse=True)


def passes_preferences(job, prefs):
    """prefs: a row from the profiles table. Location / remote / relocation / salary filters."""
    locations = [l.strip().lower() for l in (prefs.get("locations") or "").split(",") if l.strip()]
    if locations and not prefs.get("willing_to_relocate"):
        in_place = any(l in (job.get("location") or "").lower() for l in locations)
        if not (in_place or (prefs.get("remote_ok") and job.get("remote"))):
            return False
    if not prefs.get("remote_ok") and job.get("remote") and not locations:
        return False
    min_salary = prefs.get("min_salary_lpa") or 0
    top = job.get("salary_max_lpa") or job.get("salary_min_lpa")
    if min_salary and top is not None and top < min_salary:
        return False
    return True
