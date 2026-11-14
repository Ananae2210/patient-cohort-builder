"""
PHASE 3 - Make the LLM's SQL safe to run (Week 2)

Never run SQL from an LLM without checking it. You write these checks.
"""


def is_safe(sql: str) -> tuple[bool, str]:
    """Return (ok, reason).

    TODO, at minimum:
      - only a single statement (no `;` followed by more SQL)
      - must start with SELECT or WITH
      - block INSERT, UPDATE, DELETE, DROP, ALTER, ATTACH, PRAGMA
      - only the 4 known tables
    Bonus: open the database read-only so even a missed check can't change data:
      sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    """
    raise NotImplementedError
