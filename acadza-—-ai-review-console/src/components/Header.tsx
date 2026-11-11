import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { FACULTY_PROFILES } from '../data/faculty';
import {
  Search,
  Moon,
  Sun,
  Download,
  Cpu,
  ChevronDown,
  Check,
  RefreshCw,
  X,
} from 'lucide-react';

export const Header: React.FC = () => {
  const {
    theme,
    toggleTheme,
    searchQuery,
    setSearchQuery,
    currentFaculty,
    setCurrentFaculty,
    setIsTokenInspectorOpen,
    downloadResultsJson,
    resetAllCasesToDefault,
    showToast,
    runUsage,
  } = useApp();

  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard shortcut '/' to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        setIsMobileSearchOpen(true);
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const tokenK = Math.round(runUsage.totalTokens / 1000);

  return (
    <header className="sticky top-0 z-40 bg-white dark:bg-black border-b border-neutral-200 dark:border-neutral-800 transition-colors w-full">
      <div className="max-w-7xl mx-auto px-2.5 sm:px-6 lg:px-8 h-14 sm:h-16 flex items-center justify-between gap-1.5 sm:gap-4">
        {/* Brand Zone - Compact on Phone, Full on Desktop */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-neutral-900 dark:bg-white text-white dark:text-black border border-neutral-800 dark:border-neutral-200 overflow-hidden shadow-xs shrink-0">
            <img
              src="/assets/aistudio/image_adb6fece.png"
              alt="Acadza"
              className="w-full h-full object-cover scale-110"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-base sm:text-lg font-extrabold tracking-tight text-neutral-900 dark:text-white">
              Acadza
            </span>
            <span className="hidden sm:inline-block text-xs font-medium text-neutral-500 dark:text-neutral-400">
              AI Review Console
            </span>
          </div>
        </div>

        {/* Search Bar Zone (Desktop) */}
        <div className="hidden md:flex flex-1 max-w-sm mx-4">
          <div className="relative flex items-center w-full">
            <Search className="absolute left-3 w-3.5 h-3.5 text-neutral-400 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search questions, formulas... (/)"
              className="w-full h-8 pl-8 pr-7 text-xs bg-neutral-100 dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 placeholder-neutral-500 rounded-lg border border-neutral-200 dark:border-neutral-800 focus:border-neutral-400 dark:focus:border-neutral-600 focus:bg-white dark:focus:bg-black focus:outline-none transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 p-0.5 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
                title="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Action Controls Zone */}
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          {/* Mobile search toggle */}
          <button
            onClick={() => setIsMobileSearchOpen(!isMobileSearchOpen)}
            className="md:hidden p-1.5 min-h-[38px] min-w-[38px] flex items-center justify-center text-neutral-700 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors"
            title="Search"
            aria-label="Search"
          >
            <Search className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsTokenInspectorOpen(true)}
            className="flex items-center gap-1 px-2 py-1.5 min-h-[36px] text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 border border-neutral-300 dark:border-neutral-800 rounded-lg transition-colors"
            title="Inspect triage engine token usage"
          >
            <Cpu className="w-3.5 h-3.5 text-neutral-500 shrink-0" />
            <span className="hidden sm:inline text-neutral-600 dark:text-neutral-300">Tokens:</span>
            <span className="font-mono font-bold">{tokenK}k</span>
          </button>

          {/* Download results.json */}
          <button
            onClick={downloadResultsJson}
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 min-h-[36px] text-xs font-semibold text-neutral-900 dark:text-neutral-100 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 border border-neutral-300 dark:border-neutral-800 rounded-lg transition-colors"
            title="Download validated results.json matching submission format"
          >
            <Download className="w-3.5 h-3.5 text-neutral-500" />
            <span>Export</span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="p-1.5 sm:p-2 min-h-[38px] min-w-[38px] flex items-center justify-center text-neutral-700 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg transition-colors"
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Moon className="w-4 h-4 text-neutral-200" />
            ) : (
              <Sun className="w-4 h-4 text-neutral-700" />
            )}
          </button>

          {/* Faculty Profile Switcher */}
          <div className="relative shrink-0" ref={dropdownRef}>
            <button
              onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
              className="flex items-center gap-1 p-1 sm:px-2 sm:py-1 min-h-[38px] rounded-lg border border-neutral-300 dark:border-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors"
              title="Active Faculty Reviewer"
            >
              <div className="w-6 h-6 rounded-md bg-neutral-900 dark:bg-white text-white dark:text-black font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                {currentFaculty.avatarInitials}
              </div>
              <ChevronDown className="w-3 h-3 text-neutral-500 hidden sm:block" />
            </button>

            {/* Profile Dropdown */}
            {isProfileMenuOpen && (
              <div className="absolute right-0 mt-1.5 w-60 sm:w-64 bg-white dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl shadow-2xl py-1.5 z-50 text-xs">
                <div className="px-3 py-2 border-b border-neutral-100 dark:border-neutral-800">
                  <p className="text-[10px] text-neutral-400 uppercase tracking-wider font-mono font-semibold">
                    Active faculty reviewer
                  </p>
                  <p className="text-neutral-900 dark:text-white font-semibold truncate mt-0.5">
                    {currentFaculty.name}
                  </p>
                  <p className="text-[11px] text-neutral-500">
                    {currentFaculty.role}
                  </p>
                </div>

                <div className="py-1">
                  {FACULTY_PROFILES.map((fac) => (
                    <button
                      key={fac.id}
                      onClick={() => {
                        setCurrentFaculty(fac);
                        setIsProfileMenuOpen(false);
                        showToast(`Switched active reviewer to ${fac.name}`);
                      }}
                      className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-neutral-100 dark:hover:bg-neutral-900 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded bg-neutral-200 dark:bg-neutral-800 text-[10px] font-mono font-bold flex items-center justify-center text-neutral-800 dark:text-neutral-200">
                          {fac.avatarInitials}
                        </span>
                        <div>
                          <div className="font-semibold text-neutral-900 dark:text-white text-xs">
                            {fac.name}
                          </div>
                          <div className="text-[10px] text-neutral-500">
                            {fac.department}
                          </div>
                        </div>
                      </div>
                      {currentFaculty.id === fac.id && (
                        <Check className="w-3.5 h-3.5 text-neutral-900 dark:text-white" />
                      )}
                    </button>
                  ))}
                </div>

                <div className="p-1 border-t border-neutral-100 dark:border-neutral-800">
                  <button
                    onClick={() => {
                      resetAllCasesToDefault();
                      setIsProfileMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-neutral-600 dark:text-neutral-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 rounded transition-colors text-[11px]"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Reset to engine results
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Search Bar Dropdown */}
      {isMobileSearchOpen && (
        <div className="md:hidden px-3 py-2 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950">
          <div className="relative flex items-center">
            <Search className="absolute left-3 w-3.5 h-3.5 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search questions, formulas, topics..."
              className="w-full h-9 pl-9 pr-8 text-xs bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white border border-neutral-300 dark:border-neutral-800 rounded-lg focus:outline-none"
              autoFocus
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 p-1 text-neutral-400"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
