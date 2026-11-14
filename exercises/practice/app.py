"""
PHASE 4 - The Streamlit dashboard (end of Week 2)

Run with:  streamlit run app.py

This is where your WellStack experience shows. Sketch the screen on paper (or
in Figma) BEFORE writing code. Questions to answer in the sketch:
  - Where does the query box live, and what example queries help a first-time user?
  - How do you show what the AI understood? (filter chips from "assumptions")
  - Which 3-4 KPI tiles matter for a cohort? (size, % of population, avg age, avg HbA1c?)
  - Which 2 charts? (age distribution, HbA1c distribution, condition overlap?)
  - Where does the generated SQL go: hidden in an expander for power users?
  - Empty state, loading state, error state (the LLM will fail sometimes)
  - Export: download the cohort as CSV

TODO (in this order):
  1. st.set_page_config + title + a text_input for the question
  2. call question_to_sql, then is_safe, then run the SQL
  3. show the assumptions as chips, KPIs with st.metric, the table with st.dataframe
  4. charts (Plotly or Altair)
  5. st.download_button for CSV
  6. polish: example query buttons, empty/error states, a theme in .streamlit/config.toml
"""
