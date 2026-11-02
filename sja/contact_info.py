import re

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"\+?\d[\d -]{8,14}\d")
LINKEDIN_PATTERN = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
GITHUB_PATTERN = re.compile(r"github\.com/[\w-]+", re.IGNORECASE)


def find_email(text):
    match = EMAIL_PATTERN.search(text)
    return match.group() if match else ""


def find_phone(text):
    for match in PHONE_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 10 <= len(digits) <= 12:
            return match.group().strip()
    return ""


def find_link(pattern, text):
    match = pattern.search(text)
    return match.group() if match else ""


def find_name(text):
    for line in text.splitlines()[:5]:
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.replace(".", "").isalpha() for w in words):
            return line
    return ""


def extract_contact(text):
    return {
        "name": find_name(text),
        "email": find_email(text),
        "phone": find_phone(text),
        "linkedin": find_link(LINKEDIN_PATTERN, text),
        "github": find_link(GITHUB_PATTERN, text),
    }


if __name__ == "__main__":
    from sja.resume_reader import extract_text
    text = extract_text("data/resume.pdf")
    for key, value in extract_contact(text).items():
        print(f"{key:9}: {value}")
