import React from 'react';
import { useApp } from '../context/AppContext';
import { X, Cpu } from 'lucide-react';
import { caseLabel } from '../utils/caseLabel';

export const TokenWasteInspectorModal: React.FC = () => {
  const { isTokenInspectorOpen, setIsTokenInspectorOpen, cases, runUsage, setSelectedCaseId } =
    useApp();

  if (!isTokenInspectorOpen) return null;

  const totalReports = cases.reduce((acc, c) => acc + c.reports.length, 0);
  const caseTokens = cases.reduce((acc, c) => acc + c.tokenUsage.totalTokens, 0);
  const stepEntries = Object.entries(runUsage.byStep || {}).sort(
    (a, b) => (b[1]?.total_tokens || 0) - (a[1]?.total_tokens || 0)
  );

  const topCases = [...cases]
    .sort((a, b) => b.tokenUsage.totalTokens - a.tokenUsage.totalTokens)
    .slice(0, 8);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-3xl bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden my-auto max-h-[92vh] flex flex-col">
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-black shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-neutral-200 dark:bg-neutral-900 text-amber-600 dark:text-amber-400 border border-neutral-300 dark:border-neutral-800">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
                Engine token usage
              </h2>
              <p className="text-[11px] sm:text-xs text-neutral-500">
                From the last triage run · {totalReports} reports · {runUsage.calls} LLM calls
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsTokenInspectorOpen(false)}
            className="p-1.5 min-h-[36px] min-w-[36px] rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-4 sm:p-6 space-y-5 text-xs sm:text-sm">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <Metric label="Total tokens" value={runUsage.totalTokens.toLocaleString()} hint="run_totals" />
            <Metric label="Prompt" value={runUsage.promptTokens.toLocaleString()} hint="input" />
            <Metric
              label="Completion"
              value={runUsage.completionTokens.toLocaleString()}
              hint="output"
            />
            <Metric
              label="Est. cost"
              value={`$${runUsage.estimatedUsd.toFixed(4)}`}
              hint={`${runUsage.failedCalls} failed call(s)`}
            />
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-bold text-neutral-900 dark:text-white uppercase tracking-wider font-mono">
              By pipeline step
            </h3>
            <div className="space-y-1.5">
              {stepEntries.map(([step, stats]) => {
                const pct = runUsage.totalTokens
                  ? Math.round(((stats.total_tokens || 0) / runUsage.totalTokens) * 100)
                  : 0;
                return (
                  <div
                    key={step}
                    className="flex items-center gap-3 p-2.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-black"
                  >
                    <div className="w-28 font-mono font-semibold text-neutral-800 dark:text-neutral-200 truncate">
                      {step}
                    </div>
                    <div className="flex-1 h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden">
                      <div
                        className="h-full bg-neutral-800 dark:bg-neutral-200"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="w-24 text-right font-mono text-neutral-700 dark:text-neutral-300">
                      {(stats.total_tokens || 0).toLocaleString()}
                    </div>
                    <div className="w-16 text-right text-neutral-500">${(stats.estimated_usd || 0).toFixed(3)}</div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-bold text-neutral-900 dark:text-white uppercase tracking-wider font-mono">
              Highest token cases (allocated)
            </h3>
            <p className="text-[11px] text-neutral-500">
              Case-level sum ≈ {caseTokens.toLocaleString()} allocated tokens (shared solver cost
              split across sibling reports).
            </p>
            <div className="overflow-x-auto rounded-xl border border-neutral-200 dark:border-neutral-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-neutral-100 dark:bg-neutral-900 text-neutral-500 font-mono uppercase text-[10px]">
                  <tr>
                    <th className="px-3 py-2">Question</th>
                    <th className="px-3 py-2">Subject</th>
                    <th className="px-3 py-2 text-right">Tokens</th>
                    <th className="px-3 py-2">Route</th>
                  </tr>
                </thead>
                <tbody>
                  {topCases.map((c) => (
                    <tr
                      key={c.questionId}
                      className="border-t border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900 cursor-pointer"
                      onClick={() => {
                        setSelectedCaseId(c.questionId);
                        setIsTokenInspectorOpen(false);
                      }}
                    >
                      <td className="px-3 py-2 font-mono text-neutral-800 dark:text-neutral-200">
                        {caseLabel(c)}
                      </td>
                      <td className="px-3 py-2">{c.subject}</td>
                      <td className="px-3 py-2 text-right font-mono">{c.tokenUsage.totalTokens}</td>
                      <td className="px-3 py-2 font-mono">{c.aiRoute}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string; hint: string }> = ({ label, value, hint }) => (
  <div className="p-3 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-black">
    <span className="text-[10px] text-neutral-400 uppercase font-mono tracking-wider">{label}</span>
    <div className="text-lg sm:text-xl font-extrabold text-neutral-900 dark:text-white font-mono mt-0.5 tabular-nums">
      {value}
    </div>
    <span className="text-[10px] text-neutral-500">{hint}</span>
  </div>
);
