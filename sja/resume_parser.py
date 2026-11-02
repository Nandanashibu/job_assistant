from sja.resume_reader import extract_text
from sja.contact_info import extract_contact
from sja.skills import find_skills
from sja.education_experience import split_sections, find_education, find_experience_years


def parse_resume(path):
    """Read a resume file and return everything we know about the person."""
    text = extract_text(path)
    sections = split_sections(text)
    profile = extract_contact(text)                 # name, email, phone, linkedin, github
    profile["skills"] = find_skills(text)
    profile["education"] = find_education(sections)
    profile["experience_years"] = find_experience_years(sections)
    profile["sections"] = [s for s in sections if s not in ("header", "other")]
    profile["text"] = text
    return profile


if __name__ == "__main__":
    profile = parse_resume("data/resume.pdf")
    for key, value in profile.items():
        if key != "text":
            print(f"{key:17}: {value}")
