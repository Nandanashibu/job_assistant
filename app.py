"""Smart Job Assistant - the website.

Run it with:   streamlit run app.py
Then open the link it prints (usually http://localhost:8501).
"""
import streamlit as st

import config
from sja import database as db
from ui import login, recruiter, seeker

st.set_page_config(page_title="Smart Job Assistant", page_icon="💼", layout="wide")
db.init_db()
if "demo_checked" not in st.session_state:          # first visit: fill an empty database with demo data
    from sja.demo import seed_if_empty
    with st.spinner("Setting up demo data (first start only)..."):
        seed_if_empty()
    st.session_state["demo_checked"] = True

if "user_id" not in st.session_state:
    login.show()
    st.stop()

user = db.get_user(st.session_state["user_id"])
if user is None:                       # account deleted or database reset
    st.session_state.clear()
    st.rerun()

if user["role"] == "seeker":
    pages = {
        "👤 Profile & resume": seeker.profile_page,
        "🔎 Job feed": seeker.feed_page,
        "📋 My applications": seeker.applications_page,
        "📈 Skill insights": seeker.insights_page,
        "✉️ Emails": seeker.emails_page,
    }
else:
    pages = {
        "📝 Post a job": recruiter.post_page,
        "👥 My jobs & applicants": recruiter.applicants_page,
    }

with st.sidebar:
    st.markdown("### 💼 Smart Job Assistant")
    st.write(f"**{user['name']}**")
    st.caption(f"{'Job seeker' if user['role'] == 'seeker' else 'Recruiter · ' + user['company']}")
    choice = st.radio("Go to", list(pages), label_visibility="collapsed")
    st.divider()
    if config.EMAIL_DRY_RUN:
        st.caption("✉️ Email dry run is ON: emails are saved, not sent.")
    if st.button("Log out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

pages[choice](user)
