import json
from sja.resume_parser import parse_resume
from sja.ats import ats_score, grade

with open("data/answer_key.json") as f:
    people = json.load(f)

for person in people:
    profile = parse_resume("data/" + person["file"])
    score, checks, tips = ats_score(profile)
    print(f"{person['name']:18} {score:3}/100  {grade(score):10}  tips: {len(tips)}")
