import json
from sja.resume_reader import extract_text
from sja.education_experience import split_sections, find_education, find_experience_years

with open("data/answer_key.json") as f:
    people = json.load(f)

for person in people:
    sections = split_sections(extract_text("data/" + person["file"]))
    education = find_education(sections)
    top = education[0] if education else {"degree": "-", "year": "", "score": ""}
    years = find_experience_years(sections)
    print(f"{person['name']:18} | {top['degree'][:35]:35} | {top['year']} | {top['score']:5} | {years} yrs")
