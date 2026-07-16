'use client';

import React from 'react';
import { Gauge } from '../common/Gauge';

export const ThresholdGauge = ({ threshold, current }: { threshold: number; current: number }) => {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-500">
        <span>Confidence Target ({threshold * 100}%)</span>
        <span className={current >= threshold ? 'text-emerald-600 font-bold' : 'text-red-500 font-bold'}>
          {current * 100}%
        </span>
      </div>
      <Gauge value={current * 100} max={100} />
    </div>
  );
};
