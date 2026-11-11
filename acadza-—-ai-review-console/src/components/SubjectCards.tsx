import React from 'react';
import { useApp } from '../context/AppContext';
import { Subject } from '../types';
import { Atom, Leaf, Bug } from 'lucide-react';

interface SubjectInfo {
  id: Subject;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const SUBJECTS: SubjectInfo[] = [
  { id: 'Physics', label: 'Physics', icon: Atom },
  { id: 'Botany', label: 'Botany', icon: Leaf },
  { id: 'Zoology', label: 'Zoology', icon: Bug },
];

export const SubjectCards: React.FC = () => {
  const { cases, activeSubjectFilter, setActiveSubjectFilter } = useApp();

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white tracking-tight">
            Subject workspaces
          </h2>
          {activeSubjectFilter !== 'All' && (
            <button
              onClick={() => setActiveSubjectFilter('All')}
              className="text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-white underline font-medium"
            >
              Reset to all
            </button>
          )}
        </div>
        <div className="text-xs text-neutral-500 font-mono">
          <span className="font-semibold text-neutral-800 dark:text-neutral-200">{cases.length}</span>{' '}
          reported questions
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        {SUBJECTS.map((sub) => {
          const Icon = sub.icon;
          const isSelected = activeSubjectFilter === sub.id;
          const subjectCases = cases.filter((c) => c.subject === sub.id);
          const needsReview = subjectCases.filter(
            (c) => c.aiRoute === 'faculty_review' && c.workflowStatus === 'pending'
          ).length;

          return (
            <button
              key={sub.id}
              onClick={() => {
                if (isSelected) setActiveSubjectFilter('All');
                else setActiveSubjectFilter(sub.id);
              }}
              className={`flex flex-col items-center justify-center p-3.5 sm:p-4 rounded-xl border transition-all text-center ${
                isSelected
                  ? 'bg-neutral-900 dark:bg-white text-white dark:text-black border-neutral-900 dark:border-white shadow-sm ring-1 ring-neutral-400'
                  : 'bg-white dark:bg-neutral-950 text-neutral-800 dark:text-neutral-200 border-neutral-200 dark:border-neutral-800/80 hover:border-neutral-300 dark:hover:border-neutral-700'
              }`}
            >
              <div className="mb-1.5">
                <Icon
                  className={`w-5 h-5 ${isSelected ? 'text-white dark:text-black' : 'text-neutral-500 dark:text-neutral-400'}`}
                />
              </div>
              <span className="text-xs sm:text-sm font-semibold tracking-tight">{sub.label}</span>
              <div className="flex items-center gap-1.5 mt-1 text-[11px] font-mono opacity-80">
                <span>{subjectCases.length} cases</span>
                {needsReview > 0 && (
                  <span
                    className={`px-1 rounded text-[10px] font-bold ${isSelected ? 'bg-amber-400 text-black' : 'text-amber-500'}`}
                  >
                    • {needsReview}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
