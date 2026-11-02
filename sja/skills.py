"""Lesson 4: find skills in any text (resumes AND job descriptions) using data/skills.json."""
import json
import re

import config

with open(config.SKILLS_FILE, encoding="utf-8") as f:
    SKILLS = json.load(f)


def make_pattern(aliases):
    # longest names first, so "react native" is tried before "react"
    aliases = sorted(aliases, key=len, reverse=True)
    options = "|".join(re.escape(a) for a in aliases)
    # no letter/digit right before or after: stops "java" matching inside "javascript"
    return re.compile(rf"(?<![a-z0-9+#])(?:{options})(?![a-z0-9+#])")


PATTERNS = {name: make_pattern(info["aliases"]) for name, info in SKILLS.items()}


def find_skills(text):
    """Return a sorted list of skill names found in the text."""
    text = (text or "").lower()
    found = []
    for name, pattern in PATTERNS.items():
        check = text
        # remove phrases that look like this skill but mean something else
        for phrase in SKILLS[name].get("exclude", []):
            check = check.replace(phrase, " ")
        if pattern.search(check):
            found.append(name)
    return sorted(found)


def skills_by_category(skills):
    groups = {}
    for skill in skills:
        groups.setdefault(category(skill), []).append(skill)
    return groups


def category(skill):
    return SKILLS.get(skill, {}).get("category", "Other")


def learning_link(skill):
    """A free place to learn the skill (falls back to a course search)."""
    link = SKILLS.get(skill, {}).get("learn")
    return link or f"https://www.youtube.com/results?search_query={skill.replace(' ', '+')}+tutorial+for+beginners"


if __name__ == "__main__":
    from sja.resume_reader import extract_text
    skills = find_skills(extract_text("data/resume.pdf"))
    print(f"Found {len(skills)} skills:\n")
    for cat, items in skills_by_category(skills).items():
        print(f"{cat:20}: {', '.join(items)}")
