'use client';

import React from 'react';

export const Gauge = ({ value, max = 100 }: { value: number; max?: number }) => {
  const percent = Math.min((value / max) * 100, 100);
  return (
    <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
      <div 
        className="bg-slate-900 h-full transition-all duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
};
