'use client';

import Image from 'next/image';
import Link from 'next/link';
import { FlaskConical, Home } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';

export function FeatureShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3" aria-label="BA Accelerator home">
            <Image src="/images_and_videos/logo.png" alt="BA Accelerator" width={120} height={32} className="h-7 w-auto dark:invert dark:brightness-200" />
            <span className="hidden h-6 w-px bg-border sm:block" />
            <span className="hidden items-center gap-2 text-sm font-semibold sm:flex">
              <FlaskConical className="h-4 w-4 text-primary" /> Test Case Generation
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/" className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm font-medium hover:bg-muted">
              <Home className="h-4 w-4" /><span className="hidden sm:inline">Home</span>
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:py-8">{children}</main>
    </div>
  );
}
