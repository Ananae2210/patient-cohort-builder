"""
EXERCISE 1 - Talk to the patient database in plain SQL (about 60-90 minutes)

Why this matters: later, an LLM will write SQL for you. You can only judge
whether its SQL is right if you can write the same query yourself. So before
any AI, you build the cohort by hand.

How to run (from the cohort-builder folder, with your venv active):

    python exercises/ex01_first_queries.py

Each task prints your result next to the expected answer, and a tick if they
match. Read docs/schema.md first. Treat 2026-11-01 as "today" when you work
out ages, so your answers match.

Rules: write every query yourself. If you get stuck for more than 15 minutes
on one, paste your attempt and the error into the thread and I'll explain
what's going wrong (I won't just hand you the answer).
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Make the ✓ / ✗ marks print on the Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cohort.db"
con = sqlite3.connect(DB_PATH)


def run(sql: str) -> pd.DataFrame:
    """Run a SQL query and return the result as a pandas DataFrame."""
    return pd.read_sql(sql, con)


def check(task: str, sql: str, expected):
    """Run your query, show the result and compare the first value to the expected answer."""
    print(f"\n=== {task} ===")
    if not sql.strip():
        print("  (not written yet)")
        return
    try:
        df = run(sql)
    except Exception as e:  # show the error instead of crashing, so you can read it
        print(f"  SQL error: {e}")
        return
    print(df.head(10).to_string(index=False))
    got = df.iloc[0, 0] if len(df) else None
    ok = got is not None and abs(float(got) - float(expected)) < 0.01
    print(f"  your answer: {got}   expected: {expected}   {'✓' if ok else '✗'}")


# --- Warm-up: look around -------------------------------------------------
# Nothing to write here. Run the file once and read what this prints.
print("Tables:", run("SELECT name FROM sqlite_master WHERE type='table'")["name"].tolist())
print(run("SELECT * FROM patients LIMIT 3").to_string(index=False))


# --- Task 1 ---------------------------------------------------------------
# How many patients are in the database?
# Hint: COUNT(*)
# TODO: write your SQL between the triple quotes
q1 = """
"""
check("Task 1: total patients", q1, 800)


# --- Task 2 ---------------------------------------------------------------
# How many patients are women?
# Hint: look at the values in the gender column first (Task 1's warm-up output helps).
# TODO
q2 = """
"""
check("Task 2: women", q2, 389)


# --- Task 3 ---------------------------------------------------------------
# How many different patients have type 2 diabetes?
# Hints: the condition lives in the conditions table. Filter on the SNOMED code
# (see docs/schema.md), not the description text. One patient could appear more
# than once, so think about COUNT(DISTINCT ...).
# TODO
q3 = """
"""
check("Task 3: patients with type 2 diabetes", q3, 177)


# --- Task 4 ---------------------------------------------------------------
# How many patients are OVER 50 (strictly older than 50) on 2026-11-01?
# Hints: birthdate is text like '1971-04-09'. SQLite has no AGE() function.
# Start with the year difference using strftime('%Y', ...), then fix it for
# people whose birthday hasn't happened yet this year (compare '%m-%d').
# Getting this exactly right is the hardest part of the exercise.
# TODO
q4 = """
"""
check("Task 4: patients over 50", q4, 401)


# --- Task 5 ---------------------------------------------------------------
# How many patients have BOTH type 2 diabetes AND essential hypertension?
# Hint: there are at least three ways (INTERSECT, IN + IN, or a self-JOIN).
# Pick one, then try a second way and check you get the same number.
# TODO
q5 = """
"""
check("Task 5: diabetes AND hypertension", q5, 67)


# --- Task 6 (the real thing) ----------------------------------------------
# "Diabetic women over 50 with an HbA1c above 8"
# Count the women over 50 with type 2 diabetes whose MOST RECENT HbA1c
# result is above 8.
#
# Hints:
#   - HbA1c is LOINC code '4548-4' in observations.
#   - Patients have several HbA1c results over time. A clinician means the
#     latest one. A correlated subquery (ORDER BY date DESC LIMIT 1) or a
#     window function (ROW_NUMBER() OVER (PARTITION BY ...)) both work.
#   - Reuse your age logic from Task 4.
# TODO
q6 = """
"""
check("Task 6: the cohort", q6, 16)


# --- Reflection (write your answers as comments) ---------------------------
# If you ignore "most recent" and count anyone who EVER had an HbA1c above 8,
# you get 17 instead of 16.
#   a) Which reading is a better match for what a clinician means?
#   b) The words "an HbA1c above 8" don't say which one. How would you want
#      your app to show the user which reading it chose? (Think as a designer.)
# Your answers:
#   a)
#   b)
