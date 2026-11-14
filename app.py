"""
Patient Cohort Builder: the Streamlit dashboard.

Run from the cohort-builder folder (with your venv active):
    streamlit run app.py

Two ways to build a cohort:
  - Ask in plain English: a free LLM writes the SQL, guardrails check it, it runs read-only.
  - Filters: classic dropdowns, no AI (src/cohort.py). Handy when you have no API quota left.

The blank version you can write yourself is in exercises/practice/app.py.
"""

import html

import pandas as pd
import plotly.express as px
import streamlit as st

from src.cohort import CONDITIONS, MEDICATIONS, CohortFilters, build_sql
from src.db import enrich_patients, population_size, run_query
from src.llm import is_configured, model_name, provider
from src.nl_to_sql import ask

st.set_page_config(page_title="Cohort Builder", page_icon="🩺", layout="wide")

ACCENT = "#0F766E"
HBA1C_TARGET = 7.0

EXAMPLES = [
    "Diabetic women over 50 with an HbA1c above 8",
    "Men 65 or older with coronary heart disease",
    "Patients with kidney disease whose latest eGFR is below 45",
    "People with high blood pressure readings but no hypertension diagnosis",
]

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2rem; max-width: 1200px; }}
  .chip {{ display:inline-block; padding:4px 12px; margin:0 6px 6px 0; border-radius:999px;
          background: rgba(15,118,110,.10); color:{ACCENT}; border:1px solid rgba(15,118,110,.25);
          font-size: .85rem; }}
  .muted {{ color: rgba(128,128,128,.95); font-size: .9rem; }}
  div[data-testid="stMetricValue"] {{ font-size: 1.8rem; }}
</style>
""", unsafe_allow_html=True)


# ---------- cached helpers (save free-tier quota and keep the UI fast) ----------

def cached_ask(question: str):
    """Reuse answers to questions already asked this session (saves free-tier quota).
    Failed answers are not kept, so a retry after a rate limit really retries."""
    cache = st.session_state.setdefault("answers", {})
    key = question.strip().lower()
    if key in cache:
        return cache[key]
    result = ask(question)
    if result.ok or result.clarification:
        cache[key] = result
    return result


@st.cache_data(show_spinner=False)
def cached_population() -> int:
    return population_size()


@st.cache_data(show_spinner=False)
def cached_enrich(ids: tuple[str, ...]) -> pd.DataFrame:
    df = enrich_patients(list(ids))
    short = {"Body mass index 30+ - obesity": "Obesity", "Essential hypertension": "Hypertension",
             "Diabetes mellitus type 2": "Type 2 diabetes", "Chronic kidney disease stage 3": "CKD stage 3",
             "Major depressive disorder": "Depression"}
    df["conditions"] = (df["conditions"].fillna("").str.split(",")
                        .apply(lambda xs: ", ".join(short.get(x, x) for x in xs if x)))
    return df


@st.cache_data(show_spinner=False)
def cached_cities() -> list[str]:
    return run_query("SELECT DISTINCT city FROM patients ORDER BY city")["city"].tolist()


def chips(items: list[str]) -> None:
    if items:
        st.markdown("".join(f'<span class="chip">{html.escape(i)}</span>' for i in items),
                    unsafe_allow_html=True)


# ---------- dashboard for any cohort ----------

def show_cohort(ids: list[str], sql: str | None, label: str, attempts=None) -> None:
    total = cached_population()
    df = cached_enrich(tuple(ids))

    if df.empty:
        st.warning("No patients match. Try loosening one of the criteria, for example a lower threshold or a wider age range.")
        if sql:
            with st.expander("Show the SQL"):
                st.code(sql, language="sql")
        return

    # KPI tiles
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Patients", f"{len(df):,}")
    c2.metric("Of all patients", f"{len(df) / total:.1%}")
    c3.metric("Median age", f"{df['age'].median():.0f}")
    c4.metric("Women", f"{(df['gender'] == 'F').mean():.0%}")
    a1c = df["latest_hba1c"].dropna()
    c5.metric("Avg latest HbA1c", f"{a1c.mean():.1f}%" if len(a1c) else "–",
              help="Average of each patient's most recent HbA1c. Patients with no HbA1c are left out.")

    # Charts
    left, right = st.columns(2)
    with left:
        fig = px.histogram(df, x="age", nbins=15, color_discrete_sequence=[ACCENT])
        fig.update_layout(title="Age", bargap=0.08, height=300, margin=dict(l=10, r=10, t=40, b=10),
                          xaxis_title=None, yaxis_title="Patients")
        st.plotly_chart(fig, width="stretch")
    with right:
        if len(a1c):
            fig = px.histogram(a1c, nbins=15, color_discrete_sequence=[ACCENT])
            fig.add_vline(x=HBA1C_TARGET, line_dash="dash", line_color="#B45309",
                          annotation_text="7% target", annotation_position="top right")
            fig.update_layout(title="Latest HbA1c (%)", bargap=0.08, height=300, showlegend=False,
                              margin=dict(l=10, r=10, t=40, b=10), xaxis_title=None, yaxis_title="Patients")
            st.plotly_chart(fig, width="stretch")
        else:
            st.markdown('<p class="muted">No HbA1c results in this cohort.</p>', unsafe_allow_html=True)

    # Other conditions in the cohort
    conds = df["conditions"].str.split(", ").explode().replace("", pd.NA).dropna()
    if len(conds):
        top = (conds.value_counts() / len(df)).head(8).sort_values()
        fig = px.bar(x=top.values, y=top.index, orientation="h", color_discrete_sequence=[ACCENT])
        fig.update_layout(title="Active conditions in this cohort", height=320,
                          margin=dict(l=10, r=10, t=40, b=10), xaxis_title=None, yaxis_title=None,
                          xaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")

    # Patient table
    st.subheader("Patients")
    st.dataframe(
        df.drop(columns=["id"]),
        hide_index=True,
        width="stretch",
        column_config={
            "name": "Name", "gender": "Sex", "age": "Age", "race": "Race", "city": "City",
            "latest_hba1c": st.column_config.NumberColumn("Latest HbA1c (%)", format="%.1f"),
            "latest_bmi": st.column_config.NumberColumn("Latest BMI", format="%.1f"),
            "latest_sbp": st.column_config.NumberColumn("Latest systolic BP", format="%d"),
            "conditions": "Active conditions",
        },
    )
    st.download_button("Download cohort as CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"cohort_{label[:40].replace(' ', '_').lower() or 'export'}.csv",
                       mime="text/csv")

    if sql:
        with st.expander("Show the SQL"):
            st.code(sql, language="sql")
            if attempts and len(attempts) > 1:
                st.caption(f"The first {len(attempts) - 1} attempt(s) failed and were fixed automatically:")
                for a in attempts[:-1]:
                    st.code(a.sql, language="sql")
                    st.caption(f"Problem: {a.error}")


# ---------- sidebar ----------

with st.sidebar:
    st.markdown("### Cohort Builder")
    mode = st.radio("Build a cohort by", ["Asking in plain English", "Choosing filters"], index=0)
    st.divider()
    ok, why = is_configured()
    if ok:
        st.caption(f"AI model: {provider()} · {model_name()}")
    else:
        st.caption("AI model: not set up")
    st.caption(f"Data: {cached_population():,} synthetic patients. No real patient data. "
               "Ages are calculated on 1 Nov 2026.")
    if st.session_state.get("recent"):
        st.divider()
        st.caption("Recent questions")
        for q in st.session_state["recent"][-5:][::-1]:
            if st.button(q, key=f"recent_{q}", width="stretch"):
                st.session_state["pending"] = q


st.title("Find a patient cohort")

# ---------- mode 1: plain English ----------

if mode == "Asking in plain English":
    st.markdown('<p class="muted">Describe the patients you need. The query is checked and runs read-only.</p>',
                unsafe_allow_html=True)

    if not ok:
        st.error(why)
        st.stop()

    # A question chosen from an example, a recent question or a clarification.
    # It has to be copied into the text box BEFORE the box is drawn.
    if "pending" in st.session_state:
        st.session_state["question"] = st.session_state.pop("pending")
        st.session_state["run"] = True

    with st.form("ask", border=False):
        q_col, b_col = st.columns([6, 1])
        question = q_col.text_input("Question", key="question", label_visibility="collapsed",
                                    placeholder="e.g. Diabetic women over 50 with an HbA1c above 8")
        submitted = b_col.form_submit_button("Find", type="primary", width="stretch")

    def use_example(text: str) -> None:
        st.session_state["pending"] = text

    st.caption("Or try an example")
    ex_cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        ex_cols[i % 2].button(ex, on_click=use_example, args=(ex,), width="stretch")

    run_now = submitted or st.session_state.pop("run", False)
    question = st.session_state.get("question", "").strip()

    if run_now and question:
        with st.spinner("Writing and checking the query…"):
            result = cached_ask(question)
        st.session_state["last"] = result
        recent = st.session_state.setdefault("recent", [])
        if question not in recent:
            recent.append(question)

    result = st.session_state.get("last")

    if result is None:
        st.info("Try one of the examples above, or type your own question. "
                "You can mention sex, age, conditions (diabetes, hypertension, kidney disease…), "
                "lab results (HbA1c, BMI, blood pressure, LDL, eGFR), medications and city.")
    elif result.clarification:
        st.warning(f"**I need a bit more detail:** {result.clarification}")
        with st.form("clarify", border=False):
            answer = st.text_input("Your answer")
            if st.form_submit_button("Continue", type="primary") and answer.strip():
                st.session_state["pending"] = f"{result.question}. To clarify: {answer.strip()}"
                st.rerun()
    elif result.error:
        st.error(f"Something went wrong: {result.error}")
        st.caption("You can rephrase the question, or switch to **Choosing filters** in the sidebar.")
        if result.sql:
            with st.expander("Show the last SQL tried"):
                st.code(result.sql, language="sql")
    else:
        st.markdown(f"**{html.escape(result.explanation or result.question)}**")
        chips(result.assumptions)
        show_cohort(result.patient_ids, result.sql, result.question, result.attempts)

# ---------- mode 2: filters, no AI ----------

else:
    st.markdown('<p class="muted">No AI here: pick criteria and the app builds the SQL directly.</p>',
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    sex = c1.selectbox("Sex", ["Any", "Women", "Men"])
    ages = c2.slider("Age", 18, 90, (18, 90))
    city = c3.selectbox("City", ["Any"] + cached_cities())
    c4, c5 = st.columns(2)
    conds = c4.multiselect("Has all of these conditions", list(CONDITIONS))
    meds = c5.multiselect("Takes all of these medications", list(MEDICATIONS))
    c6, c7 = st.columns(2)
    use_a1c = c6.checkbox("Latest HbA1c above")
    a1c_val = c6.number_input("HbA1c %", 4.0, 14.0, 8.0, 0.1, disabled=not use_a1c, label_visibility="collapsed")
    use_bmi = c7.checkbox("Latest BMI at least")
    bmi_val = c7.number_input("BMI", 15.0, 60.0, 30.0, 0.5, disabled=not use_bmi, label_visibility="collapsed")

    f = CohortFilters(
        gender={"Women": "F", "Men": "M"}.get(sex),
        min_age=ages[0] if ages[0] > 18 else None,
        max_age=ages[1] if ages[1] < 90 else None,
        condition_codes=[CONDITIONS[c] for c in conds],
        medication_codes=[MEDICATIONS[m] for m in meds],
        hba1c_above=a1c_val if use_a1c else None,
        bmi_at_least=bmi_val if use_bmi else None,
        city=None if city == "Any" else city,
    )
    summary = [s for s in [
        sex if sex != "Any" else None,
        f"Age {ages[0]}–{ages[1]}" if ages != (18, 90) else None,
        *conds, *meds,
        f"Latest HbA1c > {a1c_val:g}%" if use_a1c else None,
        f"Latest BMI ≥ {bmi_val:g}" if use_bmi else None,
        city if city != "Any" else None,
    ] if s]
    chips(summary or ["All patients"])
    sql, params = build_sql(f)
    ids = run_query(sql, params)["id"].tolist()
    shown_sql = sql + "\n-- parameters: " + ", ".join(map(str, params)) if params else sql
    show_cohort(ids, shown_sql, "_".join(summary) or "all")
