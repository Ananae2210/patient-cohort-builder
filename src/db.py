"""Database access: read-only connections and helpers shared by the app and the eval."""

import sqlite3
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "cohort.db"
TODAY = "2026-11-01"  # fixed "today" for the synthetic data

ALLOWED_TABLES = {"patients", "conditions", "observations", "medications"}

# Age in whole years on TODAY. `{col}` is a birthdate column such as p.birthdate.
AGE_SQL = (
    "(CAST(strftime('%Y', '{today}') AS INTEGER) - CAST(strftime('%Y', {col}) AS INTEGER)"
    " - (strftime('%m-%d', '{today}') < strftime('%m-%d', {col})))"
)


def age_sql(col: str = "p.birthdate") -> str:
    return AGE_SQL.format(today=TODAY, col=col)


def latest_obs_sql(code_param: str = "?", patient_col: str = "p.id") -> str:
    """Correlated subquery for a patient's most recent value of one LOINC code."""
    return (f"(SELECT o.value FROM observations o WHERE o.patient = {patient_col} "
            f"AND o.code = {code_param} ORDER BY o.date DESC LIMIT 1)")


def _authorizer(action, arg1, arg2, dbname, source):
    """SQLite calls this for every operation while compiling a statement.

    Only reads are allowed, and only from the 4 known tables. This is the real
    safety net: even if the text checks in guardrails.py miss something, SQLite
    refuses to compile a write, PRAGMA, ATTACH, etc.
    """
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        # arg1 = table name. sqlite_master reads are needed internally.
        if arg1 in ALLOWED_TABLES or arg1 in ("sqlite_master", "sqlite_schema"):
            return sqlite3.SQLITE_OK
        # CTE / subquery aliases are not real tables and don't trigger READ for unknown names,
        # so anything else here is a table we don't allow.
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        # arg2 = function name. Block functions that touch files or load code.
        if arg2 and arg2.lower() in {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_RECURSIVE:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def connect_readonly(timeout_s: float = 5.0) -> sqlite3.Connection:
    """Open the database read-only, with the authorizer and a time limit per connection."""
    con = sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True, check_same_thread=False)
    con.set_authorizer(_authorizer)
    # Stop runaway queries (e.g. an accidental cross join) after timeout_s seconds.
    deadline = time.monotonic() + timeout_s
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    return con


def run_query(sql: str, params: list | tuple = (), timeout_s: float = 5.0, max_rows: int = 5000) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame (at most `max_rows` rows)."""
    con = connect_readonly(timeout_s)
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows)
        return pd.DataFrame(rows, columns=cols)
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise TimeoutError(f"Query took longer than {timeout_s:.0f} seconds and was stopped.") from e
        raise
    finally:
        con.close()


def population_size() -> int:
    return int(run_query("SELECT COUNT(*) AS n FROM patients").iloc[0, 0])


def enrich_patients(ids: list[str]) -> pd.DataFrame:
    """Standard dashboard columns for a list of patient ids, whatever query produced them."""
    if not ids:
        return pd.DataFrame(columns=["id", "name", "gender", "age", "race", "city",
                                     "latest_hba1c", "latest_bmi", "latest_sbp", "conditions"])
    placeholders = ",".join("?" * len(ids))
    sql = f"""
        SELECT p.id,
               p.first || ' ' || p.last AS name,
               p.gender,
               {age_sql()} AS age,
               p.race,
               p.city,
               {latest_obs_sql("'4548-4'")} AS latest_hba1c,
               {latest_obs_sql("'39156-5'")} AS latest_bmi,
               {latest_obs_sql("'8480-6'")} AS latest_sbp,
               (SELECT group_concat(DISTINCT replace(replace(c.description, ' (disorder)', ''), ' (finding)', ''))
                  FROM conditions c WHERE c.patient = p.id AND c.stop IS NULL) AS conditions
        FROM patients p
        WHERE p.id IN ({placeholders})
        ORDER BY p.last, p.first
    """
    return run_query(sql, ids, max_rows=len(ids) + 1)
