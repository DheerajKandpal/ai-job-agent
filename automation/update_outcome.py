"""
update_outcome.py
-----------------
CLI:
    python -m automation.update_outcome <id> <status> [notes]
"""

from __future__ import annotations

import json
import sys

from automation.outcome_tracker import update_outcome


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: update_outcome <id> <status> [notes]")
        return 1

    try:
        application_id = int(sys.argv[1])
    except ValueError:
        print("application id must be an integer")
        return 1

    status = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        result = update_outcome(application_id, status, notes)
    except Exception as exc:
        print(f"Failed to update outcome: {exc}")
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

