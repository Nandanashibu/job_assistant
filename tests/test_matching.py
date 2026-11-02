"""Does each sample resume's best job match its role?   python -m tests.test_matching"""
import json
from sja import database as db
from sja.collector import collect_all
from sja.matcher import rank_jobs
from sja.resume_parser import parse_resume

db.init_db()
collect_all(["sample"])
jobs = [j for j in db.active_jobs() if j["fake_level"] != "High"]
with open("data/answer_key.json") as f:
    people = json.load(f)
for person in people:
    ranked = rank_jobs(parse_resume("data/" + person["file"]), jobs)
    print(f"{person['role'][:30]:30} -> " + " | ".join(f"{j['title'][:24]} {r['match']:.0f}%" for j, r in ranked[:3]))
