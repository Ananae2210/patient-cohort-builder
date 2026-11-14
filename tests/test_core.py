"""Quick checks that need no API key (no AI calls are made). Run from the cohort-builder folder:
    python tests/test_core.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.db as db  # noqa: E402
from src.cohort import CONDITIONS, CohortFilters, get_cohort  # noqa: E402
from src.db import enrich_patients, run_query  # noqa: E402
from src.guardrails import is_safe  # noqa: E402
from src.limits import RateLimiter  # noqa: E402
from src.nl_to_sql import ask  # noqa: E402


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

# Edge cases
asthma = CONDITIONS["Asthma"]
results.append(check("conditions: only current asthma by default (40)",
                     len(get_cohort(CohortFilters(condition_codes=[asthma]))) == 40))
results.append(check("conditions: past asthma included on request (62)",
                     len(get_cohort(CohortFilters(condition_codes=[asthma], include_past=True))) == 62))

big = run_query("SELECT id FROM patients", max_rows=100)
results.append(check("large results are flagged, not cut off silently",
                     len(big) == 100 and big.attrs["truncated"] is True))
results.append(check("normal results are not flagged",
                     run_query("SELECT id FROM patients").attrs["truncated"] is False))

all_ids = run_query("SELECT id FROM patients")["id"].tolist()
db.ENRICH_BATCH = 150  # force several batches
enriched = enrich_patients(all_ids)
results.append(check("patient details work across batches (800 rows, no duplicates)",
                     len(enriched) == 800 and enriched["id"].is_unique))

lim = RateLimiter(limit=2, window_s=60)
results.append(check("rate limit: allows 2, blocks the 3rd, frees up after the window",
                     lim.try_acquire(0) and lim.try_acquire(1) and not lim.try_acquire(2)
                     and lim.try_acquire(61)))

results.append(check("very long questions are refused before calling the AI",
                     ask("x" * 1000).error is not None))
results.append(check("empty questions are refused before calling the AI", ask("   ").error is not None))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
