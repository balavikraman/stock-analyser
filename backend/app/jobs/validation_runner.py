from __future__ import annotations

import argparse
import json
from datetime import date

from ..db import SessionLocal, init_db
from ..services.validation_runner import execute_validation_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Mature prospective stock-analysis outcomes once per market day.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum eligible predictions to process")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="Use a YYYY-MM-DD date; intended for controlled recovery/testing")
    parser.add_argument("--force", action="store_true", help="Rerun even if today's daily job already succeeded")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        result = execute_validation_run(
            db,
            limit=args.limit,
            as_of=args.as_of,
            force=args.force,
            triggered_by="cli",
        )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["execution"] in {"success", "skipped", "active"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
