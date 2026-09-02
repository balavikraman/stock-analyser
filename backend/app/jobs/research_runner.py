from __future__ import annotations
import json
from ..db import SessionLocal, init_db
from ..services.research_runner import execute_research_run

def main() -> int:
    init_db()
    with SessionLocal() as db:
        result=execute_research_run(db, triggered_by="scheduler")
    print(json.dumps(result, default=str))
    return 1 if result.get("execution") == "failed" else 0

if __name__ == "__main__": raise SystemExit(main())
