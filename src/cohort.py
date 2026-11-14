"""
Phase 1: a cohort builder WITHOUT AI.

Builds parameterised SQL from structured filters. Used as:
  - the "Filters" mode in the dashboard, and
  - a known-good reference when checking the LLM.

The blank version you can write yourself is in exercises/practice/cohort.py.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import age_sql, latest_obs_sql, run_query  # noqa: E402

# Friendly names for the filter UI → SNOMED-CT codes
CONDITIONS = {
    "Type 2 diabetes": "44054006",
    "Prediabetes": "15777000",
    "Hypertension": "59621000",
    "Hyperlipidemia": "55822004",
    "Obesity": "162864005",
    "Chronic kidney disease stage 3": "433144002",
    "Coronary heart disease": "53741008",
    "Asthma": "195967001",
    "Depression": "370143000",
}

MEDICATIONS = {
    "Metformin": "860975",
    "Insulin": "106892",
    "Lisinopril": "314076",
    "Atorvastatin": "259255",
}

HBA1C, BMI, SBP = "4548-4", "39156-5", "8480-6"


@dataclass
class CohortFilters:
    gender: str | None = None                      # "F", "M" or None
    min_age: int | None = None                     # inclusive
    max_age: int | None = None                     # inclusive
    condition_codes: list[str] = field(default_factory=list)   # must have ALL
    medication_codes: list[str] = field(default_factory=list)  # must have ALL
    include_past: bool = False   # False: only current conditions/medications (stop IS NULL)
    hba1c_above: float | None = None               # latest HbA1c, strictly above
    hba1c_below: float | None = None               # latest HbA1c, strictly below
    bmi_at_least: float | None = None              # latest BMI, inclusive
    city: str | None = None


def build_sql(f: CohortFilters) -> tuple[str, list]:
    """Return (sql, params). Values always go in params, never into the SQL text."""
    age = age_sql("p.birthdate")
    where, params = ["1=1"], []

    if f.gender:
        where.append("p.gender = ?")
        params.append(f.gender)
    if f.min_age is not None:
        where.append(f"{age} >= ?")
        params.append(int(f.min_age))
    if f.max_age is not None:
        where.append(f"{age} <= ?")
        params.append(int(f.max_age))
    current = "" if f.include_past else " AND stop IS NULL"
    for code in f.condition_codes:
        where.append(f"p.id IN (SELECT patient FROM conditions WHERE code = ?{current})")
        params.append(code)
    for code in f.medication_codes:
        where.append(f"p.id IN (SELECT patient FROM medications WHERE code = ?{current})")
        params.append(code)
    if f.hba1c_above is not None:
        where.append(f"{latest_obs_sql()} > ?")
        params += [HBA1C, float(f.hba1c_above)]
    if f.hba1c_below is not None:
        where.append(f"{latest_obs_sql()} < ?")
        params += [HBA1C, float(f.hba1c_below)]
    if f.bmi_at_least is not None:
        where.append(f"{latest_obs_sql()} >= ?")
        params += [BMI, float(f.bmi_at_least)]
    if f.city:
        where.append("p.city = ?")
        params.append(f.city)

    sql = (f"SELECT p.id, p.first, p.last, p.gender, {age} AS age\n"
           f"FROM patients p\nWHERE " + "\n  AND ".join(where) + "\nORDER BY p.last, p.first")
    return sql, params


def get_cohort(f: CohortFilters) -> pd.DataFrame:
    sql, params = build_sql(f)
    return run_query(sql, params)


if __name__ == "__main__":
    df = get_cohort(CohortFilters(gender="F", min_age=51,
                                  condition_codes=[CONDITIONS["Type 2 diabetes"]], hba1c_above=8))
    print(df.to_string(index=False))
    print(len(df), "patients (expected 16)")
