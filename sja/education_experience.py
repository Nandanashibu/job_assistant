import re
from datetime import date

# ---------------------------------------------------------------------------
# 1. Split the resume into sections using its headings
# ---------------------------------------------------------------------------
HEADINGS = {
    "education": ["education", "academic background", "qualification", "qualifications"],
    "experience": ["experience", "work experience", "professional experience",
                   "internship", "internships", "employment history"],
    "skills": ["skills", "technical skills", "key skills", "known software"],
    "projects": ["projects", "academic projects"],
    "summary": ["summary", "professional summary", "profile", "objective",
                "career objective", "about me"],
    "other": ["certifications", "certifications & activities", "achievements",
              "hobbies", "declaration", "languages"],
}


def split_sections(text):
    """Return {'education': '...', 'experience': '...', ...}."""
    sections = {"header": []}
    current = "header"
    for line in text.splitlines():
        clean = line.lower().strip(" :")
        new_section = None
        for section, names in HEADINGS.items():
            if clean in names:
                new_section = section
        if new_section:
            current = new_section
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


# ---------------------------------------------------------------------------
# 2. Education: degree, year, CGPA / percentage
# ---------------------------------------------------------------------------
# (pattern, level) - a higher level means a higher degree
DEGREES = [
    (r"ph\.?\s?d", 6),
    (r"m\.?\s?tech|mca|mba|m\.?\s?sc|m\.?\s?com|master", 5),
    (r"b\.?\s?tech|b\.?\s?e\b|bca|bba|b\.?\s?sc|b\.?\s?com|bachelor", 4),
    (r"diploma|polytechnic", 3),
    (r"higher secondary|plus two|class xii|hsc", 2),
    (r"sslc|class x\b|10th", 1),
]
YEAR = re.compile(r"\b(19|20)\d{2}\b")
SCORE = re.compile(r"(?:cgpa|gpa)\s*:?\s*(\d{1,2}(?:\.\d{1,2})?)|(\d{2}(?:\.\d+)?)\s*%", re.IGNORECASE)


def is_degree(line):
    return any(re.search(p, line, re.IGNORECASE) for p, _ in DEGREES)


def find_education(sections):
    lines = sections.get("education", "").splitlines()
    results = []
    for i, line in enumerate(lines):
        for pattern, level in DEGREES:
            if re.search(pattern, line, re.IGNORECASE):
                nearby = " ".join(lines[i:i + 3])        # score is often on the next lines
                # long degree lines wrap, so also read the next line,
                # unless the next line is a different degree
                both = line
                if i + 1 < len(lines) and not is_degree(lines[i + 1]):
                    both += " " + lines[i + 1]
                years = [m.group() for m in YEAR.finditer(both)]
                score = SCORE.search(nearby)
                results.append({
                    "degree": line.split(",")[0].strip(),
                    "level": level,
                    "year": max(years) if years else "",
                    "score": (score.group(1) or score.group(2) + "%") if score else "",
                })
                break
    results.sort(key=lambda d: d["level"], reverse=True)   # highest degree first
    return results


# ---------------------------------------------------------------------------
# 3. Experience: add up date ranges like "Jul 2024 - Present"
# ---------------------------------------------------------------------------
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
RANGE = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})"
    r"\s*(?:-|–|to)\s*"
    r"(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})|present|current|now)",
    re.IGNORECASE)


def month_number(month, year):
    """Turn 'jul', '2024' into one number so we can subtract dates."""
    return int(year) * 12 + MONTHS[month.lower()[:3]]


def find_experience_years(sections):
    text = sections.get("experience", "")
    today = date.today()
    now = today.year * 12 + today.month
    periods = []
    for m in RANGE.finditer(text):
        start = month_number(m.group(1), m.group(2))
        end = month_number(m.group(3), m.group(4)) if m.group(3) else now
        periods.append((start, end))

    # merge overlapping jobs so the same month is not counted twice
    total_months, last_end = 0, 0
    for start, end in sorted(periods):
        start = max(start, last_end + 1)
        if end >= start:
            total_months += end - start + 1
        last_end = max(last_end, end)
    return round(total_months / 12, 1)


if __name__ == "__main__":
    from sja.resume_reader import extract_text
    sections = split_sections(extract_text("data/resume.pdf"))
    print("Sections found:", ", ".join(sections))
    print("Education:")
    for d in find_education(sections):
        print(f"   {d['degree']}  | year {d['year']} | score {d['score']}")
    print("Experience:", find_experience_years(sections), "years")
