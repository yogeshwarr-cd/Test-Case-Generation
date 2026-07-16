
'use client';

import React, { createContext, useContext, useState } from 'react';

interface WorkflowContextType {
  currentStep: number;
  setCurrentStep: React.Dispatch<React.SetStateAction<number>>;
}

const WorkflowContext = createContext<WorkflowContextType | null>(null);

export const WorkflowProvider = ({ children }: { children: React.ReactNode }) => {
  const [currentStep, setCurrentStep] = useState<number>(0);
  return (
    <WorkflowContext.Provider value={{ currentStep, setCurrentStep }}>
      {children}
    </WorkflowContext.Provider>
  );
};

export const useWorkflowContext = () => useContext(WorkflowContext);
