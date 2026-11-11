## Who loses the most when a question is broken?

The next student, not the person who reported it.

Think about a question where the correct answer is 50 V, but the answer key says 130 V. One mistake can silently affect hundreds of students who have already attempted that question. The person who reported it has already faced the problem, but the students who never report it continue losing marks without even knowing why.

That's the problem I want to solve.

My approach is to make sure we prioritise the impact on students, not just the order in which reports arrive.

### How I am thinking about the design

**1. Prioritise based on impact, not FIFO.**

If multiple students report the same questionId, that should increase its priority. A question affecting 100 students should not sit below a spelling mistake reported five minutes earlier. I want the queue to consider both urgency and blast radius.

**2. A student report is a signal, not the final decision.**

For example, a student might report that the answer should be option B instead of D because they got 4√2 while solving it. That doesn't automatically mean the answer key is wrong.

Before changing anything, I want the system to independently solve the question, read the existing solution and compare the results. If the evidence doesn't agree, it should go to faculty instead of blindly changing the answer.

**3. Fix what can be fixed immediately.**

Not every issue needs a long AI analysis. If the problem is a spelling mistake, exam tag or unnecessary text, we should be able to fix it quickly.

The goal is not to make every case complicated. The goal is to resolve simple issues today and spend human attention where it actually matters.

**4. Keep communication simple and respectful.**

When a student reports an issue, the reply should be short, clear and helpful. We should explain what was checked and what was corrected without making the student feel wrong for reporting something.

If students stop trusting the reporting system, they will stop reporting genuine problems too.

For me, the priority is simple: faculty time matters, institute reputation matters, but the biggest loss happens when students lose marks because of a mistake we could have caught.

---

### What I would never allow AI to change automatically

I don't want AI to have unrestricted control over academic content. Some changes are too risky to automate, especially when a wrong decision can affect thousands of attempts.

Here is how I would handle them:

| Issue | My decision |
|---|---|
| identical_options | Faculty review |
| Diagram-related issues | Faculty review |
| Wrong question / unsound question | Faculty review |
| Wrong chapter / syllabus | Faculty review |
| Answer key | Only when independent solve and existing solution agree on the proposed new key |
| Unit-scale changes (8 ↔ 0.08) | Never auto-apply |
| Solve and solution disagree | Escalate to faculty |
| Raw HTML / scope / surgical validation failure | Block the write |

One important thing: even if the AI independently solves a question and gets a different answer, that alone is not enough to change the answer key.

The existing solution might already support the stored answer, which means the student's report could be incorrect. We need stronger evidence before making a change that affects everyone.

I would keep taxonomy auto-application disabled. AI can suggest a classification, but decisions about diagrams, syllabus and academic correctness should remain with humans.

My rule is that AI can handle low-risk corrections, but changes to academic truth need evidence and, where necessary, human approval.

---

### What I want to measure in Week 1

I don't want to measure success by how many reports the AI processes. That number doesn't tell us whether students are actually benefiting.

My primary metric would be:

**Time-to-clear for multi-report defects.**

Measure the time between the first report against a questionId and either:
- An approved correction going live.
- An explicit `no_error` decision closing the issue.

This will tell us whether we are actually resolving high-impact problems faster.

I would also monitor the auto-apply rollback rate over 48 hours.

If faculty frequently undo AI corrections, our confidence thresholds are probably too low.

If rollback remains low but multi-report defects are still taking too long to resolve, then the problem might not be the model. It could be the faculty queue experience or the approval workflow.

I want the metrics to help us identify the actual bottleneck instead of automatically blaming AI.

---

### One additional idea: Solve Once, Decide Many

I was also thinking about how we can make this system economical as Acadza scales.

With around 8 lakh questions, repeatedly running a full AI solving pipeline for reports against the same question doesn't make much sense.

We can introduce a content-fingerprint-based cache.

**How it would work:**

1. Generate a fingerprint using the question stem, options, answer key and solution.
2. When the same question comes up again with another report, check whether its fingerprint already exists.
3. If it does, reuse the previous independent solve and solution analysis.
4. Run only the lightweight report interpreter and comparison logic for the new report.
5. If the question content changes, generate a new fingerprint and run the required analysis again.

This way, we solve the academic problem once but can evaluate multiple student reports against the same evidence.

**I would also introduce three taxonomy spend tiers (see `engine/routing.py`):**

- **L0 — never solve:** Spelling, chapter, NEET tag, markup, app, syllabus. Rules + mini intent only; template reply. Example: “filed under wrong chapter” → refile note, key untouched.
- **L1 — explain from stored solution:** Unit/form / 0.08 vs 8 / sig-fig confusion. Read the bank’s solution + stem; short student reply. No gpt-4o re-solve. Example: “answer is 0.08 cm” when stem asks cm and key is already 8 → clarify conversion, keep key.
- **L2 — solve once:** Answer key or solution-step dispute. Strong model solves that question once (cached); each sibling report only decides.

These tiers keep tokens low: most of ~44 reports never touch the solver.

**Faculty console: Token ledger**

I would also like to show token consumption directly in the faculty dashboard.

For every case, we can display:
- Tokens consumed.
- Tokens saved through cache hits.
- Tokens saved through fast-path processing.
- Whether a second-opinion model call was required.

For high-risk answer-key conflicts, we can allow at most one additional independent model opinion. If the disagreement still exists, send it to faculty. No endless model calls trying to force an agreement.

The idea is to make AI cost visible and measurable instead of treating it as an invisible backend expense.

---

### My overall thinking

I don't want to build a system that simply reads student complaints and changes questions using an LLM.

I want to build a system that understands the impact of a reported defect, checks the evidence, makes safe corrections where possible and knows when to stop and ask a human.

The core approach remains the same:

**Solve once per question. Decide separately for every report. Never bypass the validation layer when writing changes.**

And as the platform scales, make sure the cost of keeping those questions correct doesn't scale unnecessarily with it.

At the end of the day, the objective isn't to maximise AI automation. It's to make sure that the next student doesn't lose marks because nobody caught a mistake in time.
