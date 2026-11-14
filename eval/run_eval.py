"""
Phase 3: score the English-to-SQL step against eval/golden_questions.csv.

Run from the cohort-builder folder:
    python eval/run_eval.py              # all 13 questions
    python eval/run_eval.py 6 8          # only questions 6 and 8

A question passes when the query returns exactly the expected number of distinct patients.
Results are saved to eval/results_DATE_TIME.csv so you can compare prompt versions.
The free Gemini tier has a per-minute request limit, so there's a pause between questions.

The blank version you can write yourself is in exercises/practice/run_eval.py.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from src.llm import is_configured, model_name, provider  # noqa: E402
from src.nl_to_sql import ask  # noqa: E402

PAUSE_SECONDS = 7  # stays under ~10 requests/minute on the free tier


def main(only_ids: list[int]) -> None:
    ok, why = is_configured()
    if not ok:
        sys.exit(why)

    golden = pd.read_csv(HERE / "golden_questions.csv")
    if only_ids:
        golden = golden[golden["id"].isin(only_ids)]

    print(f"Evaluating {len(golden)} questions with {provider()} / {model_name()}\n")
    rows = []
    for i, g in enumerate(golden.itertuples(index=False)):
        if i:
            time.sleep(PAUSE_SECONDS)
        r = ask(g.question)
        got = len(r.patient_ids) if r.ok else None
        passed = got == g.expected_count
        status = "PASS" if passed else ("ASKED" if r.clarification else "FAIL")
        print(f"[{status}] {g.id:>2}. {g.question}")
        print(f"        expected {g.expected_count}, got {got}, tries {len(r.attempts)}"
              + (f", error: {r.error}" if r.error else "")
              + (f", asked: {r.clarification}" if r.clarification else ""))
        rows.append({"id": g.id, "question": g.question, "expected": g.expected_count, "got": got,
                     "passed": passed, "tries": len(r.attempts),
                     "self_corrected": len(r.attempts) > 1 and r.ok,
                     "clarification": r.clarification, "error": r.error, "sql": r.sql,
                     "assumptions": " | ".join(r.assumptions)})

    df = pd.DataFrame(rows)
    score = int(df["passed"].sum())
    print(f"\nScore: {score}/{len(df)} correct"
          f"  (self-corrected after an error: {int(df['self_corrected'].sum())})")
    out = HERE / f"results_{datetime.now():%Y%m%d_%H%M}.csv"
    df.to_csv(out, index=False)
    print(f"Saved {out}")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]])
