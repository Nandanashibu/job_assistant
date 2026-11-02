"""Collect jobs once.   python scripts/collect_jobs.py            (sample jobs only)
                       python scripts/collect_jobs.py infopark technopark remotive"""
import sys

import _path  # noqa: F401
from sja.collector import collect_all

if __name__ == "__main__":
    sources = sys.argv[1:] or ["sample"]
    new, log = collect_all(sources)
    print("\n".join(log))
