import { QuestionCase } from '../types';

/** Faculty-facing label — never the Mongo ObjectId. */
export function caseLabel(c: Pick<QuestionCase, 'humanQid' | 'chapter' | 'subject'>): string {
  if (c.humanQid) return c.humanQid;
  if (c.chapter) return c.chapter;
  return c.subject || 'Question';
}
