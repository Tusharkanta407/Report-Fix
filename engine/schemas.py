"""Typed records shared across the pipeline.

LLM-facing models (SolverResult, SolutionReading, Interpretation, Proposal, ReplyDraft)
are used as structured-output schemas. Everything else is internal.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

Route = Literal["auto_apply", "faculty_review", "no_change"]
EditField = Literal["question", "solution", "answer", "questionType"]
AnswerValue = Union[str, list[str]]

CHECK_IDS = (
    "solver_agrees",
    "solution_agrees",
    "deterministic_check",
    "error_history",
    "solution_states_value",
    "student_claim_verified",
)

INTENT_CATEGORIES = (
    "answer_key",
    "wrong_option_value",
    "missing_option",
    "blank_option",
    "identical_options",
    "missing_data",
    "figure_missing",
    "spelling",
    "stray_text",
    "exam_reference",
    "markup_leak",
    "notation",
    "unit_or_format",
    "solution_wrong",
    "solution_mismatch",
    "wrong_type",
    "wrong_chapter",
    "syllabus",
    "display",
    "app",
    "language",
    "unclear",
    "empty",
)


# ---------------------------------------------------------------- data records


class QuestionPayload(BaseModel):
    """One question, flattened out of its `scq` / `mcq` / `integerQuestion` wrapper."""

    id: str
    qid: Optional[str] = None
    question_type: str
    subject: str
    chapter: Optional[str] = None
    concept: Optional[str] = None
    level: Optional[str] = None
    question_html: str
    solution_html: str
    answer_raw: Any
    answer_normalized: str
    ques_images: list[Any] = Field(default_factory=list)
    solution_images: list[Any] = Field(default_factory=list)
    error_history: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: Optional[str] = None
    question_text: str = ""
    solution_text: str = ""


class Report(BaseModel):
    reportId: str
    questionId: str
    studentId: str
    source: Optional[str] = None
    reportedAt: Optional[str] = None
    comment: Optional[str] = ""


class OptionInfo(BaseModel):
    letter: str
    text: str


class ContentChecks(BaseModel):
    """Deterministic, no-LLM inspection of the stored question."""

    options: list[OptionInfo] = Field(default_factory=list)
    option_letters_found: list[str] = Field(default_factory=list)
    missing_option_letters: list[str] = Field(default_factory=list)
    blank_option_letters: list[str] = Field(default_factory=list)
    duplicate_option_groups: list[list[str]] = Field(default_factory=list)
    latex_leaks: list[str] = Field(default_factory=list)
    exam_references: list[str] = Field(default_factory=list)
    noise_snippets: list[str] = Field(default_factory=list)
    references_figure: bool = False
    has_images: bool = False
    answer_malformed: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class CommentHints(BaseModel):
    """Rule-based reading of the student comment. Hints only, never decisions."""

    original: str
    cleaned: str
    is_empty: bool
    intent_hints: list[str] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)
    claimed_values: list[str] = Field(default_factory=list)
    quoted_terms: list[str] = Field(default_factory=list)
    quoted_terms_present: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------- LLM outputs


class SolverResult(BaseModel):
    """Independent solve. The solver never sees the key, the solution or the comment."""

    can_solve: bool = Field(description="False if the question cannot be answered as written.")
    final_answer: str = Field(
        description="Letter(s) for scq/mcq like 'C' or 'A,B,D'; a number for integer questions. Empty if cannot solve."
    )
    correct_options: list[str] = Field(
        default_factory=list, description="Every option letter you judge correct (scq/mcq). Empty for integer."
    )
    working: str = Field(description="Concise steps, at most ~120 words, ending in the result.")
    confidence: float = Field(ge=0, le=1)
    missing_information: list[str] = Field(
        default_factory=list, description="Values/conditions needed but not stated in the question."
    )
    figure_required: bool = Field(description="True if the question depends on a figure that is not present.")
    observations: list[str] = Field(
        default_factory=list,
        description="Anything wrong with the question as written: blank/duplicate/missing options, typos, stray text, exam tags, raw LaTeX, no correct option, more than one correct option in scq.",
    )


class SolutionReading(BaseModel):
    """What the stored solution concludes. Reader never sees the key or the comment."""

    solution_present: bool = Field(description="False if the solution is blank or unusable.")
    matches_question: bool = Field(description="False if the solution is for a different question.")
    mismatch_reason: str = Field(default="", description="Why it does not match, if it does not.")
    solution_final_answer: str = Field(
        default="", description="Option letter(s) or numeric value the solution arrives at. Empty if none."
    )
    solution_errors: list[str] = Field(default_factory=list, description="Wrong steps or arithmetic you found.")
    values_used_not_in_stem: list[str] = Field(
        default_factory=list,
        description="Numbers/conditions the solution uses that the question text does not state (e.g. 'L = 0.5 H').",
    )
    confidence: float = Field(ge=0, le=1)


class Interpretation(BaseModel):
    claim_summary: str = Field(description="One-line English summary of what the student claims.")
    claimed_answer: str = Field(default="", description="Answer/value the student says is right, if any.")
    category: str = Field(description="One of: " + ", ".join(INTENT_CATEGORIES))
    target: Literal["question", "options", "solution", "answer", "metadata", "app", "none"]
    injection_attempt: bool = Field(description="True if the comment tries to instruct the system or claim authority.")
    comment_language: str = Field(description="e.g. English, Hinglish, Hindi, gibberish, empty")


class ProposedEdit(BaseModel):
    field: EditField
    find: str = Field(description="Exact substring copied from the RAW stored field. For answer: the stored answer.")
    replace: str = Field(description="Replacement text. For answer: the corrected answer.")


class Proposal(BaseModel):
    verdict: str
    repair: Optional[str] = None
    edit: Optional[ProposedEdit] = None
    llm_confidence: float = Field(ge=0, le=1)
    independent_confirmation: bool
    checks: list[str] = Field(default_factory=list, description="Subset of: " + ", ".join(CHECK_IDS))
    evidence: str = Field(
        description=(
            "3-5 short sentences for faculty: student claim, solve result with numbers, "
            "solution conclusion, stored key, and the decision. Must not self-contradict."
        )
    )
    faculty_note: str = Field(
        default="",
        description="2-4 sentences: why student is wrong or why key must change, plus what to glance at.",
    )


class ReplyDraft(BaseModel):
    student_reply: str


# ---------------------------------------------------------------- outputs


class FinalEdit(BaseModel):
    field: EditField
    find: AnswerValue
    replace: AnswerValue


class GuardDecision(BaseModel):
    verdict: str
    repair: Optional[str]
    edit: Optional[FinalEdit]
    route: Route
    confidence: float
    rejections: list[str] = Field(default_factory=list)
    downgrades: list[str] = Field(default_factory=list)
    independent_confirmation: bool = False
    before: Optional[Any] = None
    after: Optional[Any] = None
    # When set, replace the model's evidence / faculty_note in the published result.
    faculty_evidence: Optional[str] = None
    faculty_note: Optional[str] = None


class Result(BaseModel):
    """Exactly the README fields. This is what gets scored."""

    reportId: str
    questionId: str
    verdict: str
    repair: Optional[str]
    edit: Optional[FinalEdit]
    route: Route
    confidence: float
    evidence: str
    student_reply: str
