import json
from sja.resume_reader import extract_text
from sja.skills import find_skills

with open("data/answer_key.json") as f:
    people = json.load(f)

for person in people:
    skills = find_skills(extract_text("data/" + person["file"]))
    print(f"{person['role']} ({len(skills)} skills)")
    print("   " + ", ".join(skills))
    print()
