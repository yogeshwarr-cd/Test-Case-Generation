'use client';

import React from 'react';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { TopNav } from '@/components/common/TopNav';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-foreground">
      <TopNav />
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar Nav */}
        <Sidebar />

        {/* Main workspace view area */}
        <main className="flex-1 flex flex-col h-full overflow-y-auto relative bg-background">
          {children}
        </main>
      </div>
    </div>
  );
}
