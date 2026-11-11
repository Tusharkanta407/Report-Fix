import React from 'react';
import { useApp } from '../context/AppContext';
import { Copy, Check, Users, Shield } from 'lucide-react';

export const SummaryCards: React.FC = () => {
  const { cases, setActiveRouteFilter, activeRouteFilter } = useApp();

  // Compute exact metrics from dataset
  const totalReports = cases.reduce((acc, c) => acc + c.reports.length, 0);
  const autoReadyCount = cases.filter((c) => c.aiRoute === 'auto_apply').length;
  const facultyReviewCount = cases.filter((c) => c.aiRoute === 'faculty_review').length;
  const noChangeCount = cases.filter((c) => c.aiRoute === 'no_change').length;

  const totalQuestions = cases.length;
  const pendingCases = cases.filter((c) => c.workflowStatus === 'pending').length;
  const reviewedCases = cases.filter(
    (c) => c.workflowStatus === 'accepted' || c.workflowStatus === 'rejected' || c.workflowStatus === 'edited'
  ).length;

  return (
    <div className="space-y-3 w-full">
      {/* 4 Primary Metric Columns matching image_67727156.png */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4 w-full">
        {/* Metric 1: Total Reports */}
        <button
          onClick={() => setActiveRouteFilter('all')}
          className={`flex flex-col text-left p-3.5 sm:p-4 rounded-xl border transition-all ${
            activeRouteFilter === 'all'
              ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-900 dark:border-white ring-1 ring-neutral-900 dark:ring-white shadow-xs'
              : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700'
          }`}
        >
          <div className="flex items-center justify-between text-neutral-400 mb-1.5">
            <Copy className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
            <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">Total</span>
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-neutral-900 dark:text-white tabular-nums tracking-tight">
            {totalReports}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5 font-medium">
            Total reports
          </div>
        </button>

        {/* Metric 2: Auto-ready */}
        <button
          onClick={() => setActiveRouteFilter('auto_ready')}
          className={`flex flex-col text-left p-3.5 sm:p-4 rounded-xl border transition-all ${
            activeRouteFilter === 'auto_ready'
              ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-900 dark:border-white ring-1 ring-neutral-900 dark:ring-white shadow-xs'
              : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700'
          }`}
        >
          <div className="flex items-center justify-between text-neutral-400 mb-1.5">
            <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              Auto
            </span>
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-neutral-900 dark:text-white tabular-nums tracking-tight">
            {autoReadyCount}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5 font-medium">
            Auto-ready
          </div>
        </button>

        {/* Metric 3: Faculty review */}
        <button
          onClick={() => setActiveRouteFilter('needs_review')}
          className={`flex flex-col text-left p-3.5 sm:p-4 rounded-xl border transition-all ${
            activeRouteFilter === 'needs_review'
              ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-900 dark:border-white ring-1 ring-neutral-900 dark:ring-white shadow-xs'
              : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700'
          }`}
        >
          <div className="flex items-center justify-between text-neutral-400 mb-1.5">
            <Users className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
              Review
            </span>
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-neutral-900 dark:text-white tabular-nums tracking-tight">
            {facultyReviewCount}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5 font-medium">
            Faculty review
          </div>
        </button>

        {/* Metric 4: No change */}
        <button
          onClick={() => setActiveRouteFilter('no_change')}
          className={`flex flex-col text-left p-3.5 sm:p-4 rounded-xl border transition-all ${
            activeRouteFilter === 'no_change'
              ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-900 dark:border-white ring-1 ring-neutral-900 dark:ring-white shadow-xs'
              : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-700'
          }`}
        >
          <div className="flex items-center justify-between text-neutral-400 mb-1.5">
            <Shield className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
              Verified
            </span>
          </div>
          <div className="text-2xl sm:text-3xl font-extrabold text-neutral-900 dark:text-white tabular-nums tracking-tight">
            {noChangeCount}
          </div>
          <div className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5 font-medium">
            No change
          </div>
        </button>
      </div>

      {/* Secondary Meta Note */}
      <div className="flex flex-wrap items-center justify-between text-xs text-neutral-600 dark:text-neutral-400 px-1 gap-2 font-medium">
        <div className="flex items-center gap-2">
          <span>{totalQuestions} unique questions reported</span>
          <span>·</span>
          <span>{pendingCases} awaiting faculty review</span>
          <span>·</span>
          <span>{reviewedCases} decided</span>
        </div>
        <div className="text-neutral-500 italic text-[11px]">
          Calculated dynamically from imported results.
        </div>
      </div>
    </div>
  );
};
