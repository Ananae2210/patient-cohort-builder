"""Quick checks that need no API key. Run from the cohort-builder folder:
    python tests/test_core.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cohort import CONDITIONS, CohortFilters, get_cohort  # noqa: E402
from src.db import run_query  # noqa: E402
from src.guardrails import is_safe  # noqa: E402


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    return cond


results = [
    check("filters: target cohort has 16 patients",
          len(get_cohort(CohortFilters(gender="F", min_age=51, condition_codes=[CONDITIONS["Type 2 diabetes"]],
                                       hba1c_above=8))) == 16),
    check("filters: no filters returns all 800", len(get_cohort(CohortFilters())) == 800),
    check("guardrails: plain SELECT allowed", is_safe("SELECT * FROM patients")[0]),
    check("guardrails: CTE allowed", is_safe("WITH a AS (SELECT id FROM patients) SELECT * FROM a")[0]),
    check("guardrails: DROP blocked", not is_safe("DROP TABLE patients")[0]),
    check("guardrails: stacked statements blocked", not is_safe("SELECT 1; DELETE FROM patients")[0]),
    check("guardrails: unknown table blocked", not is_safe("SELECT * FROM users")[0]),
    check("guardrails: keyword inside a string is fine", is_safe("SELECT * FROM patients WHERE first = 'drop'")[0]),
]

for sql in ["DELETE FROM patients", "PRAGMA table_info(patients)", "ATTACH 'x.db' AS x"]:
    try:
        run_query(sql)
        results.append(check(f"database refuses: {sql}", False))
    except Exception:
        results.append(check(f"database refuses: {sql}", True))

try:
    run_query("SELECT count(*) FROM patients a, patients b, patients c", timeout_s=1)
    results.append(check("runaway query is stopped", False))
except TimeoutError:
    results.append(check("runaway query is stopped", True))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
