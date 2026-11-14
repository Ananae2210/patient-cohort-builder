"""
PHASE 2 - Natural language to SQL with a free LLM (Week 2)

Free options only: Gemini via Google AI Studio (free tier, key in your .env),
Groq, GitHub Models, or a local model with Ollama. Start with Gemini because
you've already set up google-genai.

Don't start this file until Phase 1 is done and Week 2 has covered JSON output.
"""

from pathlib import Path

SCHEMA_DOC = (Path(__file__).resolve().parent.parent / "docs" / "schema.md").read_text(encoding="utf-8")


def build_prompt(question: str) -> str:
    # TODO: combine instructions + SCHEMA_DOC + the user's question.
    # Things your prompt must tell the model (each one fixes a real mistake you'll see):
    #   - SQLite dialect only
    #   - today is 2026-11-01 and how to compute age
    #   - filter conditions/labs by code, not description
    #   - "their HbA1c" means the most recent value
    #   - SELECT statements only
    # Then add 2-3 example question -> SQL pairs (few-shot). Use your Exercise 1 queries.
    raise NotImplementedError


def question_to_sql(question: str) -> dict:
    """Return {"sql": ..., "explanation": ..., "assumptions": [...]}.

    TODO:
      - call the LLM and ask for JSON output (response_mime_type="application/json" in Gemini)
      - parse it with json.loads and handle the case where parsing fails
      - "assumptions" is for the UI: e.g. "Used the most recent HbA1c".
        This is your designer superpower: show users what the AI assumed.
    """
    raise NotImplementedError
