"""
PHASE 3 - Measure how often the LLM gets it right (Week 2)

golden_questions.csv has 13 questions with the correct patient count.
This script is how you prove (on your resume) that your app works:
"Answers 12/13 benchmark questions correctly".

TODO:
  - read golden_questions.csv with pandas
  - for each question: question_to_sql -> is_safe -> run it -> count rows
  - compare to expected_count, print a table and an overall score
  - keep the free-tier rate limit in mind: add time.sleep between calls
  - save results to eval/results_<date>.csv so you can compare prompt versions
"""
