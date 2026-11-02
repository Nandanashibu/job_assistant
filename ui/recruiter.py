"""Recruiter pages: post a job (scam-checked) and review applicants ranked by match %."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sja import applier, database as db
from sja.job_tools import build_job
from sja.matcher import rank_applicants

INVITE_STATUSES = {"Shortlist": "Shortlisted", "Invite to interview": "Interview", "Reject": "Rejected"}


def post_page(user):
    st.header("📝 Post a job")
    with st.form("post_job", clear_on_submit=False):
        title = st.text_input("Job title", placeholder="Python Developer")
        c1, c2 = st.columns(2)
        location = c1.text_input("Location", placeholder="Infopark, Kochi")
        remote = c2.checkbox("Remote / work from home allowed")
        salary = c1.text_input("Salary", placeholder="4-6 LPA")
        closing = c2.date_input("Closing date", date.today() + timedelta(days=21))
        description = st.text_area(
            "Description: responsibilities, required skills, experience (e.g. '1-3 years experience in Python, SQL')",
            height=220)
        questions = st.text_area("Extra questions for applicants (one per line, end each with ?)", height=80)
        if st.form_submit_button("Publish job", type="primary"):
            if not title.strip() or len(description.strip()) < 50:
                st.error("Add a title and a description of at least 50 characters.")
                return
            full = description.strip() + ("\n" + questions.strip() if questions.strip() else "")
            job = build_job(title, user["company"], full, source="Posted in app", location=location,
                            remote=remote, posted_by=user["id"], salary_text=salary, closing_date=closing.isoformat())
            if job["fake_level"] == "High":
                st.error("This post looks like a scam to our checks, so it was not published:\n"
                         + "\n".join(f"- {r}" for r in job["fake_reasons"]))
                return
            db.save_job(job)
            st.success("Job published.")
            st.write(f"**Skills detected:** {', '.join(job['skills']) or 'none, add tool names to the description'}")
            st.write(f"**Experience asked:** {job['min_years']:g}+ years · **Questions:** {len(job['questions'])}")
            if job["fake_level"] == "Medium":
                st.warning("Published, but some wording looks risky:\n" + "\n".join(f"- {r}" for r in job["fake_reasons"]))


def applicants_page(user):
    st.header("👥 My jobs & applicants")
    jobs = db.jobs_posted_by(user["id"])
    if not jobs:
        st.info("You have not posted any jobs yet.")
        return
    labels = {f"{j['title']} ({'open' if j['active'] else 'closed'}) · {j['created_at'][:10]}": j for j in jobs}
    job = labels[st.selectbox("Job", list(labels))]

    c1, c2 = st.columns([3, 1])
    c1.caption(f"Skills: {', '.join(job['skills']) or '-'} · {job['min_years']:g}+ years · closes {job['closing_date'] or '-'}")
    if c2.button("Close job" if job["active"] else "Reopen job"):
        db.set_job_active(job["id"], not job["active"])
        st.rerun()

    apps = db.applications_for_job(job["id"])
    st.subheader(f"Applicants ({len(apps)}), best match first")
    if not apps:
        st.write("No applicants yet.")
    else:
        candidates = []
        for a in apps:
            profile = db.get_profile(a["user_id"])
            candidates.append(({**a, "ats": profile.get("ats_score", 0) if profile else 0},
                               profile["parsed"] if profile else {}))
        ranked = rank_applicants(job, candidates)
        min_match = st.slider("Show applicants with match of at least", 0, 100, 0, 5)
        st.dataframe(pd.DataFrame([{"Name": a["name"], "Match %": round(r["match"]), "ATS": a["ats"],
                                    "Experience (yrs)": p.get("experience_years", 0), "Status": a["status"],
                                    "Has": ", ".join(r["matched_skills"]), "Missing": ", ".join(r["missing_skills"])}
                                   for a, p, r in ranked if r["match"] >= min_match]),
                     hide_index=True, use_container_width=True)

        for a, parsed, r in ranked:
            if r["match"] < min_match:
                continue
            with st.expander(f"{a['name']} · {r['match']:.0f}% · {a['status']}"):
                st.write(f"📧 {a['email']} · 📞 {parsed.get('phone') or '-'} · {parsed.get('linkedin') or ''}")
                edu = parsed.get("education") or []
                st.write(f"🎓 {edu[0]['degree'] if edu else '-'} · {parsed.get('experience_years', 0)} years experience")
                st.text_area("Cover letter / answers", a["cover_letter"], height=180, disabled=True, key=f"cl{a['id']}")
                cols = st.columns(3)
                for col, (label, status) in zip(cols, INVITE_STATUSES.items()):
                    if col.button(label, key=f"{label}{a['id']}"):
                        db.update_application_status(a["id"], status)
                        seeker = db.get_user(a["user_id"])
                        messages = {
                            "Shortlisted": "Good news: you have been shortlisted.",
                            "Interview": "You are invited to an interview. The recruiter will contact you with a time.",
                            "Rejected": "Thank you for applying. The company has decided not to continue this time.",
                        }
                        applier.notify(seeker, f"Update on your application: {job['title']} at {user['company']}",
                                       f"{messages[status]}\n\nJob: {job['title']}\nCompany: {user['company']}\n"
                                       f"Recruiter: {user['name']} ({user['email']})")
                        st.rerun()

    st.subheader("Suggested candidates who have not applied")
    applied_ids = {a["user_id"] for a in apps}
    pool = []
    for seeker in db.all_seekers():
        if seeker["id"] in applied_ids:
            continue
        profile = db.get_profile(seeker["id"])
        if profile and profile["parsed"].get("text"):
            pool.append((seeker, profile["parsed"]))
    suggested = [x for x in rank_applicants(job, pool) if x[2]["match"] >= 60][:5]
    if not suggested:
        st.write("No strong matches among registered job seekers yet.")
    for seeker, parsed, r in suggested:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{seeker['name']}** · {r['match']:.0f}% match · has {', '.join(r['matched_skills'][:6])}")
        if c2.button("Invite to apply", key=f"inv{seeker['id']}{job['id']}"):
            applier.notify(seeker, f"{user['company']} invites you to apply: {job['title']}",
                           f"Hi {seeker['name']},\n\n{user['company']} thinks you match their {job['title']} role "
                           f"({r['match']:.0f}% match). Open Smart Job Assistant > Job feed to apply.")
            st.success("Invitation sent.")
