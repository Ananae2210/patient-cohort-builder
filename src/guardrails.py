"""Checks LLM-written SQL before it runs.

Two layers of safety:
  1. is_safe() here: fast text checks with a clear message for the user.
  2. db.connect_readonly(): the database is opened read-only and SQLite's
     authorizer refuses anything that isn't a read from the 4 known tables.
Layer 2 is the real protection. Layer 1 gives friendly error messages.
"""

import re

from src.db import ALLOWED_TABLES

BLOCKED_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "create",
                    "attach", "detach", "pragma", "vacuum", "reindex", "analyze",
                    "load_extension", "begin", "commit", "rollback", "savepoint"]


def _strip_strings_and_comments(sql: str) -> str:
    """Remove string literals and comments so keywords inside them don't trigger false alarms."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)
    return sql


def clean_sql(sql: str) -> str:
    """Remove markdown fences and a trailing semicolon that LLMs often add."""
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip().rstrip(";").strip()
    return sql


def is_safe(sql: str) -> tuple[bool, str]:
    """Return (ok, reason). reason is empty when ok."""
    if not sql or not sql.strip():
        return False, "The query is empty."
    body = _strip_strings_and_comments(clean_sql(sql))
    lowered = body.lower()

    if ";" in body:
        return False, "Only one SQL statement is allowed."
    if not re.match(r"^\s*(select|with)\b", lowered):
        return False, "Only SELECT queries are allowed."
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", lowered):
            return False, f"The query uses a blocked keyword: {kw.upper()}."

    # Every name after FROM/JOIN must be a known table or a CTE defined in the query.
    ctes = set(re.findall(r"(?:with|,)\s*(?:recursive\s+)?([a-z_][a-z0-9_]*)\s+as\s*\(", lowered))
    for name in re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", lowered):
        if name not in ALLOWED_TABLES and name not in ctes:
            return False, f"Unknown table: {name}."
    return True, ""
