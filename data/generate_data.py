"""
Generate a small, Synthea-style synthetic patient dataset and load it into SQLite.

You don't need to edit this file. Run it once from the project folder:

    python data/generate_data.py

It writes:
    data/csv/patients.csv, conditions.csv, observations.csv, medications.csv
    data/cohort.db   (SQLite database with the same 4 tables)

Everything is fake. The random seed is fixed, so everyone gets the same data
and the expected answers in exercises/ stay correct.

Column names and codes (SNOMED-CT for conditions, LOINC for lab results,
RxNorm for medications) follow the same style as Synthea's CSV export, so
switching to real Synthea data later (Phase 6) needs only small changes.
"""

import csv
import random
import sqlite3
import uuid
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_PATIENTS = 800
TODAY = date(2026, 11, 1)  # fixed "today" so ages never drift

HERE = Path(__file__).resolve().parent
CSV_DIR = HERE / "csv"
DB_PATH = HERE / "cohort.db"

rng = random.Random(SEED)

FIRST_F = ["Asha", "Maria", "Linda", "Priya", "Grace", "Fatima", "Mei", "Sofia",
           "Nora", "Ruth", "Carmen", "Aisha", "Helen", "Divya", "Joan", "Leila"]
FIRST_M = ["Rahul", "James", "Omar", "Wei", "Carlos", "David", "Samuel", "Arjun",
           "Peter", "Kofi", "Luis", "Ethan", "Ravi", "George", "Hassan", "Tom"]
LAST = ["Sharma", "Smith", "Khan", "Garcia", "Chen", "Okafor", "Patel", "Brown",
        "Nguyen", "Lopez", "Iyer", "Miller", "Ali", "Davis", "Kim", "Mehta"]
RACES = [("white", 0.55), ("black", 0.15), ("asian", 0.15), ("hispanic", 0.12), ("other", 0.03)]
CITIES = [("Boston", "Massachusetts"), ("Worcester", "Massachusetts"),
          ("Springfield", "Massachusetts"), ("Cambridge", "Massachusetts"),
          ("Lowell", "Massachusetts"), ("Quincy", "Massachusetts")]

# Conditions (SNOMED-CT code, description as Synthea writes it)
T2D = ("44054006", "Diabetes mellitus type 2 (disorder)")
PREDIABETES = ("15777000", "Prediabetes (finding)")
HTN = ("59621000", "Essential hypertension (disorder)")
HLD = ("55822004", "Hyperlipidemia (disorder)")
OBESITY = ("162864005", "Body mass index 30+ - obesity (finding)")
CKD3 = ("433144002", "Chronic kidney disease stage 3 (disorder)")
CHD = ("53741008", "Coronary heart disease (disorder)")
ASTHMA = ("195967001", "Asthma (disorder)")
DEPRESSION = ("370143000", "Major depressive disorder (disorder)")

# Observations (LOINC code, description, units)
HBA1C = ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%")
BMI = ("39156-5", "Body mass index (BMI) [Ratio]", "kg/m2")
SBP = ("8480-6", "Systolic blood pressure", "mm[Hg]")
LDL = ("18262-6", "Low Density Lipoprotein Cholesterol", "mg/dL")
EGFR = ("33914-3", "Glomerular filtration rate/1.73 sq M.predicted", "mL/min/{1.73_m2}")

# Medications (RxNorm code, description)
METFORMIN = ("860975", "24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet")
INSULIN = ("106892", "insulin isophane human 70 UNT/ML / insulin regular human 30 UNT/ML Injectable Suspension [Humulin]")
LISINOPRIL = ("314076", "lisinopril 10 MG Oral Tablet")
ATORVASTATIN = ("259255", "atorvastatin 80 MG Oral Tablet")


def pick_weighted(options):
    r = rng.random()
    total = 0.0
    for value, weight in options:
        total += weight
        if r <= total:
            return value
    return options[-1][0]


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, max(0, (end - start).days)))


def age_on(birth: date, on: date) -> int:
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def make_patient():
    gender = rng.choice(["F", "M"])
    age = int(min(90, max(18, rng.gauss(52, 17))))
    birth = TODAY - timedelta(days=age * 365 + rng.randint(0, 364))
    city, state = rng.choice(CITIES)
    first = rng.choice(FIRST_F if gender == "F" else FIRST_M)
    return {
        "Id": str(uuid.UUID(int=rng.getrandbits(128))),
        "BIRTHDATE": birth.isoformat(),
        "DEATHDATE": "",
        "FIRST": first,
        "LAST": rng.choice(LAST),
        "GENDER": gender,
        "RACE": pick_weighted(RACES),
        "CITY": city,
        "STATE": state,
    }


def main():
    CSV_DIR.mkdir(exist_ok=True)
    patients, conditions, observations, medications = [], [], [], []

    for _ in range(N_PATIENTS):
        p = make_patient()
        patients.append(p)
        pid = p["Id"]
        birth = date.fromisoformat(p["BIRTHDATE"])
        age = age_on(birth, TODAY)
        adult_since = birth + timedelta(days=18 * 365)

        def add_condition(cond, onset_min_age=25, ongoing=True):
            earliest = max(adult_since, birth + timedelta(days=onset_min_age * 365))
            onset = random_date(min(earliest, TODAY - timedelta(days=200)), TODAY - timedelta(days=180))
            stop = "" if ongoing else random_date(onset, TODAY).isoformat()
            conditions.append({"START": onset.isoformat(), "STOP": stop, "PATIENT": pid,
                               "CODE": cond[0], "DESCRIPTION": cond[1]})
            return onset

        def add_med(med, start):
            medications.append({"START": start.isoformat(), "STOP": "", "PATIENT": pid,
                                "CODE": med[0], "DESCRIPTION": med[1]})

        # Risk rises with age
        age_risk = (age - 18) / 72
        obese = rng.random() < 0.25 + 0.15 * age_risk
        if obese:
            add_condition(OBESITY, 20)

        diabetic = rng.random() < 0.05 + 0.25 * age_risk + (0.12 if obese else 0)
        prediabetic = (not diabetic) and rng.random() < 0.12 + 0.1 * age_risk
        htn = rng.random() < 0.08 + 0.45 * age_risk + (0.08 if obese else 0)
        hld = rng.random() < 0.06 + 0.35 * age_risk
        ckd = rng.random() < (0.02 + 0.10 * age_risk + (0.08 if diabetic else 0))
        chd = age >= 45 and rng.random() < 0.03 + 0.12 * age_risk
        asthma = rng.random() < 0.08
        depression = rng.random() < 0.10

        if diabetic:
            onset = add_condition(T2D, 30)
            add_med(METFORMIN, onset)
        if prediabetic:
            add_condition(PREDIABETES, 25)
        if htn:
            add_med(LISINOPRIL, add_condition(HTN, 30))
        if hld:
            add_med(ATORVASTATIN, add_condition(HLD, 30))
        if ckd:
            add_condition(CKD3, 40)
        if chd:
            add_condition(CHD, 45)
        if asthma:
            add_condition(ASTHMA, 18, ongoing=rng.random() < 0.7)
        if depression:
            add_condition(DEPRESSION, 18, ongoing=rng.random() < 0.6)

        # Each patient gets a lab history: 1-5 visits over the last 3 years
        control = rng.gauss(0, 1)  # how well-controlled this patient is
        n_visits = rng.randint(1, 5)
        visit_dates = sorted(random_date(TODAY - timedelta(days=3 * 365), TODAY) for _ in range(n_visits))
        base_bmi = rng.uniform(31, 42) if obese else rng.uniform(19, 29.5)

        for i, d in enumerate(visit_dates):
            drift = (i - n_visits / 2) * 0.15  # values drift over time
            if diabetic:
                a1c = 8.0 + 1.3 * control + drift + rng.gauss(0, 0.3)
                a1c = min(13.5, max(6.5, a1c))
            elif prediabetic:
                a1c = rng.uniform(5.7, 6.4)
            else:
                a1c = rng.uniform(4.6, 5.6)
            sbp = rng.gauss(142 if htn else 118, 11)
            ldl = rng.gauss(150 if hld else 105, 22)
            egfr = rng.uniform(32, 58) if ckd else rng.gauss(95 - 0.5 * age_risk * 40, 10)

            rows = [(HBA1C, round(a1c, 1)), (BMI, round(base_bmi + rng.gauss(0, 0.8), 1)),
                    (SBP, round(sbp)), (LDL, round(ldl)), (EGFR, round(egfr))]
            # Not every lab is drawn at every visit (realistic gaps)
            for (code, desc, units), value in rows:
                if code == HBA1C[0] and not (diabetic or prediabetic) and rng.random() < 0.5:
                    continue
                if code in (LDL[0], EGFR[0]) and rng.random() < 0.4:
                    continue
                observations.append({"DATE": d.isoformat(), "PATIENT": pid, "CODE": code,
                                     "DESCRIPTION": desc, "VALUE": value, "UNITS": units})

        # Poorly controlled diabetics move on to insulin
        if diabetic and control > 1.0:
            add_med(INSULIN, random_date(TODAY - timedelta(days=700), TODAY - timedelta(days=30)))

    tables = {"patients": patients, "conditions": conditions,
              "observations": observations, "medications": medications}

    for name, rows in tables.items():
        with open(CSV_DIR / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE patients (
            id TEXT PRIMARY KEY, birthdate TEXT NOT NULL, deathdate TEXT,
            first TEXT, last TEXT, gender TEXT, race TEXT, city TEXT, state TEXT);
        CREATE TABLE conditions (
            start TEXT, stop TEXT, patient TEXT REFERENCES patients(id),
            code TEXT, description TEXT);
        CREATE TABLE observations (
            date TEXT, patient TEXT REFERENCES patients(id),
            code TEXT, description TEXT, value REAL, units TEXT);
        CREATE TABLE medications (
            start TEXT, stop TEXT, patient TEXT REFERENCES patients(id),
            code TEXT, description TEXT);
    """)
    con.executemany("INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?)",
                    [(p["Id"], p["BIRTHDATE"], p["DEATHDATE"] or None, p["FIRST"], p["LAST"],
                      p["GENDER"], p["RACE"], p["CITY"], p["STATE"]) for p in patients])
    con.executemany("INSERT INTO conditions VALUES (?,?,?,?,?)",
                    [(c["START"], c["STOP"] or None, c["PATIENT"], c["CODE"], c["DESCRIPTION"]) for c in conditions])
    con.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)",
                    [(o["DATE"], o["PATIENT"], o["CODE"], o["DESCRIPTION"], o["VALUE"], o["UNITS"]) for o in observations])
    con.executemany("INSERT INTO medications VALUES (?,?,?,?,?)",
                    [(m["START"], m["STOP"] or None, m["PATIENT"], m["CODE"], m["DESCRIPTION"]) for m in medications])
    con.commit()
    con.close()

    print(f"Wrote {DB_PATH}")
    for name, rows in tables.items():
        print(f"  {name:<13} {len(rows):>6} rows")


if __name__ == "__main__":
    main()
