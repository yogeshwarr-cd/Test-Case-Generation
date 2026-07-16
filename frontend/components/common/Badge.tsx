'use client';

import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'active' | 'processing' | 'completed' | 'pending' | 'warning' | 'danger';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'pending', className = '' }) => {
  const styles = {
    active: 'bg-zinc-800 text-white border-zinc-700 font-semibold',
    processing: 'bg-zinc-100 text-zinc-800 border-zinc-300 font-medium animate-pulse',
    completed: 'bg-zinc-50 text-zinc-500 border-zinc-200 font-normal',
    pending: 'bg-transparent text-zinc-400 border-zinc-200 font-normal',
    warning: 'bg-zinc-100 text-zinc-700 border-zinc-300 font-normal',
    danger: 'bg-zinc-950 text-red-500 border-red-500/20 font-semibold'
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[variant]} ${className}`}>
      {children}
    </span>
  );
};
