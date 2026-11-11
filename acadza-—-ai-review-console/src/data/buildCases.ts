import questionsRaw from './real/questions.json';
import reportsRaw from './real/reports.json';
import resultsRaw from './real/results.json';
import casesRaw from './real/cases.json';
import usageRaw from './real/usage.json';
import {
  AIRoute,
  AIVerdict,
  Priority,
  ProposedSurgicalEdit,
  QuestionCase,
  QuestionOption,
  RepairType,
  RunUsageSummary,
  StudentReport,
  Subject,
  TokenUsageReport,
  WorkflowStatus,
} from '../types';
import { FACULTY_PROFILES } from './faculty';

type RawQuestion = {
  _id: string;
  qid: string | null;
  questionType: string;
  subject: string;
  chapter: string;
  concept: string | null;
  subConcept: string | null;
  level: string;
  scq?: { question: string; solution: string; answer: string };
  mcq?: { question: string; solution: string; answer: string | string[] };
  integerQuestion?: { question: string; solution: string; answer: string };
};

type RawReport = {
  reportId: string;
  questionId: string;
  studentId: string;
  source: string;
  reportedAt: string;
  comment: string;
};

type RawResult = {
  reportId: string;
  questionId: string;
  verdict: AIVerdict;
  repair: string | null;
  edit: { field: string; find: string; replace: string } | null;
  route: AIRoute;
  confidence: number;
  evidence: string;
  student_reply: string;
};

type RawCase = {
  reportId: string;
  questionId: string;
  comment: string;
  reportedAt: string;
  source: string;
  studentId: string;
  question?: {
    subject?: string;
    chapter?: string;
    concept?: string | null;
    level?: string;
    questionType?: string;
    answer_raw?: string;
  };
  content_checks?: {
    options?: Array<{ letter: string; text: string }>;
  };
  interpretation?: {
    claim_summary?: string;
    category?: string;
  };
  solver?: {
    can_solve?: boolean;
    final_answer?: string;
    working?: string;
    confidence?: number;
  };
  solution_reading?: {
    solution_final_answer?: string;
    solution_errors?: string[];
    matches_question?: boolean;
  };
  proposal?: {
    checks?: string[];
    faculty_note?: string;
    independent_confirmation?: boolean;
  };
  decision?: RawResult;
  preview?: { field?: string; before?: string; after?: string };
  faculty_note?: string;
  tokens?: Record<string, number>;
  independent_confirmation?: boolean;
  llm_confidence?: number;
  fast_path?: boolean;
};

const questions = questionsRaw as RawQuestion[];
const reports = reportsRaw as RawReport[];
const results = resultsRaw as RawResult[];
const engineCases = casesRaw as RawCase[];
const usage = usageRaw as {
  run_totals: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    calls: number;
    cache_hits: number;
    estimated_usd: number;
    failed_calls: number;
  };
  by_step: RunUsageSummary['byStep'];
};

const questionById = new Map(questions.map((q) => [q._id, q]));
const resultByReportId = new Map(results.map((r) => [r.reportId, r]));
const caseByReportId = new Map(engineCases.map((c) => [c.reportId, c]));

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&rsquo;/gi, "'")
    .replace(/&ldquo;|&rdquo;/gi, '"')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function shortTitle(html: string, chapter: string): string {
  const plain = stripHtml(html);
  if (!plain) return chapter || 'Untitled question';
  return plain.length > 90 ? `${plain.slice(0, 87)}…` : plain;
}

function mapSubject(raw: string): Subject {
  if (raw === 'Botany' || raw === 'Zoology' || raw === 'Biology') return raw as Subject;
  if (raw === 'Physics' || raw === 'Chemistry' || raw === 'Mathematics') return raw;
  return 'Physics';
}

function payloadFor(q: RawQuestion): { question: string; solution: string; answer: string } {
  if (q.questionType === 'scq' && q.scq) {
    return { question: q.scq.question, solution: q.scq.solution, answer: String(q.scq.answer) };
  }
  if (q.questionType === 'mcq' && q.mcq) {
    const ans = Array.isArray(q.mcq.answer) ? q.mcq.answer.join(',') : String(q.mcq.answer);
    return { question: q.mcq.question, solution: q.mcq.solution, answer: ans };
  }
  if (q.questionType === 'integerQuestion' && q.integerQuestion) {
    return {
      question: q.integerQuestion.question,
      solution: q.integerQuestion.solution,
      answer: String(q.integerQuestion.answer),
    };
  }
  return { question: '<p>(question body unavailable)</p>', solution: '', answer: '' };
}

function mapEditField(field: string | undefined): ProposedSurgicalEdit['targetField'] {
  if (!field) return 'none';
  if (field === 'answer') return 'storedAnswer';
  if (field === 'solution') return 'storedSolutionHtml';
  if (field === 'question') return 'questionHtml';
  if (field === 'options') return 'options';
  return 'none';
}

function asRepair(repair: string | null | undefined): RepairType {
  if (!repair) return 'none';
  return repair as RepairType;
}

function pickPriority(route: AIRoute, repair: RepairType, reportCount: number, verdict: AIVerdict): Priority {
  if (route === 'faculty_review') {
    if (repair === 'answer_key' || repair === 'diagram' || repair === 'unsound' || reportCount >= 3) {
      return 'high';
    }
    return 'medium';
  }
  if (route === 'auto_apply' && verdict === 'defect') return 'medium';
  return 'low';
}

function formatTimestamp(iso: string): string {
  try {
    return (
      new Date(iso).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }) + ' IST'
    );
  } catch {
    return iso;
  }
}

function buildOptions(
  engineCase: RawCase | undefined,
  storedAnswer: string,
  edit: RawResult['edit']
): QuestionOption[] | undefined {
  const opts = engineCase?.content_checks?.options;
  if (!opts || opts.length === 0) return undefined;

  const proposed =
    edit?.field === 'answer' ? String(edit.replace || '').toUpperCase() : undefined;
  const stored = String(storedAnswer || '').toUpperCase();

  return opts.map((o) => {
    const label = o.letter.toUpperCase();
    return {
      label,
      textHtml: o.text || '',
      isOriginalCorrect: label === stored || stored.includes(label),
      isProposedCorrect: proposed ? label === proposed || proposed.includes(label) : undefined,
    };
  });
}

function buildTokenUsage(engineCase: RawCase | undefined): TokenUsageReport {
  const t = engineCase?.tokens || {};
  const total = Math.round(Number(t.total_allocated || 0));
  const interpreter = Math.round(Number(t.interpreter || 0));
  const comparator = Math.round(Number(t.comparator || 0));
  const reply = Math.round(Number(t.reply || 0));
  const shared = Math.round(Number(t.question_shared_allocated || t.question_shared_total || 0));
  const promptish = interpreter + comparator + reply + shared;
  return {
    promptTokens: promptish || total,
    reasoningTokens: comparator,
    outputTokens: reply,
    totalTokens: total || promptish,
    cachedTokens: 0,
    estimatedCostUsd: Number(((total || promptish) * 0.00000015).toFixed(5)),
    wastedTokens: 0,
    wasteReason: undefined,
    efficiencyScore: 100,
    cacheHit: false,
    byStep: {
      interpreter,
      comparator,
      reply,
      question_shared: shared,
    },
  };
}

function buildEvidence(engineCase: RawCase | undefined, result: RawResult): string[] {
  const checks = engineCase?.proposal?.checks || [];
  const evidence: string[] = [];
  if (result.evidence) evidence.push(result.evidence);
  for (const c of checks) {
    evidence.push(`Check: ${c.replace(/_/g, ' ')}`);
  }
  if (engineCase?.independent_confirmation) {
    const solved = Boolean(engineCase?.solver?.final_answer);
    evidence.push(
      solved
        ? 'Independent confirmation: solver and solution reading agree on the proposed fix'
        : 'Confirmation: deterministic / metadata check (no physics re-solve needed)',
    );
  }
  if (engineCase?.solution_reading?.solution_final_answer) {
    evidence.push(`Stored solution ends at: ${engineCase.solution_reading.solution_final_answer}`);
  }
  if (engineCase?.solver?.final_answer) {
    evidence.push(`Independent solver answer: ${engineCase.solver.final_answer}`);
  }
  return evidence.length ? evidence : ['No additional corroborating checks recorded'];
}

function newestReportIso(reps: RawReport[]): string {
  return reps.map((r) => r.reportedAt).sort().slice(-1)[0] || '';
}

export function getRunUsageSummary(): RunUsageSummary {
  return {
    promptTokens: usage.run_totals.prompt_tokens,
    completionTokens: usage.run_totals.completion_tokens,
    totalTokens: usage.run_totals.total_tokens,
    calls: usage.run_totals.calls,
    cacheHits: usage.run_totals.cache_hits,
    estimatedUsd: usage.run_totals.estimated_usd,
    failedCalls: usage.run_totals.failed_calls,
    byStep: usage.by_step,
  };
}

export function buildQuestionCases(): QuestionCase[] {
  const byQuestion = new Map<string, RawReport[]>();
  for (const r of reports) {
    const list = byQuestion.get(r.questionId) || [];
    list.push(r);
    byQuestion.set(r.questionId, list);
  }

  const cases: QuestionCase[] = [];

  for (const [questionId, qReports] of byQuestion.entries()) {
    qReports.sort((a, b) => a.reportedAt.localeCompare(b.reportedAt));

    const q = questionById.get(questionId);
    const payload = q ? payloadFor(q) : { question: '<p>(missing)</p>', solution: '', answer: '' };
    const leadReport = qReports[0];
    const leadResult = resultByReportId.get(leadReport.reportId);
    const leadCase = caseByReportId.get(leadReport.reportId);

    // Prefer the "worst"/most actionable sibling result for case-level route
    const siblingResults = qReports
      .map((r) => resultByReportId.get(r.reportId))
      .filter(Boolean) as RawResult[];

    const ranked = [...siblingResults].sort((a, b) => {
      const score = (r: RawResult) =>
        (r.route === 'faculty_review' ? 300 : 0) +
        (r.route === 'auto_apply' ? 200 : 0) +
        (r.verdict === 'defect' ? 100 : 0) +
        Math.round((r.confidence || 0) * 10);
      return score(b) - score(a);
    });
    const primary = ranked[0] || leadResult;

    if (!primary) continue;

    const subject = mapSubject(q?.subject || leadCase?.question?.subject || 'Physics');
    const chapter = q?.chapter || leadCase?.question?.chapter || 'Unknown chapter';
    const topic = q?.concept || q?.subConcept || leadCase?.question?.concept || q?.level || '—';
    const repair = asRepair(primary.repair);
    const route = primary.route;
    const verdict = primary.verdict;
    const confPct = Math.round((primary.confidence || 0) * 1000) / 10;

    const studentReports: StudentReport[] = qReports.map((r) => {
      const res = resultByReportId.get(r.reportId) || primary;
      const src = (r.source || 'web').toLowerCase();
      const platform = (src === 'android' || src === 'ios' || src === 'web' ? src : 'web') as StudentReport['platform'];
      return {
        id: r.reportId,
        questionId,
        studentName: r.studentId,
        timestamp: formatTimestamp(r.reportedAt),
        studentComment: r.comment || '(empty comment)',
        platform,
        aiVerdict: res.verdict,
        aiRoute: res.route,
        aiConfidence: Math.round((res.confidence || 0) * 1000) / 10,
        studentReply: res.student_reply || '',
        studentReplyDraft: res.student_reply || '',
        isReplyReady: res.route === 'auto_apply' || res.route === 'no_change',
      };
    });

    const edit = primary.edit;
    const proposedSurgicalEdit: ProposedSurgicalEdit = {
      targetField: mapEditField(edit?.field),
      findValue: edit?.find ?? '—',
      replaceValue: edit?.replace ?? '—',
      taxonomyLabel: repair === 'none' ? primary.verdict : repair,
      affectedOptionLabel:
        edit?.field === 'answer' && /^[A-D]$/i.test(String(edit.replace || ''))
          ? String(edit.replace).toUpperCase()
          : undefined,
    };

    const solverWorking = leadCase?.solver?.working || '';
    const facultyNote = leadCase?.faculty_note || leadCase?.proposal?.faculty_note || '';
    const claim = leadCase?.interpretation?.claim_summary || leadReport.comment;
    const solverFinal = String(leadCase?.solver?.final_answer || '');
    const proposedReplace = edit?.replace != null ? String(edit.replace) : '';
    // When guard rewrote the key away from a hallucinated solver final, don't show that working as "proof".
    const solverConflictsProposal =
      Boolean(proposedReplace) &&
      Boolean(solverFinal) &&
      solverFinal.trim() !== '' &&
      proposedReplace.trim() !== '' &&
      solverFinal.trim().toUpperCase() !== proposedReplace.trim().toUpperCase();
    const academicProof = solverConflictsProposal
      ? facultyNote ||
        primary.evidence ||
        `Proposed key ${proposedReplace} follows the stored solution / student claim; solver final ${solverFinal} was rejected as inconsistent.`
      : solverWorking || facultyNote || primary.evidence;
    const lowRiskRepairs = new Set([
      'spelling',
      'noise',
      'exam_reference',
      'markup_leak',
      'answer_form',
      'notation',
    ]);
    const deterministicOnly =
      Boolean(leadCase?.fast_path) ||
      lowRiskRepairs.has(repair) ||
      ['app_issue', 'display_issue', 'language_mode', 'already_fixed', 'not_actionable'].includes(
        verdict
      );

    const workflowStatus: WorkflowStatus = route === 'no_change' ? 'resolved' : 'pending';

    cases.push({
      questionId,
      humanQid: q?.qid ?? null,
      displayTitle: shortTitle(payload.question, chapter),
      subject,
      originalSubject: subject,
      chapter,
      topic: String(topic || '—'),
      exam: 'JEE / NEET',
      questionHtml: payload.question,
      options: buildOptions(leadCase, payload.answer, edit),
      storedAnswer: payload.answer,
      storedSolutionHtml: payload.solution || '<p>(no solution stored)</p>',
      reports: studentReports,
      aiVerdict: verdict,
      aiRoute: route,
      aiConfidence: confPct,
      repairType: repair,
      priority: pickPriority(route, repair, qReports.length, verdict),
      summaryLine: primary.evidence || claim,
      issueExplanation: primary.evidence || facultyNote || claim,
      proposedSurgicalEdit,
      independentAcademicVerification: deterministicOnly
        ? facultyNote ||
          primary.evidence ||
          'Deterministic content check — no academic re-solve required for this report type.'
        : academicProof || 'No independent solver working was recorded for this case.',
      verificationEvidence: buildEvidence(leadCase || caseByReportId.get(primary.reportId), primary),
      detailedReasoning: deterministicOnly
        ? [
            'Path: deterministic fast-path (spelling / exam tag / markup / non-content / injection).',
            facultyNote && `Faculty note: ${facultyNote}`,
            primary.evidence && `Evidence: ${primary.evidence}`,
            `Route: ${route} · Verdict: ${verdict} · Repair: ${repair}`,
          ]
            .filter(Boolean)
            .join('\n\n')
        : [
            facultyNote && `Faculty note: ${facultyNote}`,
            primary.evidence && `Evidence: ${primary.evidence}`,
            !solverConflictsProposal && solverWorking && `Solver working:\n${solverWorking}`,
            solverConflictsProposal &&
              `Solver final ${solverFinal} conflicted with proposed ${proposedReplace} — working omitted from proof.`,
            leadCase?.solution_reading?.solution_final_answer &&
              `Solution reader final: ${leadCase.solution_reading.solution_final_answer}`,
            `Route: ${route} · Verdict: ${verdict} · Repair: ${repair}`,
          ]
            .filter(Boolean)
            .join('\n\n'),
      workflowStatus,
      auditLog: [
        {
          id: `aud_${questionId.slice(-6)}_${leadReport.reportId}`,
          timestamp: formatTimestamp(leadReport.reportedAt),
          actor: 'Acadza triage engine',
          actorRole: 'System',
          action: 'comment',
          previousStatus: 'pending',
          newStatus: workflowStatus,
          details: `Ingested ${qReports.length} report(s). Primary decision from ${primary.reportId}: ${verdict}/${repair || 'none'} → ${route} (confidence ${confPct}%).`,
        },
      ],
      tokenUsage: buildTokenUsage(leadCase || caseByReportId.get(primary.reportId)),
    });

    // attach newest for sorting helpers via mutation-safe field order later
    void newestReportIso(qReports);
  }

  cases.sort((a, b) => {
    const score = (c: QuestionCase) =>
      (c.workflowStatus === 'pending' && c.aiRoute === 'faculty_review' ? 1000 : 0) +
      (c.priority === 'high' ? 300 : c.priority === 'medium' ? 100 : 0) +
      c.reports.length * 40 +
      (c.aiRoute === 'auto_apply' ? 20 : 0);
    return score(b) - score(a);
  });

  return cases;
}

export { FACULTY_PROFILES };
