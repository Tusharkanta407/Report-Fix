import React, { createContext, useContext, useState, useEffect } from 'react';
import { QuestionCase, FacultyUser, WorkflowStatus, Subject, RunUsageSummary } from '../types';
import { buildQuestionCases, FACULTY_PROFILES, getRunUsageSummary } from '../data/buildCases';

interface AppContextType {
  cases: QuestionCase[];
  selectedCaseId: string | null;
  selectedCase: QuestionCase | null;
  activeSubjectFilter: Subject | 'All';
  activeRouteFilter: 'all' | 'needs_review' | 'auto_ready' | 'no_change' | 'high_priority' | 'reviewed';
  searchQuery: string;
  sortBy: 'urgency' | 'newest' | 'oldest' | 'most_reported' | 'confidence';
  theme: 'dark' | 'light';
  currentFaculty: FacultyUser;
  runUsage: RunUsageSummary;
  isTokenInspectorOpen: boolean;
  isAuditDrawerOpen: boolean;
  isAcceptModalOpen: boolean;
  isRejectModalOpen: boolean;
  isEditModalOpen: boolean;
  toastMessage: string | null;

  setSelectedCaseId: (id: string | null) => void;
  setActiveSubjectFilter: (sub: Subject | 'All') => void;
  setActiveRouteFilter: (
    route: 'all' | 'needs_review' | 'auto_ready' | 'no_change' | 'high_priority' | 'reviewed'
  ) => void;
  setSearchQuery: (q: string) => void;
  setSortBy: (sort: 'urgency' | 'newest' | 'oldest' | 'most_reported' | 'confidence') => void;
  toggleTheme: () => void;
  setCurrentFaculty: (user: FacultyUser) => void;
  setIsTokenInspectorOpen: (open: boolean) => void;
  setIsAuditDrawerOpen: (open: boolean) => void;
  setIsAcceptModalOpen: (open: boolean) => void;
  setIsRejectModalOpen: (open: boolean) => void;
  setIsEditModalOpen: (open: boolean) => void;
  showToast: (msg: string) => void;

  acceptCaseFix: (caseId: string, comment?: string) => void;
  rejectCaseFix: (caseId: string, reason: string, comment?: string) => void;
  editCaseFix: (caseId: string, findValue: string, replaceValue: string, notes?: string) => void;
  updateStudentReplyDraft: (caseId: string, reportId: string, draft: string) => void;
  toggleStudentReplyReady: (caseId: string, reportId: string) => void;
  resetAllCasesToDefault: () => void;
  downloadResultsJson: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = 'acadza_ai_review_cases_v25_r029_keep_a';
const THEME_STORAGE_KEY = 'acadza_theme_preference';

function loadInitialCases(): QuestionCase[] {
  try {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved) as QuestionCase[];
    }
  } catch {
    // fall through
  }
  return buildQuestionCases();
}

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [cases, setCases] = useState<QuestionCase[]>(loadInitialCases);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeSubjectFilter, setActiveSubjectFilter] = useState<Subject | 'All'>('All');
  const [activeRouteFilter, setActiveRouteFilter] = useState<
    'all' | 'needs_review' | 'auto_ready' | 'no_change' | 'high_priority' | 'reviewed'
  >('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'urgency' | 'newest' | 'oldest' | 'most_reported' | 'confidence'>(
    'urgency'
  );

  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === 'light' || saved === 'dark') return saved;
    } catch {
      // ignore
    }
    return 'light';
  });
  const [currentFaculty, setCurrentFaculty] = useState<FacultyUser>(FACULTY_PROFILES[0]);
  const [runUsage] = useState<RunUsageSummary>(() => getRunUsageSummary());

  const [isTokenInspectorOpen, setIsTokenInspectorOpen] = useState(false);
  const [isAuditDrawerOpen, setIsAuditDrawerOpen] = useState(false);
  const [isAcceptModalOpen, setIsAcceptModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore
    }
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(cases));
    } catch {
      // ignore
    }
  }, [cases]);

  const toggleTheme = () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3200);
  };

  const selectedCase = cases.find((c) => c.questionId === selectedCaseId) || null;

  const acceptCaseFix = (caseId: string, comment?: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.questionId !== caseId) return c;
        const newStatus: WorkflowStatus = 'accepted';
        const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST';
        return {
          ...c,
          workflowStatus: newStatus,
          facultyDecision: {
            action: 'accept',
            reviewerName: currentFaculty.name,
            reviewerRole: currentFaculty.role,
            timestamp,
            comment,
          },
          auditLog: [
            ...c.auditLog,
            {
              id: `aud_${Date.now()}`,
              timestamp,
              actor: currentFaculty.name,
              actorRole: currentFaculty.role,
              action: 'accept' as const,
              previousStatus: c.workflowStatus,
              newStatus,
              comment,
              details: `Faculty accepted AI proposed repair [${c.repairType}]: ${c.proposedSurgicalEdit.findValue} → ${c.proposedSurgicalEdit.replaceValue}`,
            },
          ],
        };
      })
    );
    showToast(`Fix approved`);
    setIsAcceptModalOpen(false);
  };

  const rejectCaseFix = (caseId: string, reason: string, comment?: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.questionId !== caseId) return c;
        const newStatus: WorkflowStatus = 'rejected';
        const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST';
        return {
          ...c,
          workflowStatus: newStatus,
          facultyDecision: {
            action: 'reject',
            reviewerName: currentFaculty.name,
            reviewerRole: currentFaculty.role,
            timestamp,
            rejectionReason: reason,
            comment,
          },
          auditLog: [
            ...c.auditLog,
            {
              id: `aud_${Date.now()}`,
              timestamp,
              actor: currentFaculty.name,
              actorRole: currentFaculty.role,
              action: 'reject' as const,
              previousStatus: c.workflowStatus,
              newStatus,
              comment,
              details: `Faculty rejected proposal. Reason: ${reason}${comment ? ` | Note: ${comment}` : ''}`,
            },
          ],
        };
      })
    );
    showToast(`Proposed fix rejected`);
    setIsRejectModalOpen(false);
  };

  const editCaseFix = (caseId: string, findValue: string, replaceValue: string, notes?: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.questionId !== caseId) return c;
        const newStatus: WorkflowStatus = 'edited';
        const timestamp = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST';
        return {
          ...c,
          workflowStatus: newStatus,
          proposedSurgicalEdit: {
            ...c.proposedSurgicalEdit,
            findValue,
            replaceValue,
          },
          facultyDecision: {
            action: 'edit',
            reviewerName: currentFaculty.name,
            reviewerRole: currentFaculty.role,
            timestamp,
            comment: notes,
            editedEdit: { findValue, replaceValue, notes: notes || '' },
          },
          auditLog: [
            ...c.auditLog,
            {
              id: `aud_${Date.now()}`,
              timestamp,
              actor: currentFaculty.name,
              actorRole: currentFaculty.role,
              action: 'edit' as const,
              previousStatus: c.workflowStatus,
              newStatus,
              comment: notes,
              details: `Faculty modified surgical replacement: "${findValue}" → "${replaceValue}"`,
            },
          ],
        };
      })
    );
    showToast(`Surgical fix updated`);
    setIsEditModalOpen(false);
  };

  const updateStudentReplyDraft = (caseId: string, reportId: string, draft: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.questionId !== caseId) return c;
        return {
          ...c,
          reports: c.reports.map((r) => (r.id === reportId ? { ...r, studentReplyDraft: draft } : r)),
        };
      })
    );
  };

  const toggleStudentReplyReady = (caseId: string, reportId: string) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.questionId !== caseId) return c;
        return {
          ...c,
          reports: c.reports.map((r) =>
            r.id === reportId ? { ...r, isReplyReady: !r.isReplyReady } : r
          ),
        };
      })
    );
    showToast(`Reply status updated for ${reportId}`);
  };

  const resetAllCasesToDefault = () => {
    const fresh = buildQuestionCases();
    setCases(fresh);
    localStorage.removeItem(LOCAL_STORAGE_KEY);
    showToast('Reset to precomputed engine results.');
  };

  const downloadResultsJson = () => {
    const rows = cases.flatMap((c) =>
      c.reports.map((r) => ({
        reportId: r.id,
        questionId: c.questionId,
        verdict: r.aiVerdict,
        repair: c.repairType === 'none' ? null : c.repairType,
        edit:
          c.proposedSurgicalEdit.targetField === 'none'
            ? null
            : {
                field:
                  c.proposedSurgicalEdit.targetField === 'storedAnswer'
                    ? 'answer'
                    : c.proposedSurgicalEdit.targetField === 'storedSolutionHtml'
                      ? 'solution'
                      : c.proposedSurgicalEdit.targetField === 'questionHtml'
                        ? 'question'
                        : 'question',
                find: c.proposedSurgicalEdit.findValue,
                replace: c.proposedSurgicalEdit.replaceValue,
              },
        route: r.aiRoute,
        confidence: Number((r.aiConfidence / 100).toFixed(4)),
        evidence: c.summaryLine,
        student_reply: r.studentReplyDraft || r.studentReply,
        faculty_status: c.workflowStatus,
        faculty_decision: c.facultyDecision || null,
      }))
    );

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(rows, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', 'results.json');
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast('results.json downloaded');
  };

  return (
    <AppContext.Provider
      value={{
        cases,
        selectedCaseId,
        selectedCase,
        activeSubjectFilter,
        activeRouteFilter,
        searchQuery,
        sortBy,
        theme,
        currentFaculty,
        runUsage,
        isTokenInspectorOpen,
        isAuditDrawerOpen,
        isAcceptModalOpen,
        isRejectModalOpen,
        isEditModalOpen,
        toastMessage,
        setSelectedCaseId,
        setActiveSubjectFilter,
        setActiveRouteFilter,
        setSearchQuery,
        setSortBy,
        toggleTheme,
        setCurrentFaculty,
        setIsTokenInspectorOpen,
        setIsAuditDrawerOpen,
        setIsAcceptModalOpen,
        setIsRejectModalOpen,
        setIsEditModalOpen,
        showToast,
        acceptCaseFix,
        rejectCaseFix,
        editCaseFix,
        updateStudentReplyDraft,
        toggleStudentReplyReady,
        resetAllCasesToDefault,
        downloadResultsJson,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
