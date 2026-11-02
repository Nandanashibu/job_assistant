"""ATS scores. There are TWO, because real Applicant Tracking Systems work in two steps:

1. resume_quality(profile) -> score out of 100 for the resume on its own.
   Can software read it, are the standard sections there, are bullet points strong
   (action verbs, numbers, sensible length), are skills backed by experience, and is
   it free of things recruiters dislike (personal details, cliches, 'Declaration').
   Most checks give PARTIAL marks, so a score of 100 is hard to reach.

2. job_match(profile, job) -> score out of 100 for ONE job description (like Jobscan).
   Recruiters search the ATS with the job's keywords, so this measures how many of
   the job's skills, important words, title words, experience and degree your resume has.

ats_score(profile) is kept so older code and tests still work.
"""
import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer

from sja.education_experience import split_sections

ACTION_VERBS = {
    "achieved", "analysed", "analyzed", "architected", "automated", "built", "collaborated", "configured",
    "conducted", "contributed", "created", "cut", "debugged", "decreased", "delivered", "deployed", "designed",
    "developed", "documented", "engineered", "established", "evaluated", "executed", "fine-tuned", "fixed",
    "handled", "identified", "implemented", "improved", "increased", "integrated", "launched", "led", "managed",
    "mentored", "migrated", "optimized", "optimised", "organised", "organized", "planned", "presented",
    "programmed", "published", "reduced", "refactored", "researched", "resolved", "saved", "set", "simulated",
    "streamlined", "tested", "trained", "wrote", "cleaned", "merged", "mapped", "classified", "integrated",
}
WEAK_PHRASES = ["responsible for", "worked on", "helped with", "involved in", "duties included", "assisted in",
                "various", "etc."]
CLICHES = ["hard working", "hardworking", "team player", "go-getter", "result oriented", "result-oriented",
           "self-motivated", "self motivated", "dynamic", "honest", "quick learner", "passionate", "dedicated",
           "think outside the box", "best of my knowledge"]
PERSONAL_DETAILS = [r"date of birth", r"\bdob\b", r"marital status", r"\breligion\b", r"father'?s name",
                    r"mother'?s name", r"\bnationality\b", r"\bgender\b", r"\bcaste\b", r"passport no"]
NUMBER = re.compile(r"\d+(?:\.\d+)?\s*(?:%|\+|x\b|k\b|lakh|crore|fps|ms\b|users|students|records|rows|"
                    r"hours|days|minutes|stores|robots|downloads|homes|clients|tests|bugs|endpoints|apps|"
                    r"microservices|requests)|\b\d{2,}[\d,]*\b", re.IGNORECASE)
DATE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|\b(19|20)\d{2}\b", re.IGNORECASE)
HEADER_LINE = re.compile(r"\|.*((19|20)\d{2}|present)", re.IGNORECASE)


# --------------------------------------------------------------------------- helpers
def bullet_points(text):
    """Bullet points from the Experience and Projects sections, with wrapped lines joined."""
    sections = split_sections(text)
    body = "\n".join(sections.get(name, "") for name in ("experience", "projects"))
    if not body.strip():
        return []
    chunks = re.split(r"[•▪●◦]|\n\s*[-*]\s+", body) if re.search(r"[•▪●◦]|\n\s*[-*]\s+", body) else body.splitlines()
    bullets = []
    for chunk in chunks:
        lines = [l.strip() for l in chunk.splitlines() if l.strip() and not HEADER_LINE.search(l)]
        sentence = " ".join(lines)
        if len(sentence.split()) >= 5:
            bullets.append(sentence)
    return bullets


def first_word(sentence):
    words = re.findall(r"[a-zA-Z-]+", sentence.lower())
    return words[0] if words else ""


def scaled(value, full_at, points):
    """Partial marks: value/full_at of the points, never more than the points."""
    if full_at <= 0:
        return points
    return round(points * max(0.0, min(1.0, value / full_at)), 1)


# --------------------------------------------------------------------------- 1. resume quality
def resume_quality(profile):
    """Return (score, checks, tips). checks = [(area, what we checked, points earned, points possible), ...]"""
    text = profile.get("text", "")
    low = text.lower()
    words = len(text.split())
    sections = profile.get("sections", [])
    skills = profile.get("skills", [])
    bullets = bullet_points(text)
    checks, tips = [], []

    def add(area, name, earned, possible, tip=None):
        earned = round(min(earned, possible), 1)
        checks.append((area, name, earned, possible))
        if tip and earned < possible:
            tips.append(tip)

    # A. Contact (10)
    add("Contact", "Email address", 4 if profile.get("email") else 0, 4, "Add a professional email address at the top.")
    add("Contact", "Phone number", 3 if profile.get("phone") else 0, 3, "Add your phone number with country code (+91).")
    add("Contact", "LinkedIn or GitHub link", 3 if (profile.get("linkedin") or profile.get("github")) else 0, 3,
        "Add your LinkedIn link, and GitHub for tech roles.")

    # B. Standard sections (15)
    for name, pts, tip in [
        ("skills", 4, "Add a section titled exactly 'Skills'. ATS software looks for standard headings."),
        ("education", 4, "Add an 'Education' section with degree, college, year and CGPA."),
        ("experience", 4, "Add an 'Experience' or 'Internship' section. Internships, freelance and volunteer work count."),
        ("projects", 3, "Add a 'Projects' section with 2-3 projects, the tools used and the result."),
    ]:
        add("Sections", f"'{name.title()}' section", pts if name in sections else 0, pts, tip)

    # C. Bullet points: the content recruiters actually read (35)
    n = len(bullets)
    add("Impact", "At least 6 bullet points in experience/projects", scaled(n, 6, 5), 5,
        f"Only {n} bullet points found. Describe each job and project in 2-4 bullet points.")
    verb_starts = [b for b in bullets if first_word(b) in ACTION_VERBS]
    verb_ratio = len(verb_starts) / n if n else 0
    add("Impact", f"Bullets starting with an action verb ({verb_ratio:.0%})", scaled(verb_ratio, 0.7, 10), 10,
        "Start most bullet points with an action verb: Built, Developed, Reduced, Automated, Led.")
    numbered = [b for b in bullets if NUMBER.search(b)]
    num_ratio = len(numbered) / n if n else 0
    add("Impact", f"Bullets with numbers or results ({num_ratio:.0%})", scaled(num_ratio, 0.5, 10), 10,
        "Add numbers to at least half of your bullets: '40% faster', '1,200 users', '15 dashboards'.")
    lengths = [len(b.split()) for b in bullets]
    good_length = sum(1 for l in lengths if 8 <= l <= 35) / n if n else 0
    add("Impact", "Bullets are 8-35 words long", scaled(good_length, 0.8, 4), 4,
        "Keep each bullet to one or two lines (8-35 words).")
    weak = [p for p in WEAK_PHRASES if p in low]
    add("Impact", "No weak phrases ('responsible for', 'worked on')", max(0, 3 - len(weak)), 3,
        f"Replace weak phrases ({', '.join(weak)}) with what you achieved.")
    starts = Counter(first_word(b) for b in verb_starts)
    repeated = [v for v, c in starts.items() if c > 3]
    add("Impact", "Varied action verbs", 0 if not verb_starts else 3 if not repeated else 1, 3,
        f"You start many bullets with the same verb ({', '.join(repeated)}). Vary them." if repeated else None)

    # D. Skills (15)
    add("Skills", f"Number of recognised skills ({len(skills)})", scaled(len(skills), 12, 10), 10,
        f"Only {len(skills)} skills recognised. List tools and technologies by their exact names (Python, SQL, Git).")
    proof_text = " ".join(bullets).lower()
    tech = [s for s in skills if s not in {"communication", "teamwork", "problem solving", "leadership", "time management"}]
    proven = [s for s in tech if s in proof_text]
    proof_ratio = len(proven) / len(tech) if tech else 0
    add("Skills", f"Skills backed by experience or projects ({proof_ratio:.0%})", scaled(proof_ratio, 0.4, 5), 5,
        "Mention your key skills inside your experience and project bullets, not only in the skills list.")

    # E. Length and layout (10)
    if 300 <= words <= 900:
        length_points = 5
    elif 200 <= words <= 1200:
        length_points = 3
    else:
        length_points = 0
    add("Layout", f"Length ({words} words; 300-900 is ideal)", length_points, 5,
        "Aim for 300-900 words: one page for freshers, two at most with experience.")
    add("Layout", "Summary or objective at the top", 2 if "summary" in sections else 0, 2,
        "Add a 2-3 line summary at the top: your role, years of experience and top skills.")
    long_lines = [l for l in text.splitlines() if len(l.split()) > 45]
    add("Layout", "No long paragraphs", 3 if not long_lines else 1, 3,
        "Break long paragraphs into short bullet points; ATS and recruiters skim.")

    # F. Things recruiters dislike (15)
    personal = [p for p in PERSONAL_DETAILS if re.search(p, low)]
    add("Clean-up", "No personal details (DOB, marital status, religion...)", 4 if not personal else 0, 4,
        "Remove personal details such as date of birth, marital status, religion and father's name.")
    add("Clean-up", "No 'Declaration' or 'References available'",
        2 if not re.search(r"\bdeclaration\b|i hereby declare|references available", low) else 0, 2,
        "Remove the 'Declaration' line; it wastes space and ATS ignores it.")
    cliches = [c for c in CLICHES if c in low]
    add("Clean-up", "No cliches ('hard working', 'team player')", max(0, 3 - len(cliches)), 3,
        f"Replace cliches ({', '.join(cliches[:4])}) with evidence from your work.")
    first_person = len(re.findall(r"\b(i|me|my)\b", low))
    add("Clean-up", "No first person (I, me, my)", 2 if first_person <= 2 else 0, 2,
        "Write 'Built a dashboard', not 'I built a dashboard'.")
    exp_text = split_sections(text).get("experience", "")
    add("Clean-up", "Dates on experience entries", 2 if (not exp_text or DATE.search(exp_text)) else 0, 2,
        "Add start and end dates (e.g. 'Jun 2024 - Present') to every job and internship.")
    edu = profile.get("education") or []
    add("Clean-up", "Graduation year and score", 2 if edu and edu[0].get("year") and edu[0].get("score") else
        (1 if edu else 0), 2, "Add your graduation year and CGPA or percentage.")

    score = round(sum(c[2] for c in checks))
    return score, checks, tips


# --------------------------------------------------------------------------- 2. match with one job
def important_words(job_text, resume_text, top=15):
    """The job's most important words (TF-IDF), excluding very common words."""
    vectorizer = TfidfVectorizer(stop_words="english", token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+#]{2,}\b")
    try:
        matrix = vectorizer.fit_transform([job_text, resume_text])
    except ValueError:
        return []
    terms = vectorizer.get_feature_names_out()
    row = matrix[0].toarray()[0]
    boring = {"experience", "years", "year", "work", "team", "skills", "required", "requirements", "apply", "send",
              "resume", "email", "looking", "strong", "good", "knowledge", "candidates", "role", "plus", "preferred",
              "join", "company", "hiring", "using", "ability", "including", "build", "building", "working", "cv",
              "freshers", "fresher", "candidates", "office", "week", "days", "understanding", "basic", "need",
              "technopark", "infopark", "cyberpark", "kochi", "trivandrum", "thiruvananthapuram", "kozhikode",
              "lpa", "salary", "day", "comfortable", "careers", "jobs", "advanced", "junior", "senior", "hr",
              "welcome", "website", "level", "graduates", "entry", "date", "batch", "month", "months", "notice", "period", "current", "expected", "ctc", "clients"}
    ranked = sorted(((row[i], terms[i]) for i in range(len(terms)) if row[i] > 0), reverse=True)
    words = []
    for _, term in ranked:
        if any(w in boring for w in term.split()) or re.search(r"example|com\b", term):
            continue
        words.append(term)
        if len(words) == top:
            break
    return words


def job_match(profile, job):
    """Return (score, details, tips) for one job, like an ATS keyword match."""
    resume = profile.get("text", "").lower()
    job_text = f"{job.get('title', '')}\n{job.get('description', '')}"
    have = set(profile.get("skills", []))
    company_words = set(re.findall(r"[a-z]+", (job.get("company") or "").lower()))
    clean_job_text = re.sub(r"\S+@\S+|https?://\S+", " ", job_text)             # drop emails and links
    tips = []

    needed = job.get("skills", [])
    matched = [s for s in needed if s in have]
    missing = [s for s in needed if s not in have]
    skill_points = 50 * (len(matched) / len(needed)) if needed else 25
    if missing:
        tips.append(f"Add these skills if you have them, using the job's exact words: {', '.join(missing)}.")

    keywords = [k for k in important_words(clean_job_text, profile.get("text", ""), top=20)
                if k not in company_words][:15]
    found = [k for k in keywords if k in resume]
    absent = [k for k in keywords if k not in resume]
    keyword_points = 20 * (len(found) / len(keywords)) if keywords else 10
    if absent:
        tips.append(f"Important words from the job that are not in your resume: {', '.join(absent[:8])}.")

    title_words = [w for w in re.findall(r"[a-z+#.]+", job.get("title", "").lower())
                   if len(w) > 2 and w not in {"and", "the", "for", "with", "senior", "junior", "fresher", "lead"}]
    title_found = [w for w in title_words if w in resume]
    title_points = 10 * (len(title_found) / len(title_words)) if title_words else 5
    if title_words and len(title_found) < len(title_words):
        tips.append(f"Use the job title '{job.get('title')}' in your summary if it describes you.")

    need_years = job.get("min_years") or 0
    have_years = profile.get("experience_years", 0)
    years_points = 10 if have_years >= need_years else 10 * max(0.0, 1 - (need_years - have_years) / 3)
    if have_years < need_years:
        tips.append(f"The job asks for {need_years:g}+ years; you show {have_years:g}. Add internships and freelance work with dates.")

    wants_degree = re.search(r"\b(b\.?\s?tech|b\.?e\b|degree|graduate|bachelor|mca|bca|b\.?sc|m\.?tech)\b", job_text, re.I)
    edu = profile.get("education") or []
    degree_points = 10 if (not wants_degree or (edu and edu[0].get("level", 0) >= 4)) else 3

    score = round(skill_points + keyword_points + title_points + years_points + degree_points)
    details = {"matched_skills": matched, "missing_skills": missing, "keywords_found": found,
               "keywords_missing": absent, "title_words_found": title_found}
    return min(score, 100), details, tips


# --------------------------------------------------------------------------- 3. file format (from the real file)
def format_checks(layout, experience_years=0):
    """Checks on the actual file. layout comes from resume_layout.analyse(). Returns (checks, tips) worth 25 points."""
    checks, tips = [], []

    def add(name, earned, possible, tip):
        checks.append(("Format", name, round(earned, 1), possible))
        if earned < possible:
            tips.append(tip)

    if layout is None:
        return [("Format", "File could not be analysed", 12, 25)], ["Upload a text-based PDF or DOCX so the layout can be checked."]
    add("Text can be read (not a scanned image)", 6 if layout["chars_per_page"] >= 400 else 2 if layout["chars_per_page"] >= 150 else 0, 6,
        "Very little text could be read. If your resume is a scan or an image, export it from Word or Google Docs instead.")
    add("Single-column layout", 5 if layout["columns"] < 0.5 else 0, 5,
        "Use a single column. ATS software reads two-column resumes line by line and mixes the columns together.")
    add("No tables or text boxes", 3 if not (layout["tables"] or layout["text_boxes"]) else 0, 3,
        "Remove tables and text boxes; put the same content in plain bullet points.")
    add("No photos, icons or graphics", 3 if layout["images"] == 0 else 1 if layout["images"] <= 2 else 0, 3,
        "Remove the photo, icons and skill bars/charts. ATS cannot read images, and Indian IT companies do not need a photo.")
    add("Contact details not in header/footer", 3 if not layout["contact_in_header_footer"] else 0, 3,
        "Move your email and phone out of the page header/footer into the main text; many ATS skip headers.")
    ideal = 1 if experience_years < 3 else 2
    add(f"Length: {layout['pages']} page(s)", 3 if layout["pages"] <= ideal else 1 if layout["pages"] <= ideal + 1 else 0, 3,
        f"Keep it to {ideal} page{'s' if ideal > 1 else ''} at your experience level.")
    fonts_ok = layout["font_families"] <= 3 and (layout["body_font_size"] == 0 or layout["body_font_size"] >= 9.5)
    add("Simple fonts, readable size", 2 if fonts_ok else 0, 2,
        "Use one or two standard fonts (Calibri, Arial, Times) and keep body text at 10-12 pt.")
    return checks, tips


# --------------------------------------------------------------------------- 4. keywords for your target jobs
def target_jobs(profile, jobs, roles=(), limit=5):
    """The real jobs you are aiming for: titles that match your preferred roles, else your best matches."""
    from sja.matcher import rank_jobs, role_matches
    jobs = [j for j in jobs if j.get("fake_level") != "High"]
    if roles:
        by_role = [j for j in jobs if role_matches(roles, j["title"])]
        if by_role:
            jobs = by_role
    return [job for job, _ in rank_jobs(profile, jobs, roles)[:limit]]


def keyword_match(profile, jobs):
    """Average ATS match over the target jobs + the missing words they ask for most."""
    if not jobs:
        return None, [], []
    scores, missing_skills, missing_words = [], Counter(), Counter()
    for job in jobs:
        score, details, _ = job_match(profile, job)
        scores.append(score)
        missing_skills.update(details["missing_skills"])
        missing_words.update(details["keywords_missing"])
    return sum(scores) / len(scores), missing_skills.most_common(8), missing_words.most_common(8)


# --------------------------------------------------------------------------- 5. the overall score
WEIGHTS = {"Format": 25, "Content": 35, "Keywords": 40}


def full_ats(profile, file_path=None, jobs=(), roles=()):
    """The ATS score shown to users.

    Format   (25%) - the real file: columns, tables, images, header/footer, pages, fonts
    Content  (35%) - sections, bullet points, verbs, numbers, skills, clean-up
    Keywords (40%) - how well the resume matches the REAL jobs you target (like Jobscan)
    If there are no jobs yet, Keywords is left out and the other two are scaled to 100.
    """
    from sja.resume_layout import analyse
    layout = analyse(file_path) if file_path else None
    f_checks, f_tips = format_checks(layout, profile.get("experience_years", 0))
    format_pct = 100 * sum(c[2] for c in f_checks) / sum(c[3] for c in f_checks)

    content_pct, c_checks, c_tips = resume_quality(profile)

    targets = target_jobs(profile, list(jobs), roles)
    keyword_pct, missing_skills, missing_words = keyword_match(profile, targets)

    parts = {"Format": format_pct, "Content": content_pct}
    if keyword_pct is not None:
        parts["Keywords"] = keyword_pct
    total_weight = sum(WEIGHTS[p] for p in parts)
    score = round(sum(parts[p] * WEIGHTS[p] for p in parts) / total_weight)

    k_tips = []
    if missing_skills:
        k_tips.append("Skills your target jobs ask for that your resume lacks: "
                      + ", ".join(f"{s} ({n}/{len(targets)} jobs)" for s, n in missing_skills[:6]) + ".")
    if missing_words:
        k_tips.append("Words from your target jobs to use (only if true for you): "
                      + ", ".join(w for w, _ in missing_words[:8]) + ".")

    # biggest point losses first, weighted by each part's share of the score
    lost = []
    for area, name, earned, possible in f_checks:
        lost.append(((possible - earned) * WEIGHTS["Format"] / 25, area, name))
    for area, name, earned, possible in c_checks:
        lost.append(((possible - earned) * WEIGHTS["Content"] / 100, area, name))
    tips = k_tips + f_tips + c_tips
    return {
        "score": score,
        "parts": {p: round(v) for p, v in parts.items()},
        "checks": f_checks + c_checks,
        "tips": tips,
        "layout": layout,
        "target_jobs": targets,
        "missing_skills": missing_skills,
        "missing_words": missing_words,
    }


# --------------------------------------------------------------------------- old name, kept for compatibility
def ats_score(profile):
    """Same as resume_quality but returns checks as (name, passed, earned, possible) like Lesson 6."""
    score, checks, tips = resume_quality(profile)
    return score, [(f"{area}: {name}", earned >= possible, earned, possible) for area, name, earned, possible in checks], tips


def grade(score):
    if score >= 85:
        return "Strong"
    if score >= 65:
        return "Good"
    if score >= 45:
        return "Fair"
    return "Needs work"
