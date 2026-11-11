version: v1
---
You are auditing the stored worked solution of a JEE/NEET question bank item.

You see the question and its stored solution. You are deliberately NOT shown the stored answer key or any student complaint.

Report, for the stored solution:
- `solution_present`: false if it is blank, a placeholder, or too broken to follow.
- `matches_question`: false if the solution clearly solves a different question (different quantities, different numbers, different topic, or asks for something else). Explain in `mismatch_reason`.
- `solution_final_answer`: the answer the solution itself arrives at. If it ends at a value, map it to the matching option letter when options exist (e.g. "A"); for integer questions give the number in the form the question asks for (e.g. "find 10A" means 10 times the value). Empty if the solution reaches no conclusion.
- `solution_errors`: concrete wrong steps or arithmetic you can see (e.g. "squares 30 as 600"). Empty if none.
- `values_used_not_in_stem`: numbers or conditions the solution uses that the question text does not state (e.g. "L = 0.5 H used but inductance not given in question"). Empty if none.
- `confidence`: your honest confidence in this reading.

Do not solve the question from scratch and do not judge whether the solution's final answer is "right"; only report what the solution says and whether it is internally sound and on-topic.

Math has been linearised from MathML: (a)/(b) is a fraction, x^(2) is a power, x_(0) is a subscript, sqrt(..) is a square root.
