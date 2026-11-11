import React, { useEffect } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { Header } from './components/Header';
import { SummaryCards } from './components/SummaryCards';
import { SubjectCards } from './components/SubjectCards';
import { PriorityQueue } from './components/PriorityQueue';
import { CaseReviewWorkspace } from './components/CaseReviewWorkspace';
import { TokenWasteInspectorModal } from './components/TokenWasteInspectorModal';
import { AcceptModal, RejectModal, EditFixModal, AuditDrawer } from './components/ActionModals';
import { CheckCircle2 } from 'lucide-react';

const MainContent: React.FC = () => {
  const { selectedCaseId, setSelectedCaseId, toastMessage } = useApp();

  // Escape key to exit case review
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedCaseId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setSelectedCaseId]);

  return (
    <div className="min-h-screen bg-neutral-100 dark:bg-black text-neutral-900 dark:text-neutral-100 transition-colors flex flex-col font-sans w-full max-w-full overflow-x-hidden">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6">
        {selectedCaseId ? (
          <CaseReviewWorkspace />
        ) : (
          <div className="space-y-4 sm:space-y-6">
            <SummaryCards />
            <SubjectCards />
            <PriorityQueue />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-neutral-200 dark:border-neutral-800/80 py-4 px-4 sm:px-6 text-center text-xs text-neutral-500 bg-white dark:bg-black">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>
            Acadza AI Review Console · Every student report deserves a clear answer.
          </span>
          <span className="font-mono text-[11px] text-neutral-400">
            Precomputed from engine results.json · 44 reports
          </span>
        </div>
      </footer>

      {/* Global Modals and Drawers */}
      <TokenWasteInspectorModal />
      <AcceptModal />
      <RejectModal />
      <EditFixModal />
      <AuditDrawer />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-20 sm:bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-black text-xs font-semibold shadow-2xl border border-neutral-800 dark:border-neutral-200 flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
};

export default function App() {
  return (
    <AppProvider>
      <MainContent />
    </AppProvider>
  );
}
