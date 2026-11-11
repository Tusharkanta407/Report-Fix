# Bonus: defects nobody reported

43 questions in `data/questions.json`, 39 appear in `reports.json`.  
These **4 IDs have zero student reports** — scanned for silent defects.

| # | `_id` | Human `qid` | Verdict | Repair |
|---|-------|-------------|---------|--------|
| 1 | `68dea87d387eea3d0d95fbe3` | SecAQ4 | defect | `markup_leak` / display |
| 2 | `68dea657387eea3d0d95f54a` | SecAQ14 | defect | `notation` (solution) |
| 3 | `695ede2a88d7701e561aa9d9` | MHCET_PCB_PYQ_2021_1_BIO_L876 | defect | `stem_data` (likely) |
| 4 | `68dea6e6387eea3d0d95f6f8` | SecAQ11 | no clear defect | — |

Do **not** add these to scored `results.json` (that file is 1 row per report). Document for PRODUCT / bonus credit.

---

## 1. SecAQ4 — capacitor `K = αV` (`68dea87d…`)

- **Key A = 5 V is academically correct** (charge conservation → `V² + V − 30 = 0` → `V = 5`).
- **Unreported defect:** options `(B)(C)(D)` are wrapped in invalid MathML `<mspace linebreak="newline">…</mspace>` in the stored HTML. Native MathML renderers can drop or garble those options so students only reliably see (A).
- Also: `volt⁻¹` uses an empty `<mi></mi>` before the superscript — fragile markup.
- **Suggested repair:** unwrap B–D from `<mspace>`; keep answer `A`.

## 2. SecAQ14 lenses (`68dea657…`) — *unreported* optics integer

- **Key `5` (dioptre) is correct** (`f_eq = 10 cm` → `P_eq = 10 D` → each lens `5 D`).
- **Unreported defect:** solution text ends with corrupted subscripts **`P_eqcu`** / **`P_eqch`** instead of a clean “each lens” label → `notation` / light `solution_fix`.
- **Extra CMS smell:** human `qid` value `SecAQ14` is reused on **three different** `_id`s (optics unreported + Newton’s laws reported + work-energy reported). Metadata collision, not a student-facing stem bug.

## 3. Dialysis assertion (`695ede2a…`)

- Stem Statement-II: *“Sometimes dialysis is **not** a supportive measure in those for whom transplant is inappropriate.”*
- NCERT Class 11 (Excretory): dialysis is a holding measure **or a permanent/supportive measure** when transplant is not possible → Statement-II as stored is **false biology**.
- Stored key **D** (I correct, II incorrect) matches the stem **as written**.
- **Unreported defect (stem):** the `not` looks like a corrupted NCERT paraphrase. If Statement-II were restored to the NCERT sense (“**is** a supportive/permanent measure…”), **both** statements would be true → key should be **B**, not D.
- **Suggested faculty call:** confirm against original MHT CET paper; likely `stem_data` (`not` removal) + answer flip `D → B`, or leave key D if exam paper truly had this wording.

## 4. SecAQ11 displacement method (`68dea6e6…`)

- Given `D = 150 cm`, `f = 24 cm` → `x = 90 cm` → size ratio `((D+x)/(D−x))² = 16`.
- **Key `16` matches independent solve.** No solid content defect found; solution is a bit messy (starts from the `f` formula though `f` is given) but not wrong.

---

## Note on `68dea616d0cda73d07e93ae6` (SecBQ22)

This one **was** reported (`R005`). Human code is **`SecBQ22`**. Mongo `_id` is what reports/results use; the console now shows `SecBQ22` beside the `_id`.
