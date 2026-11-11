import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { StudentReport } from '../types';
import {
  ArrowLeft,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  Edit3,
  History,
  ChevronDown,
  Cpu,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import { caseLabel } from '../utils/caseLabel';

export const CaseReviewWorkspace: React.FC = () => {
  const {
    selectedCase,
    setSelectedCaseId,
    cases,
    setIsAcceptModalOpen,
    setIsRejectModalOpen,
    setIsEditModalOpen,
    setIsAuditDrawerOpen,
    setIsTokenInspectorOpen,
    updateStudentReplyDraft,
    toggleStudentReplyReady,
    showToast,
  } = useApp();

  const [activeReportIndex, setActiveReportIndex] = useState(0);
  const [isReasoningExpanded, setIsReasoningExpanded] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [copiedReply, setCopiedReply] = useState(false);
  const [mobileTab, setMobileTab] = useState<'overview' | 'question' | 'student'>('overview');

  if (!selectedCase) {
    return null;
  }

  const reports = selectedCase.reports || [];
  const activeReport: StudentReport | undefined = reports[activeReportIndex] || reports[0];

  const currentIndex = cases.findIndex((c) => c.questionId === selectedCase.questionId);
  const prevCase = currentIndex > 0 ? cases[currentIndex - 1] : null;
  const nextCase = currentIndex < cases.length - 1 ? cases[currentIndex + 1] : null;

  const label = caseLabel(selectedCase);

  const handleCopyId = () => {
    navigator.clipboard.writeText(label);
    setCopiedId(true);
    showToast(`Copied: ${label}`);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleCopyStudentReply = () => {
    if (!activeReport) return;
    const textToCopy = activeReport.studentReplyDraft || activeReport.studentReply;
    navigator.clipboard.writeText(textToCopy);
    setCopiedReply(true);
    showToast(`Student reply copied to clipboard!`);
    setTimeout(() => setCopiedReply(false), 2200);
  };

  const isAccepted = selectedCase.workflowStatus === 'accepted';
  const isRejected = selectedCase.workflowStatus === 'rejected';
  const isEdited = selectedCase.workflowStatus === 'edited';

  return (
    <div className="space-y-4 sm:space-y-6 pb-28 w-full max-w-full">
      {/* 1. TOP BAR */}
      <div className="bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl p-3 sm:p-4 shadow-xs space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          {/* Back button & Question ID */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedCaseId(null)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 min-h-[40px] text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 border border-neutral-300 dark:border-neutral-800 rounded-lg transition-colors"
              title="Return to queue (Esc)"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Back</span>
            </button>

            <div className="flex items-center gap-1.5 min-w-0">
              <span className="font-mono text-xs sm:text-sm font-extrabold text-neutral-900 dark:text-white shrink-0">
                {label}
              </span>
              <button
                onClick={handleCopyId}
                className="p-1.5 min-h-[36px] min-w-[36px] flex items-center justify-center text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 rounded shrink-0"
                title="Copy code"
              >
                {copiedId ? (
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </div>

          {/* Quick Prev / Next Case Navigation */}
          <div className="flex items-center gap-1.5 text-xs">
            {prevCase && (
              <button
                onClick={() => {
                  setSelectedCaseId(prevCase.questionId);
                  setActiveReportIndex(0);
                }}
                className="px-2 py-1 min-h-[36px] rounded bg-neutral-100 dark:bg-neutral-900 text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-neutral-800 font-medium hover:bg-neutral-200 dark:hover:bg-neutral-800"
              >
                ← Prev
              </button>
            )}
            <span className="text-neutral-500 dark:text-neutral-400 font-mono text-[11px] px-1 hidden sm:inline">
              {currentIndex + 1} / {cases.length}
            </span>
            {nextCase && (
              <button
                onClick={() => {
                  setSelectedCaseId(nextCase.questionId);
                  setActiveReportIndex(0);
                }}
                className="px-2 py-1 min-h-[36px] rounded bg-neutral-100 dark:bg-neutral-900 text-neutral-800 dark:text-neutral-200 border border-neutral-300 dark:border-neutral-800 font-medium hover:bg-neutral-200 dark:hover:bg-neutral-800"
              >
                Next →
              </button>
            )}
          </div>
        </div>

        {/* Case Metadata */}
        <div className="flex flex-wrap items-center justify-between gap-y-1.5 pt-2 border-t border-neutral-100 dark:border-neutral-800/80 text-xs">
          <div className="flex items-center flex-wrap gap-1.5 text-neutral-600 dark:text-neutral-400">
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              {selectedCase.subject}
            </span>
            <span>•</span>
            <span>{selectedCase.chapter}</span>
            <span className="hidden sm:inline">•</span>
            <span className="hidden sm:inline text-neutral-500 dark:text-neutral-400 italic">{selectedCase.topic}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[10px] sm:text-[11px] font-mono px-2 py-0.5 rounded border border-neutral-300 dark:border-neutral-800 text-neutral-700 dark:text-neutral-300 font-medium">
              {selectedCase.exam}
            </span>
            <span
              className={`text-[10px] sm:text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${
                isAccepted
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-900/60'
                  : isRejected
                  ? 'bg-red-50 text-red-800 border-red-300 dark:bg-red-950/40 dark:text-red-400 dark:border-red-900/60'
                  : isEdited
                  ? 'bg-neutral-100 text-neutral-800 border-neutral-300 dark:bg-neutral-800 dark:text-neutral-200 dark:border-neutral-700'
                  : 'bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900/60'
              }`}
            >
              {selectedCase.workflowStatus.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {/* MOBILE SEGMENTED TABS (Visible on Phone, Hidden on Desktop) */}
      <div className="flex lg:hidden items-center p-1 rounded-xl bg-neutral-200 dark:bg-neutral-900 text-xs font-semibold gap-1">
        <button
          onClick={() => setMobileTab('overview')}
          className={`flex-1 py-2 text-center rounded-lg min-h-[40px] transition-all ${
            mobileTab === 'overview'
              ? 'bg-neutral-900 text-white dark:bg-white dark:text-black shadow-xs font-bold'
              : 'text-neutral-700 dark:text-neutral-400'
          }`}
        >
          Fix & Evidence
        </button>
        <button
          onClick={() => setMobileTab('question')}
          className={`flex-1 py-2 text-center rounded-lg min-h-[40px] transition-all ${
            mobileTab === 'question'
              ? 'bg-neutral-900 text-white dark:bg-white dark:text-black shadow-xs font-bold'
              : 'text-neutral-700 dark:text-neutral-400'
          }`}
        >
          Original Question
        </button>
        <button
          onClick={() => setMobileTab('student')}
          className={`flex-1 py-2 text-center rounded-lg min-h-[40px] transition-all ${
            mobileTab === 'student'
              ? 'bg-neutral-900 text-white dark:bg-white dark:text-black shadow-xs font-bold'
              : 'text-neutral-700 dark:text-neutral-400'
          }`}
        >
          Reports ({reports.length})
        </button>
      </div>

      {/* 2. DUAL COLUMN WORKSPACE */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 items-start">
        {/* ================= COLUMN 1: ORIGINAL / BEFORE ================= */}
        <div className={`space-y-4 ${mobileTab !== 'question' ? 'hidden lg:block' : 'block'}`}>
          <div className="bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl p-4 sm:p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <h2 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
                Original Question (Before)
              </h2>
              <span className="text-xs font-mono text-neutral-500">Stored in DB</span>
            </div>

            {/* Question Text with MathML */}
            <div className="text-xs sm:text-sm leading-relaxed text-neutral-900 dark:text-neutral-100 font-sans space-y-2 overflow-x-auto">
              <div
                dangerouslySetInnerHTML={{ __html: selectedCase.questionHtml }}
                className="[&>p]:mb-2 [&_math]:font-mono [&_math]:text-neutral-950 dark:[&_math]:text-white font-medium"
              />
            </div>

            {/* Diagram (if available) */}
            {selectedCase.diagramSvg && (
              <div className="my-2 p-2 sm:p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-black flex flex-col items-center">
                <div
                  dangerouslySetInnerHTML={{ __html: selectedCase.diagramSvg }}
                  className="w-full flex justify-center max-w-sm"
                />
                {selectedCase.diagramCaption && (
                  <p className="text-[11px] text-neutral-600 dark:text-neutral-400 text-center mt-1.5 italic">
                    {selectedCase.diagramCaption}
                  </p>
                )}
              </div>
            )}

            {/* MCQ Options */}
            {selectedCase.options && selectedCase.options.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-neutral-100 dark:border-neutral-800">
                <div className="text-xs font-bold text-neutral-800 dark:text-neutral-300">
                  Multiple Choice Options:
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {selectedCase.options.map((opt) => (
                    <div
                      key={opt.label}
                      className={`p-2.5 rounded-lg border text-xs flex items-center justify-between ${
                        opt.isOriginalCorrect
                          ? 'bg-amber-50 text-amber-950 border-amber-300 dark:bg-amber-950/20 dark:text-amber-300 dark:border-amber-900/40 font-semibold'
                          : 'bg-white text-neutral-900 border-neutral-200 dark:bg-neutral-900/60 dark:text-neutral-300 dark:border-neutral-800'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-full bg-neutral-200 dark:bg-neutral-800 text-[11px] font-mono font-bold flex items-center justify-center text-neutral-900 dark:text-neutral-100">
                          {opt.label}
                        </span>
                        <span dangerouslySetInnerHTML={{ __html: opt.textHtml }} />
                      </div>
                      {opt.isOriginalCorrect && (
                        <span className="text-[10px] font-bold text-amber-800 dark:text-amber-400 uppercase font-mono">
                          Stored Key
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Original Stored Answer Key */}
            <div className="pt-2 border-t border-neutral-100 dark:border-neutral-800 flex items-center gap-2">
              <span className="text-xs font-bold text-neutral-800 dark:text-neutral-300">
                Stored Answer Key:
              </span>
              <span className="px-2.5 py-1 rounded bg-neutral-100 dark:bg-neutral-900 text-neutral-950 dark:text-white font-mono text-sm font-extrabold border border-neutral-300 dark:border-neutral-800">
                {selectedCase.storedAnswer}
              </span>
            </div>

            {/* Original Stored Solution with Defective text highlighted in soft red */}
            <div className="space-y-1.5 pt-2 border-t border-neutral-100 dark:border-neutral-800">
              <div className="text-xs font-bold text-neutral-800 dark:text-neutral-300">
                Stored Solution Explanation:
              </div>
              <div
                dangerouslySetInnerHTML={{ __html: selectedCase.storedSolutionHtml }}
                className="text-xs leading-relaxed text-neutral-900 dark:text-neutral-200 bg-neutral-50 dark:bg-black p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 font-sans"
              />
            </div>

            {/* Finding callout */}
            <div
              className={`p-3 rounded-lg border space-y-1 ${
                selectedCase.aiVerdict === 'defect'
                  ? 'border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-950/20'
                  : 'border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/40'
              }`}
            >
              <div
                className={`text-xs font-bold flex items-center gap-1.5 ${
                  selectedCase.aiVerdict === 'defect'
                    ? 'text-red-800 dark:text-red-400'
                    : 'text-neutral-800 dark:text-neutral-300'
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>
                  {selectedCase.aiVerdict === 'defect' ? 'What went wrong?' : 'AI assessment'}
                </span>
              </div>
              <p
                className={`text-xs leading-relaxed font-medium ${
                  selectedCase.aiVerdict === 'defect'
                    ? 'text-red-950 dark:text-neutral-200'
                    : 'text-neutral-800 dark:text-neutral-200'
                }`}
              >
                {selectedCase.issueExplanation}
              </p>
            </div>
          </div>
        </div>

        {/* ================= COLUMN 2: AI PROPOSED / AFTER ================= */}
        <div className={`space-y-4 ${mobileTab !== 'overview' ? 'hidden lg:block' : 'block'}`}>
          {/* AI Case Brief (High Contrast in both Light and Dark) */}
          <div className="bg-neutral-900 text-white dark:bg-black border border-neutral-800 rounded-xl p-4 sm:p-5 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-800">
              <div className="text-sm sm:text-base font-bold text-white tracking-tight">
                AI Case Brief
              </div>
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-950/60 text-amber-400 border border-amber-800">
                {selectedCase.workflowStatus === 'pending' ? 'Verification required' : selectedCase.workflowStatus.toUpperCase()}
              </span>
            </div>

            {/* STUDENT REPORTED */}
            <div className="space-y-1">
              <div className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-neutral-400 font-semibold">
                Student Reported
              </div>
              <p className="text-xs sm:text-sm text-neutral-100 italic font-sans leading-relaxed">
                "{activeReport ? activeReport.studentComment : selectedCase.reports[0]?.studentComment}"
              </p>
            </div>

            {/* AI FINDING */}
            <div className="space-y-1 pt-2 border-t border-neutral-800">
              <div className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-neutral-400 font-semibold">
                AI Finding
              </div>
              <p className="text-xs sm:text-sm text-neutral-100 font-sans leading-relaxed">
                {selectedCase.summaryLine}
              </p>
            </div>

            {/* PROPOSED CORRECTION */}
            <div className="space-y-2 pt-2 border-t border-neutral-800">
              <div className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-neutral-400 font-semibold">
                Proposed Correction
              </div>
              {selectedCase.proposedSurgicalEdit.targetField === 'none' ||
              (selectedCase.proposedSurgicalEdit.findValue === '—' &&
                selectedCase.proposedSurgicalEdit.replaceValue === '—') ? (
                <p className="text-xs text-neutral-300">No content edit proposed ({selectedCase.aiRoute}).</p>
              ) : (
                <div className="flex items-center gap-2.5">
                  <span className="px-3 py-1 rounded bg-red-950 text-red-300 font-mono text-sm font-bold border border-red-800 max-w-[45%] truncate">
                    {selectedCase.proposedSurgicalEdit.findValue}
                  </span>
                  <span className="text-neutral-400 font-bold">→</span>
                  <span className="px-3 py-1 rounded bg-emerald-950 text-emerald-300 font-mono text-sm font-bold border border-emerald-800 max-w-[45%] truncate">
                    {selectedCase.proposedSurgicalEdit.replaceValue}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* SURGICAL DIFF & EVIDENCE PANEL */}
          <div className="bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl p-4 sm:p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
              <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-1.5">
                <span>Academic Verification</span>
              </h3>
              <span className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-400">
                Confidence: {selectedCase.aiConfidence}%
              </span>
            </div>

            {/* Surgical diff specs */}
            <div className="grid grid-cols-2 gap-2 text-xs bg-neutral-50 dark:bg-black p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 font-mono">
              <div>
                <span className="text-neutral-500 text-[10px] uppercase font-bold">Target Field:</span>
                <div className="text-neutral-900 dark:text-neutral-100 font-semibold truncate">
                  {selectedCase.proposedSurgicalEdit.targetField}
                </div>
              </div>
              <div>
                <span className="text-neutral-500 text-[10px] uppercase font-bold">Taxonomy:</span>
                <div className="text-neutral-900 dark:text-neutral-100 font-semibold truncate">
                  {selectedCase.proposedSurgicalEdit.taxonomyLabel}
                </div>
              </div>
            </div>

            {/* Verification — academic solve OR deterministic check */}
            <div className="space-y-1">
              <div className="text-xs font-bold text-neutral-900 dark:text-neutral-200">
                {[
                  'spelling',
                  'noise',
                  'exam_reference',
                  'markup_leak',
                  'answer_form',
                  'notation',
                ].includes(selectedCase.repairType) ||
                ['app_issue', 'display_issue', 'language_mode', 'already_fixed', 'not_actionable'].includes(
                  selectedCase.aiVerdict
                )
                  ? 'Deterministic check:'
                  : 'Independent academic proof:'}
              </div>
              <div className="p-3 rounded-lg bg-neutral-50 dark:bg-black border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-200 font-mono leading-relaxed whitespace-pre-wrap">
                {selectedCase.independentAcademicVerification}
              </div>
            </div>

            {/* Evidence checklist */}
            <div className="space-y-1.5 pt-2 border-t border-neutral-100 dark:border-neutral-800 text-xs text-neutral-800 dark:text-neutral-300">
              <div className="font-bold text-neutral-900 dark:text-neutral-200">
                Corroborating Evidence:
              </div>
              {selectedCase.verificationEvidence.map((ev, i) => (
                <div key={i} className="flex items-start gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
                  <span className="text-neutral-800 dark:text-neutral-200 font-medium">{ev}</span>
                </div>
              ))}
            </div>

            {/* Expandable detailed reasoning */}
            <div className="pt-2 border-t border-neutral-100 dark:border-neutral-800">
              <button
                onClick={() => setIsReasoningExpanded(!isReasoningExpanded)}
                className="w-full flex items-center justify-between text-xs text-neutral-800 dark:text-neutral-300 hover:text-black dark:hover:text-white py-1 font-bold"
              >
                <span>{isReasoningExpanded ? 'Hide detailed AI derivation' : 'Show detailed AI reasoning & derivation'}</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform ${isReasoningExpanded ? 'rotate-180' : ''}`}
                />
              </button>
              {isReasoningExpanded && (
                <div className="mt-2 p-3 rounded-lg bg-neutral-50 dark:bg-black border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-200 leading-relaxed font-sans">
                  {selectedCase.detailedReasoning}
                </div>
              )}
            </div>

            {/* Inline Token Usage for this Question */}
            <div className="p-3 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <Cpu className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span className="font-mono text-neutral-900 dark:text-neutral-300 font-medium">
                  {selectedCase.tokenUsage.totalTokens} tokens allocated
                </span>
              </div>
              <button
                onClick={() => setIsTokenInspectorOpen(true)}
                className="text-[11px] font-bold text-neutral-900 dark:text-neutral-200 hover:underline"
              >
                View run usage →
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 3. SIBLING STUDENT REPORTS & STUDENT REPLY PREVIEW */}
      <div className={`space-y-4 ${mobileTab !== 'student' ? 'hidden lg:block' : 'block'}`}>
        <div className="bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl p-4 sm:p-5 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-100 dark:border-neutral-800 pb-3">
            <div>
              <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <span>Student Reports ({reports.length})</span>
              </h3>
              <p className="text-xs text-neutral-500">
                Student complaints for {label}.
              </p>
            </div>

            {/* Sibling Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto">
              {reports.map((rep, idx) => (
                <button
                  key={rep.id}
                  onClick={() => setActiveReportIndex(idx)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg whitespace-nowrap min-h-[36px] transition-colors ${
                    activeReportIndex === idx
                      ? 'bg-neutral-900 text-white dark:bg-white dark:text-black'
                      : 'bg-neutral-100 dark:bg-neutral-900 text-neutral-700 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800'
                  }`}
                >
                  {rep.id}
                </button>
              ))}
            </div>
          </div>

          {/* Active report details */}
          {activeReport && (
            <div className="space-y-3 bg-neutral-50 dark:bg-black p-3.5 rounded-xl border border-neutral-200 dark:border-neutral-800 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-neutral-700 dark:text-neutral-300">
                  <strong className="font-bold text-neutral-900 dark:text-white">
                    {activeReport.studentName || 'Student Report'}
                  </strong>
                  <span className="text-neutral-400">·</span>
                  <span className="font-mono text-neutral-600 dark:text-neutral-400 font-semibold">{activeReport.id}</span>
                  <span className="text-neutral-400">·</span>
                  <span className="text-neutral-500">{activeReport.timestamp}</span>
                </div>
              </div>

              <div className="p-3 bg-white dark:bg-neutral-900 rounded-lg border border-neutral-200 dark:border-neutral-800 text-neutral-900 dark:text-neutral-100 leading-relaxed font-sans">
                "{activeReport.studentComment}"
              </div>
            </div>
          )}

          {/* Student Reply Preview Card */}
          <div className="space-y-2 pt-2 border-t border-neutral-100 dark:border-neutral-800">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-neutral-900 dark:text-white">
                  Student Reply
                </span>
                <p className="text-[11px] text-neutral-500">
                  AI-drafted response for reporting student. Teacher can edit before dispatch.
                </p>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => {
                    if (activeReport) {
                      updateStudentReplyDraft(selectedCase.questionId, activeReport.id, activeReport.studentReply);
                      showToast('Restored original AI draft.');
                    }
                  }}
                  className="text-xs flex items-center gap-1 px-2.5 py-1 text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white transition-colors font-medium"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Restore</span>
                </button>

                <button
                  onClick={handleCopyStudentReply}
                  className="text-xs font-semibold px-3 py-1.5 min-h-[36px] bg-neutral-900 text-white dark:bg-white dark:text-black rounded-lg hover:bg-neutral-800 dark:hover:bg-neutral-200 transition-colors flex items-center gap-1"
                >
                  {copiedReply ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy Reply</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {activeReport && (
              <textarea
                rows={3}
                value={activeReport.studentReplyDraft || activeReport.studentReply}
                onChange={(e) => updateStudentReplyDraft(selectedCase.questionId, activeReport.id, e.target.value)}
                placeholder="Edit student reply..."
                className="w-full text-xs sm:text-sm p-3 rounded-xl border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-400 dark:focus:border-neutral-600 transition-colors leading-relaxed font-sans"
              />
            )}
          </div>
        </div>
      </div>

      {/* 4. STICKY ACTION BAR */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-black/95 backdrop-blur-md border-t border-neutral-200 dark:border-neutral-800 py-2.5 sm:py-3 px-3 sm:px-6 shadow-2xl transition-colors">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-2">
          {/* Left summary in action bar (Desktop) */}
          <div className="hidden md:flex items-center gap-2 text-xs">
            <span className="font-mono font-bold text-neutral-900 dark:text-white">
              {label}
            </span>
            <span className="text-neutral-400">·</span>
            <span className="font-mono text-neutral-700 dark:text-neutral-300 font-medium">
              Fix: {selectedCase.proposedSurgicalEdit.findValue} → {selectedCase.proposedSurgicalEdit.replaceValue}
            </span>
          </div>

          {/* Action buttons - Large 44px touch targets on Mobile */}
          <div className="flex items-center justify-between w-full md:w-auto gap-2">
            <button
              onClick={() => setIsAuditDrawerOpen(true)}
              className="p-2 sm:px-3 sm:py-2 min-h-[44px] min-w-[44px] text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-lg flex items-center justify-center gap-1.5 transition-colors border border-neutral-300 dark:border-neutral-800"
              title="Audit Log"
            >
              <History className="w-4 h-4 text-neutral-500" />
              <span className="hidden sm:inline">Audit ({selectedCase.auditLog.length})</span>
            </button>

            <button
              onClick={() => setIsEditModalOpen(true)}
              className="px-3 sm:px-3.5 py-2 min-h-[44px] text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-lg flex items-center justify-center gap-1.5 transition-colors border border-neutral-300 dark:border-neutral-800"
            >
              <Edit3 className="w-4 h-4" />
              <span>Edit</span>
            </button>

            <button
              onClick={() => setIsRejectModalOpen(true)}
              className="px-3.5 sm:px-4 py-2 min-h-[44px] text-xs font-semibold text-red-700 dark:text-red-400 bg-red-50 hover:bg-red-100 dark:bg-red-950/30 dark:hover:bg-red-950/50 border border-red-300 dark:border-red-900/60 rounded-lg flex items-center justify-center gap-1.5 transition-colors"
            >
              <XCircle className="w-4 h-4" />
              <span>Reject</span>
            </button>

            <button
              onClick={() => setIsAcceptModalOpen(true)}
              className="flex-1 sm:flex-none px-5 py-2 min-h-[44px] text-xs sm:text-sm font-bold text-white bg-neutral-900 hover:bg-neutral-800 dark:bg-white dark:text-black dark:hover:bg-neutral-200 rounded-lg flex items-center justify-center gap-1.5 shadow transition-all border border-neutral-900 dark:border-white"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Accept Fix</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
