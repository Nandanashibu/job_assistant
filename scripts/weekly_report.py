"""Email every job seeker their weekly skills report.   python scripts/weekly_report.py"""
import _path  # noqa: F401
from sja import applier, database as db, insights
from sja.matcher import rank_jobs


def report_for(user):
    profile = db.get_profile(user["id"])
    if not profile or not profile["parsed"].get("text"):
        return None
    jobs = [j for j in db.active_jobs() if j["fake_level"] != "High"]
    roles = [r.strip() for r in (profile.get("preferred_roles") or "").split(",") if r.strip()]
    ranked = rank_jobs(profile["parsed"], jobs, roles)
    gaps = insights.skill_gaps(ranked)
    boost = {b["skill"]: b for b in insights.match_boost(profile["parsed"], jobs, [g["skill"] for g in gaps[:5]], roles)}
    weeks, table, _ = insights.weekly_skill_trends(jobs)
    rising, _ = insights.rising_and_falling(weeks, table)
    lines = [f"Hi {user['name']},", "", "Your weekly Smart Job Assistant report", "",
             f"ATS score: {profile.get('ats_score', 0)}/100",
             f"Jobs at 80%+ match right now: {sum(1 for _, r in ranked if r['match'] >= 80)}", "",
             "Top matches:"]
    lines += [f"- {j['title']} at {j['company']} ({r['match']:.0f}%)" for j, r in ranked[:5]]
    lines += ["", "Skills to learn next:"]
    for g in gaps[:5]:
        b = boost.get(g["skill"])
        extra = f", match {b['avg_before']:.0f}% -> {b['avg_after']:.0f}%" if b else ""
        lines.append(f"- {g['skill']} (in {g['share']}% of your best-fitting jobs{extra}) - {g['learn']}")
    if rising:
        lines += ["", "Rising skills this week: " + ", ".join(f"{s} (+{d}%)" for s, _, d in rising)]
    ideas = insights.project_ideas([g["skill"] for g in gaps], profile["parsed"].get("skills", []), limit=2)
    if ideas:
        lines += ["", "Project ideas:"] + [f"- {i['title']}: {i['description']}" for i in ideas]
    return "\n".join(lines)


if __name__ == "__main__":
    for user in db.all_seekers():
        body = report_for(user)
        if body:
            print(user["email"], applier.notify(user, "Your weekly skills report", body))
