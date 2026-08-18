'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
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
    const handleEscape = (event: KeyboardEvent) => event.key === 'Escape' && setIsDropdownOpen(false);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    router.push('/');
  };

  return (
    <header className="sticky top-0 z-20 flex min-h-14 shrink-0 items-center justify-between gap-2 border-b border-border bg-background/95 px-3 backdrop-blur sm:px-4">
      {/* Left: Logo */}
      <div className="flex items-center gap-2">
        <Link href="/dashboard" className="flex items-center">
          <Image src="/images_and_videos/logo.png" alt="Test Case Generator" width={112} height={30} priority className="h-6 w-auto object-contain dark:invert dark:brightness-200" />
        </Link>
      </div>

      {/* Center: Search & Autosave */}
      <div className="flex min-w-0 max-w-xl flex-1 items-center justify-center gap-4 px-1 sm:px-4">
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
            placeholder="Search scenarios, test cases, or IDs..."
            aria-label="Search scenarios, test cases, or IDs"
          />
        </div>
      </div>

      {/* Right: Theme & Profile */}
      <div className="flex items-center gap-2 relative" ref={dropdownRef}>
        <ThemeToggle />
        <div className="relative">
          <button 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-muted text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="User Profile"
            aria-haspopup="menu"
            aria-expanded={isDropdownOpen}
          >
            <User className="w-3.5 h-3.5" />
          </button>
          
          {isDropdownOpen && (
            <div role="menu" className="absolute right-0 z-50 mt-2 w-48 rounded-lg border border-border bg-card py-1.5 shadow-lg">
              <div className="px-3 py-2 border-b border-border">
                <p className="font-semibold text-foreground text-xs leading-none">Jane Smith</p>
                <p className="text-[10px] text-muted-foreground mt-1 leading-none">QA Lead</p>
              </div>
              <button 
                type="button"
                onClick={handleLogout}
                role="menuitem"
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
