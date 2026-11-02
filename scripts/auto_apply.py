"""Run auto-apply for every job seeker who switched it on.   python scripts/auto_apply.py"""
import _path  # noqa: F401
from sja.applier import auto_apply_everyone

if __name__ == "__main__":
    log = auto_apply_everyone()
    print("\n".join(log) or "Nothing to apply to.")
