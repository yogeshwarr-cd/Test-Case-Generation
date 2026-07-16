'use client';

import React from 'react';

export const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => {
  return (
    <div className={`bg-white rounded-xl p-6 border border-slate-200 shadow-sm ${className}`}>
      {children}
    </div>
  );
};
