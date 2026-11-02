"""Log in / sign up page (two roles: job seeker and recruiter)."""
import streamlit as st

from sja import auth


def show():
    st.title("💼 Smart Job Assistant")
    st.caption("Find matching jobs at Kerala IT parks, fix your resume, and apply smarter.")

    tab_login, tab_signup = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                user = auth.log_in(email, password)
                if user:
                    st.session_state["user_id"] = user["id"]
                    st.rerun()
                else:
                    st.error("Wrong email or password.")

    with tab_signup:
        role_label = st.radio("I am a", ["Job seeker", "Recruiter"], horizontal=True)
        role = "seeker" if role_label == "Job seeker" else "recruiter"
        with st.form("signup"):
            name = st.text_input("Full name")
            email = st.text_input("Email ")
            company = st.text_input("Company name") if role == "recruiter" else ""
            password = st.text_input("Password (8+ characters)", type="password")
            if st.form_submit_button("Create account", type="primary"):
                user_id, error = auth.sign_up(email, name, password, role, company)
                if error:
                    st.error(error)
                else:
                    st.session_state["user_id"] = user_id
                    st.rerun()
        st.caption("We never ask for your LinkedIn or Naukri password. Only profile links are stored.")
