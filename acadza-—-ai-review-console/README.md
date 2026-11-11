# Acadza AI Review Console

Faculty review UI for the Report → Fix triage engine. Loads **precomputed** `results.json` + question/report snapshots (no live LLM calls required).

## Data

Real assignment data is bundled under `src/data/real/`:

| File | Source |
|---|---|
| `questions.json` | `../data/questions.json` |
| `reports.json` | `../data/reports.json` |
| `results.json` | `../output/results.json` |
| `cases.json` | `../output/cases.json` |
| `usage.json` | `../output/usage.json` |

`src/data/buildCases.ts` groups the 44 reports by question, joins HTML stems/solutions, AI verdicts/edits/replies, and token allocations.

After re-running the engine, refresh the snapshots:

```powershell
python -c "import shutil,os; b=r'..'; d=r'src/data/real';
for s,n in [('data/questions.json','questions.json'),('data/reports.json','reports.json'),('output/results.json','results.json'),('output/cases.json','cases.json'),('output/usage.json','usage.json')]:
 shutil.copy2(os.path.join(b,s), os.path.join(d,n)); print(n)"
```

(Run from this console folder.)

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000

## Notes

- Approve / edit / reject actions are stored in browser `localStorage` (audit trail for the demo).
- **Export** downloads a faculty-augmented `results.json`.
- Token panel shows the engine `usage.json` run totals (not a simulated waste score).
