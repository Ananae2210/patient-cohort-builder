"""
PHASE 1 - A cohort builder WITHOUT AI (end of Week 1)

Before the LLM writes SQL, you write a normal Python function that builds the
SQL from structured filters. This becomes:
  1. your baseline: the "dropdown filters" version of the app, and
  2. a safe fallback when the LLM's answer can't be trusted.

You write all of this. Delete the `raise NotImplementedError` lines as you go.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cohort.db"
TODAY = "2026-11-01"


@dataclass
class CohortFilters:
    gender: str | None = None          # "F", "M" or None for any
    min_age: int | None = None         # inclusive
    max_age: int | None = None         # inclusive
    condition_codes: list[str] | None = None   # patient must have ALL of these SNOMED codes
    hba1c_above: float | None = None   # applied to the most recent HbA1c


def get_connection() -> sqlite3.Connection:
    # TODO: open and return a connection to DB_PATH
    raise NotImplementedError


def build_sql(f: CohortFilters) -> tuple[str, list]:
    """Return (sql, params) for the cohort described by `f`.

    TODO:
      - Start from SELECT ... FROM patients p WHERE 1=1
      - Add one AND clause per filter that is not None
      - Use ? placeholders and a params list. NEVER paste values into the SQL
        string with f-strings (that's how SQL injection happens; ask me why
        if you're curious).
      - Return columns useful for a dashboard: id, first, last, gender, age,
        latest_hba1c
    """
    raise NotImplementedError


def get_cohort(f: CohortFilters) -> pd.DataFrame:
    # TODO: build the SQL, run it with pd.read_sql(sql, con, params=params), return the DataFrame
    raise NotImplementedError


if __name__ == "__main__":
    # When this prints 16 rows, Phase 1 is done.
    df = get_cohort(CohortFilters(gender="F", min_age=51,
                                  condition_codes=["44054006"], hba1c_above=8))
    print(df)
    print(len(df), "patients (expected 16)")
