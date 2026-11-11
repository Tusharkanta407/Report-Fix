# Product thinking

## 1. Who loses the most when a question is broken, and how your design reflects that

**The student loses the most.** Not the reporter. Not faculty. The next kid who attempts the same question, loses marks, and never knows the key was wrong. One bad answer can hit hundreds of attempts. That is the blast radius.

How the design reflects that:

- **Reflex, not FIFO.** Same `questionId` with more reports jumps the queue. On the faculty console, the most-reported question sits in its own coloured section so you see it first — then the rest by urgency. A NEET-tag typo from five minutes ago should not sit above a key that is already hurting many students.
- **Serious break → teacher gets hijacked.** Wrong key, broken question, solution fighting the key — software does not quietly rewrite. It goes `faculty_review` hard. Console treats it as: teacher eye *now*.
- **Tech mess → separate lane.** App crash, missing option in UI, markup junk — that is technical team, not an academic solve. Don’t burn solver money on it.
- **Report is a signal, not an order.** Student says “mu = 0.4.” Maybe wrong. We check stored solution / solve when needed. No blind flip.
- **Reply stays teacher voice.** Short. What we checked. What we kept or fixed. If students stop trusting the report button, real defects stop coming.

Levels so spend matches impact: **L0** spelling/chapter/app (never solve) · **L1** unit/form 0.08 vs 8 (stored solution only) · **L2** key/solution fight (one strong solve per question, cached). Most reports never touch the big model.

---

## 2. What you would never let the AI auto-apply, and why

I never auto-apply:

- Proper maths / “change the key to C” decisions  
- Diagram / figure issues  
- Unsound or broken question rewrites  
- Chapter / syllabus as a fake answer flip  
- Solver-alone flips when the stored solution already ends on the live key  

**Why:** one wrong auto write can cut marks for every student on that question. AI can suggest. Code guard + faculty own academic truth. Auto-apply stays for low-risk stuff only — safe text / form clarity we already validated (fraction ↔ full number when the value is the same). Unit-scale key flips (`8` ↔ `0.08`) stay human. Taxonomy auto-apply stays off.

---

## 3. One metric I’d watch in week 1

**Time-to-clear for multi-report defects.**

Clock from the *first* report on a `questionId` until either an approved fix goes live or an explicit `no_error` closes it.

That tells me if high-blast questions actually move faster than FIFO noise. I’d also glance at auto-apply rollback in 48 hours — if faculty undoes a lot, thresholds are too soft. If rollback is low but multi-report cases still drag, the bottleneck is the console / approval flow, not the model.

---

## 4. One idea beyond this brief I’d pitch

I’d pitch this: don’t pay the model again for a question you already solved.

Acadza has lakhs of questions. If five students report the same stem, I don’t want five full solves. Solve that question once, store it against the question, and when the next report comes on the same id, reuse that work — only decide what *this* student is asking and what reply they get. If someone edits the question later, then spend again. That’s it.

And show faculty the bill on the console — tokens used, tokens saved — so cost is not a black box. One second opinion max when the key fight is serious; still disagree → human. No ping-pong until the wallet is empty.
