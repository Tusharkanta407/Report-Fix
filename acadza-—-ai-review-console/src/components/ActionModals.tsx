import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  X,
  CheckCircle2,
  XCircle,
  Edit3,
  History,
  User,
} from 'lucide-react';
import { caseLabel } from '../utils/caseLabel';

export const AcceptModal: React.FC = () => {
  const { isAcceptModalOpen, setIsAcceptModalOpen, selectedCase, acceptCaseFix, currentFaculty } = useApp();
  const [comment, setComment] = useState('');

  if (!isAcceptModalOpen || !selectedCase) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    acceptCaseFix(selectedCase.questionId, comment.trim() || undefined);
    setComment('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
              Approve & Accept Proposed Fix
            </h3>
          </div>
          <button
            onClick={() => setIsAcceptModalOpen(false)}
            className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 sm:p-6 space-y-4 text-xs sm:text-sm">
          {/* Summary Box */}
          <div className="p-3.5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-black space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="text-neutral-500">Question:</span>
              <span className="font-mono font-bold text-neutral-900 dark:text-white">
                {caseLabel(selectedCase)}
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="text-neutral-500">Subject:</span>
              <span className="font-medium text-neutral-800 dark:text-neutral-200">
                {selectedCase.subject} • {selectedCase.chapter}
              </span>
            </div>

            <div className="pt-2 border-t border-neutral-200 dark:border-neutral-800 flex items-center justify-between text-xs">
              <span className="text-neutral-500">Surgical replacement:</span>
              <div className="flex items-center gap-2 font-mono">
                <span className="px-2 py-0.5 rounded bg-red-950/60 text-red-400 line-through border border-red-900/60">
                  {selectedCase.proposedSurgicalEdit.findValue}
                </span>
                <span>→</span>
                <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 font-bold border border-emerald-900/60">
                  {selectedCase.proposedSurgicalEdit.replaceValue}
                </span>
              </div>
            </div>
          </div>

          {/* Active Reviewer */}
          <div className="flex items-center justify-between text-xs text-neutral-500 px-1">
            <span className="flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-neutral-400" />
              <span>Reviewing Faculty:</span>
            </span>
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              {currentFaculty.name}
            </span>
          </div>

          {/* Optional Reviewer Comment */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Faculty Verification Notes (Optional):
            </label>
            <textarea
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g. Verified with Gauss's law calculation; approved for CMS update."
              className="w-full text-xs p-3 rounded-xl border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-400 dark:focus:border-neutral-600"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsAcceptModalOpen(false)}
              className="px-4 py-2 min-h-[40px] text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 min-h-[40px] text-xs font-bold text-black bg-white hover:bg-neutral-200 dark:bg-white dark:text-black dark:hover:bg-neutral-200 rounded-lg shadow transition-colors flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Confirm & Accept Fix</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const RejectModal: React.FC = () => {
  const { isRejectModalOpen, setIsRejectModalOpen, selectedCase, rejectCaseFix, currentFaculty } = useApp();
  const [selectedReason, setSelectedReason] = useState('Wrong academic reasoning');
  const [comment, setComment] = useState('');

  const REASONS = [
    'Wrong academic reasoning',
    'Incorrect repair type',
    'Unsafe edit (destructive modification)',
    'Insufficient evidence / ambiguity',
    'Alternative correction required',
    'Student misunderstood standard convention',
  ];

  if (!isRejectModalOpen || !selectedCase) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    rejectCaseFix(selectedCase.questionId, selectedReason, comment.trim() || undefined);
    setComment('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <XCircle className="w-5 h-5 text-red-500" />
            <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
              Reject Proposed AI Fix
            </h3>
          </div>
          <button
            onClick={() => setIsRejectModalOpen(false)}
            className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 sm:p-6 space-y-4 text-xs sm:text-sm">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Required Rejection Reason:
            </label>
            <div className="space-y-1.5">
              {REASONS.map((r) => (
                <label
                  key={r}
                  className={`flex items-center gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                    selectedReason === r
                      ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-400 dark:border-neutral-700 text-neutral-900 dark:text-white font-medium'
                      : 'bg-white dark:bg-black border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-900'
                  }`}
                >
                  <input
                    type="radio"
                    name="rejectionReason"
                    value={r}
                    checked={selectedReason === r}
                    onChange={() => setSelectedReason(r)}
                    className="accent-black dark:accent-white"
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Additional Faculty Notes:
            </label>
            <textarea
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Explain why this proposal is rejected..."
              className="w-full text-xs p-3 rounded-xl border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-red-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsRejectModalOpen(false)}
              className="px-4 py-2 min-h-[40px] text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 min-h-[40px] text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-lg shadow transition-colors flex items-center gap-1.5"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Confirm Rejection</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const EditFixModal: React.FC = () => {
  const { isEditModalOpen, setIsEditModalOpen, selectedCase, editCaseFix } = useApp();
  const [findValue, setFindValue] = useState(selectedCase?.proposedSurgicalEdit.findValue || '');
  const [replaceValue, setReplaceValue] = useState(selectedCase?.proposedSurgicalEdit.replaceValue || '');
  const [notes, setNotes] = useState('');

  React.useEffect(() => {
    if (selectedCase) {
      setFindValue(selectedCase.proposedSurgicalEdit.findValue);
      setReplaceValue(selectedCase.proposedSurgicalEdit.replaceValue);
    }
  }, [selectedCase]);

  if (!isEditModalOpen || !selectedCase) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replaceValue.trim()) return;
    editCaseFix(selectedCase.questionId, findValue.trim(), replaceValue.trim(), notes.trim() || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <Edit3 className="w-5 h-5 text-neutral-800 dark:text-neutral-200" />
            <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
              Edit Proposed Surgical Fix
            </h3>
          </div>
          <button
            onClick={() => setIsEditModalOpen(false)}
            className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 sm:p-6 space-y-4 text-xs sm:text-sm">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Find String / Current Stored Value:
            </label>
            <input
              type="text"
              value={findValue}
              onChange={(e) => setFindValue(e.target.value)}
              className="w-full text-xs font-mono p-2.5 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black text-neutral-900 dark:text-neutral-100 focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Replace With / Faculty Verified Value:
            </label>
            <input
              type="text"
              value={replaceValue}
              onChange={(e) => setReplaceValue(e.target.value)}
              className="w-full text-xs font-mono font-bold p-2.5 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-emerald-950/20 text-emerald-400 focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
              Reason for Adjustment:
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why was this adjustment made?"
              className="w-full text-xs p-2.5 rounded-lg border border-neutral-300 dark:border-neutral-800 bg-neutral-50 dark:bg-black text-neutral-900 dark:text-neutral-100 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsEditModalOpen(false)}
              className="px-4 py-2 min-h-[40px] text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 min-h-[40px] text-xs font-bold text-black bg-white hover:bg-neutral-200 dark:bg-white dark:text-black dark:hover:bg-neutral-200 rounded-lg shadow transition-colors"
            >
              Save Edited Correction
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const AuditDrawer: React.FC = () => {
  const { isAuditDrawerOpen, setIsAuditDrawerOpen, selectedCase } = useApp();

  if (!isAuditDrawerOpen || !selectedCase) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-md bg-white dark:bg-neutral-950 border-l border-neutral-200 dark:border-neutral-800 h-full shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-neutral-200 dark:border-neutral-800 shrink-0">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-neutral-400" />
            <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
              Case Audit Trail
            </h3>
          </div>
          <button
            onClick={() => setIsAuditDrawerOpen(false)}
            className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 sm:p-6 overflow-y-auto flex-1 space-y-4 text-xs">
          <div className="p-3 rounded-lg bg-neutral-50 dark:bg-black border border-neutral-200 dark:border-neutral-800">
            <div className="font-mono font-bold text-neutral-900 dark:text-white">
              {caseLabel(selectedCase)}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">
              Current Status: <strong className="uppercase text-neutral-900 dark:text-neutral-100">{selectedCase.workflowStatus}</strong>
            </div>
          </div>

          <div className="space-y-4 pt-2">
            {selectedCase.auditLog.length === 0 ? (
              <div className="text-center py-8 text-neutral-400">
                No human review events recorded yet.
              </div>
            ) : (
              selectedCase.auditLog.map((log) => (
                <div
                  key={log.id}
                  className="relative pl-5 pb-4 border-l-2 border-neutral-300 dark:border-neutral-800 last:border-transparent last:pb-0"
                >
                  <div className="absolute -left-[5px] top-0 w-2 h-2 rounded-full bg-neutral-900 dark:bg-white" />
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-[11px] text-neutral-400">
                      <span className="font-semibold text-neutral-900 dark:text-neutral-200">
                        {log.actor}
                      </span>
                      <span className="font-mono">{log.timestamp}</span>
                    </div>
                    <div className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed">
                      {log.details}
                    </div>
                    {log.comment && (
                      <div className="text-[11px] text-neutral-500 bg-neutral-100 dark:bg-neutral-900 p-2 rounded italic">
                        "{log.comment}"
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 flex justify-end shrink-0">
          <button
            onClick={() => setIsAuditDrawerOpen(false)}
            className="px-4 py-2 min-h-[40px] text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-200 dark:hover:bg-neutral-900 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
