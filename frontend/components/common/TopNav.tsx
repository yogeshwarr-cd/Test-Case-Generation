'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Search, User, LogOut } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { AutosaveIndicator, AutosaveState } from './AutosaveIndicator';

interface TopNavProps {
  autosaveState?: AutosaveState;
}

export function TopNav({ autosaveState }: TopNavProps) {
  const router = useRouter();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    router.push('/');
  };

  return (
    <header className="h-[56px] border-b border-border bg-background flex items-center justify-between px-4 shrink-0 z-10 sticky top-0">
      {/* Left: Logo */}
      <div className="flex items-center gap-2">
        <Link href="/dashboard" className="flex items-center">
          <img src="/images_and_videos/logo.png" alt="BA Accelerator" className="h-6 object-contain" />
        </Link>
      </div>

      {/* Center: Search & Autosave */}
      <div className="flex-1 flex items-center justify-center max-w-xl px-4 gap-4">
        {autosaveState && (
          <div className="hidden md:flex">
             <AutosaveIndicator state={autosaveState} />
          </div>
        )}
        <div className="relative w-full max-w-md">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <input
            type="text"
            className="block w-full pl-9 pr-3 h-[32px] border border-border rounded-md leading-5 bg-muted/50 text-foreground placeholder-muted-foreground focus:outline-none focus:bg-background focus:ring-1 focus:ring-primary focus:border-primary text-[13px] transition-colors"
            placeholder="Search stories, summaries, or IDs..."
          />
        </div>
      </div>

      {/* Right: Theme & Profile */}
      <div className="flex items-center gap-2 relative" ref={dropdownRef}>
        <ThemeToggle />
        <div className="relative">
          <button 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="w-7 h-7 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors border border-border cursor-pointer focus:outline-none"
            aria-label="User Profile"
          >
            <User className="w-3.5 h-3.5" />
          </button>
          
          {isDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-lg shadow-lg py-1.5 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
              <div className="px-3 py-2 border-b border-border">
                <p className="font-semibold text-foreground text-xs leading-none">Jane Smith</p>
                <p className="text-[10px] text-muted-foreground mt-1 leading-none">Business Analyst</p>
              </div>
              <button 
                onClick={handleLogout}
                className="w-full text-left px-3 py-2 text-xs text-red-500 hover:bg-red-500/10 transition-colors flex items-center gap-2 font-medium cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
