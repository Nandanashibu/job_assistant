"""Job seeker pages: profile, job feed, applications, skill insights, emails."""
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from sja import applier, database as db, insights
from sja.ats import full_ats, grade, job_match
from sja.collector import collect_all
from sja.matcher import passes_preferences, rank_jobs
from sja.resume_parser import parse_resume
from sja.skills import SKILLS, skills_by_category

RISK_BADGE = {"Low": "🟢 Low risk", "Medium": "🟠 Check carefully", "High": "🔴 Likely scam"}


def _roles(profile):
    return [r.strip() for r in (profile.get("preferred_roles") or "").split(",") if r.strip()]


def _need_resume(profile):
    if not profile or not profile["parsed"].get("text"):
        st.info("Upload your resume on the **Profile & resume** page first.")
        return True
    return False


# --------------------------------------------------------------------------- profile
def profile_page(user):
    st.header("👤 Profile & resume")
    profile = db.get_profile(user["id"]) or {"parsed": {}}
    parsed = profile["parsed"]

    st.subheader("1. Upload your resume")
    upload = st.file_uploader("PDF or Word (.docx)", type=["pdf", "docx"])
    if upload is not None and st.session_state.get("last_upload") != upload.name + str(upload.size):
        safe_name = re.sub(r"[^\w.-]+", "_", upload.name)
        path = config.UPLOAD_DIR / f"user{user['id']}_{safe_name}"
        path.write_bytes(upload.getvalue())
        try:
            parsed = parse_resume(path)
        except Exception as exc:
            st.error(f"Could not read this file: {exc}")
            return
        if len(parsed["text"].split()) < 30:
            st.warning("Very little text was found. If your resume is a scanned image, export it again "
                       "from Word or Google Docs as a PDF.")
        score = full_ats(parsed, path, db.active_jobs(), _roles(profile))["score"]
        db.save_profile(user["id"], resume_path=str(path), parsed_json=parsed, ats_score=score,
                        phone=parsed.get("phone", ""), linkedin_url=parsed.get("linkedin", ""),
                        github_url=parsed.get("github", ""))
        st.session_state["last_upload"] = upload.name + str(upload.size)
        st.success("Resume read. Check the details below and correct anything that was missed.")
        profile = db.get_profile(user["id"])

    if not parsed.get("text"):
        st.info("Upload a resume to see your ATS score and matching jobs.")
        return

    # ---- ATS score
    st.subheader("2. ATS score")
    result = full_ats(parsed, profile.get("resume_path"), db.active_jobs(), _roles(profile))
    score = result["score"]
    if score != profile.get("ats_score"):
        db.save_profile(user["id"], ats_score=score)
    left, right = st.columns([1, 2])
    left.metric("ATS score", f"{score}/100", grade(score))
    left.progress(score / 100)
    for part, value in result["parts"].items():
        left.caption(f"{part}: {value}/100")
        left.progress(value / 100)
    if "Keywords" not in result["parts"]:
        left.caption("Collect jobs to add the Keywords part (40% of the score).")
    with right:
        if result["tips"]:
            st.markdown("**How to improve your resume**")
            for tip in result["tips"][:8]:
                st.markdown(f"- {tip}")
        else:
            st.success("Your resume passes every check.")
        if result["target_jobs"]:
            st.caption("Keywords compared with: " + ", ".join(f"{j['title']} ({j['company']})" for j in result["target_jobs"]))
    with st.expander("See all checks"):
        st.dataframe(pd.DataFrame([{"Area": c[0], "Check": c[1], "Points": f"{c[2]:g}/{c[3]}",
                                    "": "✅" if c[2] >= c[3] else ("🟠" if c[2] > 0 else "❌")} for c in result["checks"]]),
                     hide_index=True, use_container_width=True)

    with st.expander("🎯 Check your resume against any job description"):
        jd = st.text_area("Paste a job description (from LinkedIn, Naukri, a company site...)", height=150)
        if st.button("Check ATS match") and jd.strip():
            from sja.job_tools import build_job
            pasted = build_job(jd.strip().splitlines()[0][:80], "", jd, source="Pasted")
            match_score, details, match_tips = job_match(parsed, pasted)
            st.metric("ATS match for this job", f"{match_score}/100")
            for tip in match_tips:
                st.markdown(f"- {tip}")

    # ---- What we found + preferences
    st.subheader("3. Your details and job preferences")
    edu = parsed.get("education") or []
    st.caption(f"Found: **{parsed.get('name') or '?'}** · {parsed.get('email') or 'no email'} · "
               f"{edu[0]['degree'] if edu else 'no degree found'} · {parsed.get('experience_years', 0)} years experience")
    with st.form("profile"):
        skills = st.multiselect("Skills (add any that were missed, remove any that are wrong)",
                                sorted(SKILLS), default=[s for s in parsed.get("skills", []) if s in SKILLS])
        years = st.number_input("Years of experience", 0.0, 40.0, float(parsed.get("experience_years", 0)), 0.5)
        c1, c2 = st.columns(2)
        phone = c1.text_input("Phone", profile.get("phone", ""))
        linkedin = c2.text_input("LinkedIn profile link", profile.get("linkedin_url", ""))
        naukri = c1.text_input("Naukri profile link (optional)", profile.get("naukri_url", ""))
        github = c2.text_input("GitHub link (optional)", profile.get("github_url", ""))
        roles = st.text_input("Preferred roles (comma separated)", profile.get("preferred_roles", ""),
                              placeholder="Data Analyst, Python Developer")
        locations = st.text_input("Preferred locations (comma separated)", profile.get("locations", ""),
                                  placeholder="Kochi, Thiruvananthapuram")
        c3, c4, c5 = st.columns(3)
        remote_ok = c3.checkbox("Open to remote / work from home", bool(profile.get("remote_ok", 1)))
        relocate = c4.checkbox("Willing to relocate", bool(profile.get("willing_to_relocate", 0)))
        min_salary = c5.number_input("Minimum salary (LPA)", 0.0, 100.0, float(profile.get("min_salary_lpa") or 0), 0.5)
        auto = st.toggle(f"Auto-apply to jobs with {config.AUTO_APPLY_MIN_MATCH}%+ match "
                         f"(max {config.MAX_APPLICATIONS_PER_DAY}/day, never to risky jobs)",
                         bool(profile.get("auto_apply", 0)))
        st.caption("We only store profile links. Never enter your LinkedIn or Naukri password anywhere in this app.")
        if st.form_submit_button("Save profile", type="primary"):
            parsed["skills"] = sorted(skills)
            parsed["experience_years"] = years
            db.save_profile(user["id"], parsed_json=parsed, phone=phone,
                            linkedin_url=linkedin, naukri_url=naukri, github_url=github, preferred_roles=roles,
                            locations=locations, remote_ok=int(remote_ok), willing_to_relocate=int(relocate),
                            min_salary_lpa=min_salary, auto_apply=int(auto))
            st.success("Profile saved.")
            st.rerun()

    with st.expander("Skills by category"):
        for cat, items in skills_by_category(parsed.get("skills", [])).items():
            st.markdown(f"**{cat}:** {', '.join(items)}")


# --------------------------------------------------------------------------- job feed
def _collect_box(user, profile):
    with st.expander("🔄 Collect new jobs / run auto-apply"):
        st.caption("Collect at most once a day. Park websites are read slowly and politely.")
        c = st.columns(4)
        chosen = [name for name, box in zip(["sample", "infopark", "technopark", "remotive"],
                                            [c[0].checkbox("Sample jobs", True), c[1].checkbox("Infopark"),
                                             c[2].checkbox("Technopark"), c[3].checkbox("Remotive (remote)")]) if box]
        if st.button("Collect jobs now"):
            with st.spinner("Collecting... park websites can take a few minutes"):
                new, log = collect_all(chosen, remotive_search=(_roles(profile) or [""])[0])
            st.success(f"{new} new jobs saved.")
            st.code("\n".join(log))
        if profile.get("auto_apply"):
            if st.button("Run auto-apply now"):
                results = applier.auto_apply_for(user)
                if results:
                    for title, status, message in results:
                        st.write(f"**{title}**: {status}. {message}")
                else:
                    st.info(f"No new jobs at {config.AUTO_APPLY_MIN_MATCH}% match or above right now.")


def feed_page(user):
    st.header("🔎 Jobs for you")
    profile = db.get_profile(user["id"])
    if _need_resume(profile):
        return
    _collect_box(user, profile)

    jobs = db.active_jobs()
    if not jobs:
        st.info("No jobs yet. Open **Collect new jobs** above.")
        return

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    search = f1.text_input("Search title, company or skill")
    min_match = f2.slider("Minimum match %", 0, 100, config.SHOW_MIN_MATCH, 5)
    use_prefs = f3.checkbox("Use my preferences", True)
    show_risky = f4.checkbox("Show risky jobs", False)

    if use_prefs:
        jobs = [j for j in jobs if passes_preferences(j, profile)]
    if not show_risky:
        jobs = [j for j in jobs if j["fake_level"] != "High"]
    if search:
        s = search.lower()
        jobs = [j for j in jobs if s in f"{j['title']} {j['company']} {' '.join(j['skills'])}".lower()]
    ranked = [(j, r) for j, r in rank_jobs(profile["parsed"], jobs, _roles(profile)) if r["match"] >= min_match]
    st.caption(f"{len(ranked)} jobs, best match first")

    for job, result in ranked[:40]:
        _job_card(user, profile, job, result)


def _job_card(user, profile, job, result):
    application = db.get_application(job["id"], user["id"])
    salary = (f"{job['salary_min_lpa']:g}-{job['salary_max_lpa']:g} LPA" if job.get("salary_min_lpa") else "Salary not listed")
    header = f"**{result['match']:.0f}%** · {job['title']} · {job['company'] or 'Unknown company'}"
    with st.expander(header + (f"  ·  ✅ {application['status']}" if application else "")):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Match", f"{result['match']:.0f}%")
        c2.write(f"📍 {job['location'] or '-'}{' · Remote' if job['remote'] else ''}")
        c2.write(f"💰 {salary}")
        c3.write(f"🗂 {job['source']}")
        c3.write(f"⏳ Closes {job['closing_date'] or 'not stated'}")
        c4.write(RISK_BADGE[job["fake_level"]])
        if job["fake_reasons"]:
            st.warning("Why this may be risky:\n" + "\n".join(f"- {r}" for r in job["fake_reasons"]))
        ats_match, ats_details, ats_tips = job_match(profile["parsed"], job)
        st.markdown(f"**ATS match for this job: {ats_match}/100**")
        for tip in ats_tips[:3]:
            st.caption(f"💡 {tip}")
        st.markdown(f"**You have:** {', '.join(result['matched_skills']) or '-'}")
        st.markdown(f"**Missing:** {', '.join(result['missing_skills']) or 'nothing'}")
        st.caption(f"Skills {result['skill_part']}% · text similarity {result['text_part']}% · "
                   f"experience fit {result['experience_part']}% (job asks {job['min_years']:g}+ years)")
        st.text_area("Job description", job["description"], height=160, disabled=True, key=f"desc{job['id']}")
        if job.get("url"):
            st.markdown(f"[Open the original listing]({job['url']})")

        if application:
            st.info(f"Status: **{application['status']}** (applied {application['applied_at'][:10]})")
            return
        if job["fake_level"] == "High":
            st.error("Applying is disabled for likely scams.")
            return

        with st.form(f"apply{job['id']}"):
            letter = st.text_area("Cover letter (edit before sending)",
                                  applier.write_cover_letter(user, profile["parsed"], job, result), height=260)
            answers = {}
            for i, question in enumerate(job["questions"]):
                answers[question] = st.text_input(question, key=f"q{job['id']}{i}")
            how = ("inside the app" if job.get("posted_by") else
                   f"by email to {job['apply_email']}" if job.get("apply_email") else "on the company website")
            if st.form_submit_button(f"Apply ({how})", type="primary"):
                if job["questions"] and not all(a.strip() for a in answers.values()):
                    st.error("Please answer all the questions.")
                else:
                    status, message = applier.apply_to_job(user, profile, job, result, auto=False,
                                                           answers=answers or None, cover_letter=letter)
                    (st.success if status in ("Applied", "open link") else st.error)(message)


# --------------------------------------------------------------------------- applications
STATUSES = ["Applied", "Open link", "Needs your answers", "Shortlisted", "Interview", "Offer", "Rejected", "Withdrawn"]


def applications_page(user):
    st.header("📋 My applications")
    apps = db.applications_for_user(user["id"])
    if not apps:
        st.info("No applications yet. Apply from the **Job feed**.")
        return
    table = pd.DataFrame([{"Job": a["title"], "Company": a["company"], "Match %": round(a["match_score"]),
                           "Status": a["status"], "How": a["method"], "Auto": "yes" if a["auto"] else "",
                           "Applied": a["applied_at"][:10]} for a in apps])
    counts = table["Status"].value_counts()
    cols = st.columns(min(len(counts), 6))
    for col, (status, n) in zip(cols, counts.items()):
        col.metric(status, n)
    st.dataframe(table, hide_index=True, use_container_width=True)

    st.subheader("Update or finish an application")
    for a in apps:
        with st.expander(f"{a['title']} · {a['company']} · {a['status']}"):
            job = db.get_job(a["job_id"])
            if a["status"] == "Needs your answers" and job:
                with st.form(f"answers{a['id']}"):
                    answers = {q: st.text_input(q, key=f"ans{a['id']}{i}") for i, q in enumerate(job["questions"])}
                    if st.form_submit_button("Send application", type="primary"):
                        if not all(v.strip() for v in answers.values()):
                            st.error("Please answer every question.")
                        else:
                            profile = db.get_profile(user["id"])
                            db.delete_application(a["id"])
                            status, message = applier.apply_to_job(user, profile, job, {"match": a["match_score"]},
                                                                   answers=answers, cover_letter=a["cover_letter"])
                            st.success(message)
            if a["status"] == "Open link" and a.get("url"):
                st.markdown(f"[Apply on the company website]({a['url']}), then mark it as Applied below.")
            new_status = st.selectbox("Status", STATUSES, index=STATUSES.index(a["status"]) if a["status"] in STATUSES else 0,
                                      key=f"st{a['id']}")
            if new_status != a["status"] and st.button("Save status", key=f"save{a['id']}"):
                db.update_application_status(a["id"], new_status)
                st.rerun()
            if a["cover_letter"]:
                st.text_area("Cover letter sent", a["cover_letter"], height=200, disabled=True, key=f"cl{a['id']}")


# --------------------------------------------------------------------------- insights
def insights_page(user):
    st.header("📈 Skill insights")
    profile = db.get_profile(user["id"])
    if _need_resume(profile):
        return
    parsed = profile["parsed"]
    jobs = [j for j in db.active_jobs() if j["fake_level"] != "High"]
    if not jobs:
        st.info("Collect some jobs first (Job feed page).")
        return
    roles = _roles(profile)
    ranked = rank_jobs(parsed, jobs, roles)
    gaps = insights.skill_gaps(ranked)

    best = insights.relevant(ranked)
    c1, c2, c3 = st.columns(3)
    c1.metric("ATS score", f"{profile.get('ats_score', 0)}/100")
    c2.metric("Average match (your best-fitting jobs)", f"{sum(r['match'] for _, r in best) / len(best):.0f}%")
    c3.metric(f"Jobs at {config.AUTO_APPLY_MIN_MATCH}%+ match", sum(1 for _, r in ranked if r["match"] >= config.AUTO_APPLY_MIN_MATCH))

    st.subheader("Skills your best-fitting jobs ask for that you don't list")
    if gaps:
        boost = {b["skill"]: b for b in insights.match_boost(parsed, jobs, [g["skill"] for g in gaps[:8]], roles)}
        st.dataframe(pd.DataFrame([{
            "Skill": g["skill"], "Priority": g["priority"], "Asked in": f"{g['jobs_asking']} jobs ({g['share']}%)",
            "Match boost": f"{boost[g['skill']]['avg_before']:.0f}% → {boost[g['skill']]['avg_after']:.0f}%"
            if g["skill"] in boost else "", "Learn free": g["learn"]} for g in gaps]),
            column_config={"Learn free": st.column_config.LinkColumn("Learn free", display_text="Open")},
            hide_index=True, use_container_width=True)
        st.caption("Match boost = your average match % on your best-fitting jobs if you add this skill. "
                   "It measures fit, not the chance of being hired.")

        st.subheader("Projects that build these skills")
        ideas = insights.project_ideas([g["skill"] for g in gaps], parsed.get("skills", []))
        cols = st.columns(2)
        for i, idea in enumerate(ideas):
            with cols[i % 2].container(border=True):
                st.markdown(f"**{idea['title']}** · {idea['level']}")
                st.write(idea["description"])
                st.caption(f"Builds: {', '.join(idea['teaches'])} · Uses: {', '.join(idea['skills'])}")
    else:
        st.success("Your resume covers the skills your matching jobs ask for.")

    st.subheader("Weekly skill trends (all collected jobs)")
    weeks, table, counts = insights.weekly_skill_trends(jobs)
    this_week = weeks[-1]
    top = sorted(table, key=lambda s: table[s].get(this_week, 0), reverse=True)[:8]
    if top:
        chart = pd.DataFrame({skill: [table[skill].get(w, 0) for w in weeks] for skill in top},
                             index=[f"Week of {w}" for w in weeks])
        st.line_chart(chart, y_label="% of that week's jobs")
        st.caption("Jobs collected per week: " + ", ".join(f"{w}: {n}" for w, n in counts.items()))
        rising, falling = insights.rising_and_falling(weeks, table)
        r1, r2 = st.columns(2)
        r1.markdown("**Rising this week**\n" + "\n".join(f"- {s}: {now}% (+{d})" for s, now, d in rising) if rising else "**Rising:** -")
        r2.markdown("**Falling this week**\n" + "\n".join(f"- {s}: {now}% ({d})" for s, now, d in falling) if falling else "**Falling:** -")

    if st.button("✉️ Email me this report"):
        lines = [f"Weekly skills report for {user['name']}", "",
                 f"ATS score: {profile.get('ats_score', 0)}/100", "", "Skills to learn next:"]
        lines += [f"- {g['skill']} (asked in {g['share']}% of your best-fitting jobs) - learn: {g['learn']}" for g in gaps[:5]]
        status = applier.notify(user, "Your weekly skills report", "\n".join(lines))
        st.success(f"Report {status}.")


# --------------------------------------------------------------------------- emails
def emails_page(user):
    st.header("✉️ Emails")
    if config.EMAIL_DRY_RUN:
        st.info("Dry run is ON: emails are **saved** (as .eml files in data/outbox), not sent. "
                "Set EMAIL_DRY_RUN=false in .env to send for real.")
    emails = db.emails_for_user(user["id"])
    if not emails:
        st.write("No emails yet.")
    for e in emails:
        with st.expander(f"{e['created_at'][:16]} · {e['subject']} · to {e['to_addr']} · {e['status']}"):
            st.text(e["body"])
            if e["attachment"]:
                st.caption(f"Attachment: {Path(e['attachment']).name}")
