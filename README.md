# Smart Job Assistant

A two-sided job platform for Kerala IT parks. Job seekers upload a resume, get an ATS score, see jobs ranked by match %, apply (or auto-apply at 80%+), and get weekly skill insights. Recruiters post jobs and see applicants ranked by match %.

## 1. Where the files go

Extract the zip **into your existing `smart_job_assistant` folder** and choose **Replace** when Windows asks. Your folder should then look like this:

```
smart_job_assistant/
├── app.py                  ← the website (run this)
├── config.py               ← all settings (match threshold, email, park URLs)
├── requirements.txt
├── .env.example            ← copy to .env for real email sending
├── .gitignore
├── README.md
├── venv/                   ← your existing virtual environment (unchanged)
├── data/
│   ├── skills.json         ← 100+ skills, other names, learning links
│   ├── sample_jobs.json    ← 28 demo jobs (3 are scams on purpose)
│   ├── project_ideas.json  ← project suggestions per skill
│   ├── answer_key.json     ← correct answers for the 10 sample resumes
│   └── *.pdf / *.docx      ← 12 sample resumes (strong, average and weak)
├── sja/                    ← the core engine
│   ├── resume_reader.py        Lesson 2: text from PDF/DOCX
│   ├── contact_info.py         Lesson 3: name, email, phone, links
│   ├── skills.py               Lesson 4: skill finder (+ exclude list)
│   ├── education_experience.py Lesson 5: sections, degree, years
│   ├── resume_parser.py        Lesson 6: full profile
│   ├── ats.py                  Lesson 6: ATS score + tips
│   ├── database.py         SQLite tables and queries
│   ├── auth.py             sign up / log in (hashed passwords)
│   ├── job_tools.py        cleans a raw job: skills, years, HR email, questions, salary
│   ├── collector.py        Infopark, Technopark, Remotive, sample jobs
│   ├── fake_detector.py    scam rules + optional ML model
│   ├── matcher.py          match % for jobs and for applicants
│   ├── insights.py         skill gaps, match boost, weekly trends, project ideas
│   ├── applier.py          cover letters, apply, auto-apply, notifications
│   └── emailer.py          send email or save it (dry run)
├── ui/
│   ├── login.py            log in / sign up (seeker or recruiter)
│   ├── seeker.py           profile, job feed, applications, insights, emails
│   └── recruiter.py        post a job, ranked applicants
├── templates/cover_letter.txt
├── scripts/
│   ├── seed_demo.py        demo accounts + jobs in one command
│   ├── collect_jobs.py     collect jobs once
│   ├── auto_apply.py       run auto-apply once
│   ├── weekly_report.py    email weekly reports
│   ├── run_scheduler.py    daily collection + auto-apply, weekly reports
│   └── train_fake_model.py train the scam detector on EMSCAD
├── models/                 trained model is saved here
└── tests/                  accuracy tests on the sample resumes
```

## 2. Install and run

In the VS Code terminal, inside the project folder:

```bash
venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_demo.py
streamlit run app.py
```

A browser tab opens at http://localhost:8501. Log in with any demo account (password `demo1234`):

| Email | Role |
|---|---|
| ananya@demo.com | Job seeker, data analyst, auto-apply ON |
| rahul@demo.com | Job seeker, ROS engineer |
| fathima@demo.com | Job seeker, fresher Python developer |
| hr@demo.com | Recruiter at Demo Analytics Pvt Ltd |

To start again from an empty database, delete `data/jobs.db` and run `seed_demo.py` again.

## 3. Emails

By default **nothing is really emailed**. Every email is saved in `data/outbox` as a `.eml` file (double-click to open it in Outlook or Mail) and shown on the **Emails** page. To send for real:

1. Turn on 2-Step Verification in your Google account, then create an **App Password**.
2. Copy `.env.example` to `.env` and fill in `SMTP_USER`, `SMTP_APP_PASSWORD`, and set `EMAIL_DRY_RUN=false`.
3. Test with your own email address first, never with real HR inboxes.

## 4. Collecting real jobs

On the **Job feed** page, open *Collect new jobs* and tick Infopark / Technopark, or run:

```bash
python scripts/collect_jobs.py infopark technopark
```

The collector checks robots.txt, waits 3 seconds between pages and reads at most 40 job pages per site. **Park websites change their layout.** If it reports `0 job pages found`, open the park's job listing page in your browser, click one job, and copy the pattern of that link into `config.py` (`list_url` and `job_link_pattern`).

## 5. Training

Only the fake job detector uses a trained model, and it is optional (the rule checks always work):

1. Download `fake_job_postings.csv` (EMSCAD dataset) from Kaggle: https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction
2. Put it in `data/`, then run `python scripts/train_fake_model.py`.
3. It prints precision, recall and a confusion matrix (put these in your report) and saves `models/fake_job_model.joblib`, which the app uses automatically.

The matcher uses TF-IDF similarity, which needs no training. Resume parsing uses rules (regex + skills list), which also need no training.

## 6. Tests (accuracy numbers for your report)

```bash
python -m tests.test_contact     # name/email/phone accuracy on 10 resumes
python -m tests.test_skills      # skills found per resume
python -m tests.test_education   # degree, year, CGPA, years of experience
python -m tests.test_ats         # ATS score per resume (strong ~90+, average ~50, weak ~30)
python -m tests.test_matching    # best job for each resume
```

## 7. Automation

```bash
python scripts/run_scheduler.py        # leave running: collects + auto-applies daily at 07:00, reports Mondays 08:00
python scripts/run_scheduler.py --now  # run everything once now
```

## 8. Safety rules built in

- No LinkedIn or Naukri passwords are ever asked for or stored; only profile links.
- Passwords for this app are stored as salted PBKDF2 hashes.
- Auto-apply only at 80%+ match, once per job, never to High-risk jobs or after the closing date, max 10 a day.
- Jobs that ask extra questions are never auto-sent; the questions are emailed to you first.
- Emails are dry-run by default.
- "Match boost" reports a change in match %, not a chance of being hired.

## 9. Publishing online

Vercel cannot run this app: it only runs short serverless functions, and a Streamlit app needs a
server that stays on. Use **Streamlit Community Cloud** (free):

1. Push this folder to GitHub (the `.gitignore` keeps `.env`, the database and real resumes out).
2. Go to https://share.streamlit.io, sign in with GitHub, click **Create app**, choose the repo,
   branch `main`, main file `app.py`, and in *Advanced settings* pick Python 3.11.
3. Click **Deploy**. On the first visit the app fills itself with demo data (password `demo1234`).

Notes: the free host resets files when the app restarts, so accounts and applications made online
are temporary (fine for a demo). Emails stay in dry-run mode unless you add `EMAIL_DRY_RUN`,
`SMTP_USER` and `SMTP_APP_PASSWORD` under the app's **Settings > Secrets**.
