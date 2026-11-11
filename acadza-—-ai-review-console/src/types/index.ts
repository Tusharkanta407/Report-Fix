export type Subject = 'Physics' | 'Chemistry' | 'Mathematics' | 'Biology' | 'Botany' | 'Zoology';

export type AIVerdict =
  | 'defect'
  | 'no_error'
  | 'display_issue'
  | 'app_issue'
  | 'language_mode'
  | 'already_fixed'
  | 'not_actionable';

export type AIRoute = 'auto_apply' | 'faculty_review' | 'no_change';

export type WorkflowStatus = 'pending' | 'accepted' | 'rejected' | 'edited' | 'resolved';

/** Closed taxonomy repair keys from data/taxonomy.json (+ none when no repair). */
export type RepairType =
  | 'spelling'
  | 'noise'
  | 'exam_reference'
  | 'markup_leak'
  | 'answer_form'
  | 'notation'
  | 'stem_data'
  | 'option_repair'
  | 'solution_fix'
  | 'solution_missing'
  | 'answer_key'
  | 'type_mismatch'
  | 'identical_options'
  | 'diagram'
  | 'wrong_question'
  | 'unsound'
  | 'wrong_chapter'
  | 'syllabus'
  | 'none';

export type Priority = 'high' | 'medium' | 'low';

export type PlatformSource = 'web' | 'android' | 'ios';

export interface StudentReport {
  id: string;
  questionId: string;
  studentName?: string;
  studentRoll?: string;
  timestamp: string;
  studentComment: string;
  platform: PlatformSource;
  appVersion?: string;
  aiVerdict: AIVerdict;
  aiRoute: AIRoute;
  aiConfidence: number;
  studentReply: string;
  studentReplyDraft: string;
  isReplyReady: boolean;
}

export interface QuestionOption {
  label: string;
  textHtml: string;
  isOriginalCorrect: boolean;
  isProposedCorrect?: boolean;
}

export interface ProposedSurgicalEdit {
  targetField: 'storedAnswer' | 'questionHtml' | 'storedSolutionHtml' | 'options' | 'none';
  findValue: string;
  replaceValue: string;
  taxonomyLabel: string;
  affectedOptionLabel?: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  actorRole: string;
  action: 'accept' | 'reject' | 'edit' | 'comment' | 'reopen';
  previousStatus: WorkflowStatus;
  newStatus: WorkflowStatus;
  comment?: string;
  details: string;
  diffSummary?: string;
}

export interface TokenUsageReport {
  promptTokens: number;
  reasoningTokens: number;
  outputTokens: number;
  totalTokens: number;
  cachedTokens: number;
  estimatedCostUsd: number;
  wastedTokens: number;
  wasteReason?: string;
  efficiencyScore: number;
  cacheHit: boolean;
  byStep?: Record<string, number>;
}

export interface QuestionCase {
  questionId: string;
  /** Human CMS code when present (e.g. SecBQ22). */
  humanQid?: string | null;
  displayTitle: string;
  subject: Subject;
  originalSubject: Subject;
  chapter: string;
  topic: string;
  exam: string;
  questionHtml: string;
  options?: QuestionOption[];
  storedAnswer: string;
  storedSolutionHtml: string;
  diagramSvg?: string;
  diagramCaption?: string;
  reports: StudentReport[];
  aiVerdict: AIVerdict;
  aiRoute: AIRoute;
  aiConfidence: number; // 0 - 100
  repairType: RepairType;
  priority: Priority;
  summaryLine: string;
  issueExplanation: string;
  proposedSurgicalEdit: ProposedSurgicalEdit;
  independentAcademicVerification: string;
  verificationEvidence: string[];
  detailedReasoning: string;
  workflowStatus: WorkflowStatus;
  facultyDecision?: {
    action: 'accept' | 'reject' | 'edit';
    reviewerName: string;
    reviewerRole: string;
    timestamp: string;
    rejectionReason?: string;
    comment?: string;
    editedEdit?: {
      findValue: string;
      replaceValue: string;
      notes: string;
    };
  };
  auditLog: AuditEvent[];
  tokenUsage: TokenUsageReport;
}

export interface FacultyUser {
  id: string;
  name: string;
  role: string;
  department: Subject | 'All';
  avatarInitials: string;
}

export interface RunUsageSummary {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  calls: number;
  cacheHits: number;
  estimatedUsd: number;
  failedCalls: number;
  byStep: Record<
    string,
    {
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      calls: number;
      estimated_usd: number;
    }
  >;
}
