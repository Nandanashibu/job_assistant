"""Skill gaps, match boost and the weekly skills report.

* Skill gap:   which skills your matched jobs ask for that your resume lacks.
* Match boost: re-run the matcher as if you had learned a skill and measure how much
               your average match % rises and how many more jobs cross the auto-apply line.
               (We report match %, not a 'chance of getting hired', because hiring
               outcomes are never visible to the app.)
* Weekly report: how often each skill appeared in jobs this week vs last week.
"""
import json
from collections import Counter
from datetime import datetime, timedelta

import config
from sja.matcher import rank_jobs
from sja.skills import category, learning_link

with open(config.PROJECT_IDEAS_FILE, encoding="utf-8") as f:
    PROJECT_IDEAS = json.load(f)


def relevant(ranked, min_match=45, at_least=5, at_most=15):
    """The jobs that really fit you: match >= min_match, but always at least a few."""
    good = [pair for pair in ranked if pair[1]["match"] >= min_match][:at_most]
    return good if len(good) >= at_least else ranked[:at_least]


def skill_gaps(ranked, top_n=10):
    """ranked: output of rank_jobs. Count the skills your best-fitting jobs ask for that you lack."""
    best = relevant(ranked)
    if not best:
        return []
    counts = Counter(s for _, result in best for s in result["missing_skills"])
    rows = []
    for skill, n in counts.most_common(top_n):
        share = n / len(best)
        rows.append({
            "skill": skill,
            "category": category(skill),
            "jobs_asking": n,
            "share": round(100 * share),
            "priority": "High" if share >= 0.4 else "Medium" if share >= 0.2 else "Low",
            "learn": learning_link(skill),
        })
    return rows


def match_boost(parsed_resume, jobs, skills_to_try, roles=()):
    """For each skill: average match before/after (over your best-fitting jobs)
    and how many jobs reach the auto-apply line."""
    before = relevant(rank_jobs(parsed_resume, jobs, roles))
    jobs = [job for job, _ in before]
    line = config.AUTO_APPLY_MIN_MATCH
    base_avg = sum(r["match"] for _, r in before) / len(before) if before else 0
    base_count = sum(1 for _, r in before if r["match"] >= line)
    rows = []
    for skill in skills_to_try:
        boosted = dict(parsed_resume)
        boosted["skills"] = sorted(set(parsed_resume.get("skills", [])) | {skill})
        boosted["text"] = parsed_resume.get("text", "") + f"\n{skill}"
        after = rank_jobs(boosted, jobs, roles)
        avg = sum(r["match"] for _, r in after) / len(after) if after else 0
        rows.append({
            "skill": skill,
            "avg_before": round(base_avg, 1),
            "avg_after": round(avg, 1),
            "gain": round(avg - base_avg, 1),
            "jobs_over_line_before": base_count,
            "jobs_over_line_after": sum(1 for _, r in after if r["match"] >= line),
        })
    return sorted(rows, key=lambda r: r["gain"], reverse=True)


def week_start(day):
    return (day - timedelta(days=day.weekday())).date()


def weekly_skill_trends(jobs, weeks=4):
    """Share of jobs asking for each skill, per week, newest week last."""
    today = datetime.now()
    week_keys = [week_start(today - timedelta(weeks=w)) for w in range(weeks - 1, -1, -1)]
    per_week = {w: [] for w in week_keys}
    for job in jobs:
        try:
            created = datetime.fromisoformat(job["created_at"])
        except (TypeError, ValueError):
            continue
        w = week_start(created)
        if w in per_week:
            per_week[w].append(job)
    table = {}
    for w, week_jobs in per_week.items():
        counts = Counter(s for j in week_jobs for s in j.get("skills", []))
        total = len(week_jobs) or 1
        for skill, n in counts.items():
            table.setdefault(skill, {})[w.isoformat()] = round(100 * n / total)
    return [w.isoformat() for w in week_keys], table, {w.isoformat(): len(v) for w, v in per_week.items()}


def rising_and_falling(week_labels, table, top=5):
    if len(week_labels) < 2:
        return [], []
    this, last = week_labels[-1], week_labels[-2]
    changes = [(skill, vals.get(this, 0), vals.get(this, 0) - vals.get(last, 0)) for skill, vals in table.items()]
    rising = sorted([c for c in changes if c[2] > 0], key=lambda c: c[2], reverse=True)[:top]
    falling = sorted([c for c in changes if c[2] < 0], key=lambda c: c[2])[:top]
    return rising, falling


def project_ideas(missing_skills, have_skills=(), limit=4):
    """Pick projects that practise the missing skills, preferring ones that also use skills you have."""
    missing, have = set(missing_skills), set(have_skills)
    scored = []
    for idea in PROJECT_IDEAS:
        teaches = missing & set(idea["skills"])
        if teaches:
            scored.append((len(teaches) * 2 + len(have & set(idea["skills"])), idea, sorted(teaches)))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [dict(idea, teaches=teaches) for _, idea, teaches in scored[:limit]]
