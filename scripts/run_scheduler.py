"""Keep this running (in its own terminal) to automate the app:
   * every day at 07:00  -> collect jobs, then run auto-apply
   * every Monday 08:00  -> email weekly skills reports

   python scripts/run_scheduler.py            (leave the window open)
   python scripts/run_scheduler.py --now      (run everything once, right now)

On Windows you can instead use Task Scheduler to run collect_jobs.py, auto_apply.py
and weekly_report.py at those times.
"""
import sys
import time
from datetime import datetime

import _path  # noqa: F401
from sja.applier import auto_apply_everyone
from sja.collector import collect_all
from weekly_report import report_for
from sja import applier, database as db

SOURCES = ["sample", "infopark", "technopark"]   # edit to choose what is collected every day


def daily():
    new, log = collect_all(SOURCES)
    print("\n".join(log))
    print("\n".join(auto_apply_everyone()) or "Auto-apply: nothing new.")


def weekly():
    for user in db.all_seekers():
        body = report_for(user)
        if body:
            print(user["email"], applier.notify(user, "Your weekly skills report", body))


if __name__ == "__main__":
    if "--now" in sys.argv:
        daily()
        weekly()
        sys.exit()
    done = set()
    print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        now = datetime.now()
        if now.hour == 7 and ("daily", now.date()) not in done:
            daily()
            done.add(("daily", now.date()))
        if now.weekday() == 0 and now.hour == 8 and ("weekly", now.date()) not in done:
            weekly()
            done.add(("weekly", now.date()))
        time.sleep(60)
