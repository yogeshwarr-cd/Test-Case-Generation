'use client';

import React from 'react';

export const PipelineStepper = ({ steps, currentStep }: { steps: string[]; currentStep: number }) => {
  return (
    <div className="flex items-center space-x-4 text-xs font-medium">
      {steps.map((step, idx) => (
        <React.Fragment key={step}>
          <span className={idx <= currentStep ? 'text-slate-900' : 'text-slate-400'}>
            {step}
          </span>
          {idx < steps.length - 1 && <span className="text-slate-300">→</span>}
        </React.Fragment>
      ))}
    </div>
  );
};
