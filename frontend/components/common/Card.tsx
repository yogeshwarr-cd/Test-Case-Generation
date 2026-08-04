'use client';

import React from 'react';

export const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => {
  return (
    <div className={`rounded-xl border border-border bg-card p-4 text-card-foreground shadow-sm sm:p-6 ${className}`}>
      {children}
    </div>
  );
};
