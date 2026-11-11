import React from 'react';
import { useApp } from '../context/AppContext';
import { QuestionCase } from '../types';
import {
  MessageSquare,
  Wrench,
  ArrowRight,
  Filter,
  ArrowUpDown,
} from 'lucide-react';
import { caseLabel } from '../utils/caseLabel';

export const PriorityQueue: React.FC = () => {
  const {
    cases,
    activeSubjectFilter,
    activeRouteFilter,
    setActiveRouteFilter,
    searchQuery,
    sortBy,
    setSortBy,
    setSelectedCaseId,
  } = useApp();

  // 1. Filter by subject
  let filtered = cases.filter((c) => {
    if (activeSubjectFilter === 'All') return true;
    return c.subject === activeSubjectFilter;
  });

  // 2. Filter by route / status
  if (activeRouteFilter === 'needs_review') {
    filtered = filtered.filter((c) => c.aiRoute === 'faculty_review' && c.workflowStatus === 'pending');
  } else if (activeRouteFilter === 'auto_ready') {
    filtered = filtered.filter((c) => c.aiRoute === 'auto_apply' && c.workflowStatus === 'pending');
  } else if (activeRouteFilter === 'no_change') {
    filtered = filtered.filter((c) => c.aiRoute === 'no_change');
  } else if (activeRouteFilter === 'high_priority') {
    filtered = filtered.filter((c) => c.priority === 'high');
  } else if (activeRouteFilter === 'reviewed') {
    filtered = filtered.filter((c) => c.workflowStatus !== 'pending');
  }

  // 3. Filter by search query
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase().trim();
    filtered = filtered.filter((c) => {
      const matchId =
        c.questionId.toLowerCase().includes(q) ||
        (c.humanQid || '').toLowerCase().includes(q);
      const matchTitle = c.displayTitle.toLowerCase().includes(q);
      const matchChapter = c.chapter.toLowerCase().includes(q);
      const matchTopic = c.topic.toLowerCase().includes(q);
      const matchSummary = c.summaryLine.toLowerCase().includes(q);
      const matchReport = c.reports.some(
        (r) =>
          r.id.toLowerCase().includes(q) ||
          r.studentComment.toLowerCase().includes(q) ||
          (r.studentName && r.studentName.toLowerCase().includes(q))
      );
      return matchId || matchTitle || matchChapter || matchTopic || matchSummary || matchReport;
    });
  }

  // 4. Sort
  filtered.sort((a, b) => {
    if (sortBy === 'urgency') {
      const aScore = (a.workflowStatus === 'pending' && a.aiRoute === 'faculty_review' ? 100 : 0) +
        (a.priority === 'high' ? 50 : a.priority === 'medium' ? 20 : 0) +
        a.reports.length * 5;
      const bScore = (b.workflowStatus === 'pending' && b.aiRoute === 'faculty_review' ? 100 : 0) +
        (b.priority === 'high' ? 50 : b.priority === 'medium' ? 20 : 0) +
        b.reports.length * 5;
      return bScore - aScore;
    }
    if (sortBy === 'most_reported') {
      return b.reports.length - a.reports.length;
    }
    if (sortBy === 'confidence') {
      return b.aiConfidence - a.aiConfidence;
    }
    if (sortBy === 'newest') {
      return b.questionId.localeCompare(a.questionId);
    }
    if (sortBy === 'oldest') {
      return a.questionId.localeCompare(b.questionId);
    }
    return 0;
  });

  return (
    <div className="space-y-3.5 w-full max-w-full">
      {/* Header and Filter Controls */}
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white tracking-tight flex items-center gap-2">
          <span>Priority review queue</span>
          <span className="text-xs font-mono font-medium text-neutral-500">
            ({filtered.length})
          </span>
        </h2>

        {/* Sort selector */}
        <div className="flex items-center gap-1.5 shrink-0">
          <ArrowUpDown className="w-3.5 h-3.5 text-neutral-400" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="text-xs bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-lg px-2 py-1.5 text-neutral-900 dark:text-neutral-100 font-medium focus:outline-none"
          >
            <option value="urgency">Urgency</option>
            <option value="most_reported">Most reported</option>
            <option value="confidence">Confidence</option>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
          </select>
        </div>
      </div>

      {/* Monochrome Segmented Filter Bar */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar -mx-1 px-1">
        {[
          { id: 'all', label: 'All' },
          { id: 'needs_review', label: 'Needs Review' },
          { id: 'auto_ready', label: 'Auto-Ready' },
          { id: 'no_change', label: 'No Change' },
          { id: 'high_priority', label: 'High Priority' },
          { id: 'reviewed', label: 'Decided' },
        ].map((tab) => {
          const isActive = activeRouteFilter === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveRouteFilter(tab.id as any)}
              className={`px-3 py-1.5 font-semibold rounded-lg whitespace-nowrap transition-colors min-h-[36px] ${
                isActive
                  ? 'bg-neutral-900 text-white dark:bg-white dark:text-black shadow-sm'
                  : 'bg-neutral-100 dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Case List Grid */}
      {filtered.length === 0 ? (
        <div className="p-8 sm:p-12 text-center rounded-xl border border-dashed border-neutral-300 dark:border-neutral-800 bg-white dark:bg-neutral-950">
          <Filter className="w-7 h-7 mx-auto text-neutral-400 mb-2" />
          <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
            No matching questions in this queue
          </h3>
          <p className="text-xs text-neutral-500 mt-1 max-w-sm mx-auto">
            Try resetting your subject filter or clearing search keywords.
          </p>
        </div>
      ) : (
        <div className="space-y-3 w-full">
          {filtered.map((item) => (
            <CaseCard key={item.questionId} item={item} onSelect={() => setSelectedCaseId(item.questionId)} />
          ))}
        </div>
      )}
    </div>
  );
};

interface CaseCardProps {
  item: QuestionCase;
  onSelect: () => void;
}

const CaseCard: React.FC<CaseCardProps> = ({ item, onSelect }) => {
  // WCAG compliant, high-contrast badges for BOTH light and dark themes
  let statusBadge = {
    label: 'Needs faculty review',
    className: 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900/60',
  };

  if (item.workflowStatus === 'accepted') {
    statusBadge = {
      label: 'Accepted by Faculty',
      className: 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/60',
    };
  } else if (item.workflowStatus === 'rejected') {
    statusBadge = {
      label: 'Rejected by Faculty',
      className: 'bg-red-50 text-red-800 border-red-300 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/60',
    };
  } else if (item.workflowStatus === 'edited') {
    statusBadge = {
      label: 'Faculty Edited',
      className: 'bg-neutral-100 text-neutral-800 border-neutral-300 dark:bg-neutral-800 dark:text-neutral-200 dark:border-neutral-700',
    };
  } else if (item.aiRoute === 'auto_apply') {
    statusBadge = {
      label: 'Auto-ready safe patch',
      className: 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/60',
    };
  } else if (item.aiRoute === 'no_change') {
    statusBadge = {
      label: 'No content change (Verified)',
      className: 'bg-neutral-100 text-neutral-700 border-neutral-300 dark:bg-neutral-900 dark:text-neutral-400 dark:border-neutral-800',
    };
  }

  const repairLabel = item.repairType.replace(/_/g, ' ');
  const leadReportId = item.reports[0]?.id || 'R001';

  return (
    <div
      onClick={onSelect}
      className="group relative p-3.5 sm:p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 hover:border-neutral-400 dark:hover:border-neutral-700 transition-all cursor-pointer shadow-xs w-full overflow-hidden"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 w-full">
        <div className="space-y-1.5 flex-1 min-w-0">
          {/* Top Status Badge & ID */}
          <div className="flex items-center flex-wrap gap-2 text-xs">
            <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${statusBadge.className}`}>
              {statusBadge.label}
            </span>
            <span className="text-[11px] font-mono font-bold text-neutral-800 dark:text-neutral-200 px-1.5 py-0.5 rounded border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-900">
              {caseLabel(item)}
            </span>
          </div>

          {/* Title - high-contrast black/white */}
          <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white tracking-tight leading-snug">
            {item.displayTitle}
          </h3>

          {/* Subject • Chapter • Report ID */}
          <div className="text-xs text-neutral-600 dark:text-neutral-400 flex items-center flex-wrap gap-1.5">
            <span className="font-semibold text-neutral-900 dark:text-neutral-200">
              {item.subject}
            </span>
            <span>•</span>
            <span>{item.chapter}</span>
            <span>•</span>
            <span className="font-mono text-neutral-800 dark:text-neutral-300">
              Report {leadReportId}
            </span>
          </div>

          {/* Reports count & AI issue type */}
          <div className="flex items-center flex-wrap gap-3 text-xs text-neutral-600 dark:text-neutral-400 pt-0.5">
            <div className="flex items-center gap-1">
              <MessageSquare className="w-3.5 h-3.5 text-neutral-400" />
              <span>
                <strong className="font-mono text-neutral-900 dark:text-neutral-200">
                  {item.reports.length}
                </strong>{' '}
                {item.reports.length === 1 ? 'report' : 'reports'}
              </span>
            </div>

            <div className="flex items-center gap-1">
              <Wrench className="w-3.5 h-3.5 text-neutral-400" />
              <span className="capitalize">{repairLabel}</span>
            </div>
          </div>

          {/* Proposed Correction Highlight Strip - High Contrast in both Light and Dark */}
          {item.proposedSurgicalEdit && item.repairType !== 'none' && (
            <div className="flex items-center flex-wrap gap-1.5 pt-1 text-xs">
              <span className="text-neutral-600 dark:text-neutral-400 text-[11px] font-medium shrink-0">
                Proposed answer:
              </span>
              <div className="flex items-center flex-wrap gap-1.5 font-mono text-xs">
                {/* Red defect box */}
                <span className="px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-300 dark:bg-red-950/60 dark:text-red-400 dark:border-red-900/60 font-semibold max-w-[120px] sm:max-w-[180px] truncate">
                  {item.proposedSurgicalEdit.findValue}
                </span>
                <span className="text-neutral-400">→</span>
                {/* Green correction box */}
                <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-400 dark:border-emerald-900/60 font-semibold max-w-[120px] sm:max-w-[180px] truncate">
                  {item.proposedSurgicalEdit.replaceValue}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Action Button - 44px min-height for mobile tap */}
        <div className="shrink-0 pt-1 sm:pt-0 w-full sm:w-auto">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
            className="w-full sm:w-auto px-4 py-2.5 min-h-[44px] text-xs font-semibold text-neutral-900 dark:text-white bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 border border-neutral-300 dark:border-neutral-700/80 rounded-lg flex items-center justify-center gap-1.5 transition-colors"
          >
            <span>Review case</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
