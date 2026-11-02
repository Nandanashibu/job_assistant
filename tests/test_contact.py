import json
from sja.resume_reader import extract_text
from sja.contact_info import extract_contact

with open("data/answer_key.json") as f:
    answers = json.load(f)

correct = total = 0
for person in answers:
    text = extract_text("data/" + person["file"])
    found = extract_contact(text)
    print(person["file"])
    for field in ["name", "email", "phone"]:
        ok = found[field] == person[field]
        correct += ok
        total += 1
        mark = "OK  " if ok else "MISS"
        print(f"   {mark} {field:6}: found '{found[field]}'   expected '{person[field]}'")

print("-" * 50)
print(f"Accuracy: {correct}/{total} = {100 * correct / total:.0f}%")
