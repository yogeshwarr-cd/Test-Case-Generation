'use client';

import React from 'react';

export const AttemptTracker = ({ current, max }: { current: number; max: number }) => {
  return (
    <div className="text-xs text-slate-500">
      Regeneration Attempts: <strong className="text-slate-900">{current} / {max}</strong>
    </div>
  );
};
