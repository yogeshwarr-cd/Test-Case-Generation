'use client';

import { create } from 'zustand';
import type { WorkflowEvent, WorkflowResult } from '../types';
import { WORKFLOW_SNAPSHOT_KEY, WORKFLOW_STORAGE_KEY } from '../constants';

interface WorkflowStore {
  workflowId: string | null;
  projectId: string | null;
  snapshot: WorkflowEvent | null;
  result: WorkflowResult | null;
  setWorkflow: (workflowId: string, projectId?: string | null) => void;
  setSnapshot: (snapshot: WorkflowEvent) => void;
  setResult: (result: WorkflowResult | null) => void;
  hydrate: () => void;
  clear: () => void;
}

export const useTestCaseWorkflowStore = create<WorkflowStore>((set) => ({
  workflowId: null,
  projectId: null,
  snapshot: null,
  result: null,
  setWorkflow: (workflowId, projectId = null) => {
    sessionStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify({ workflowId, projectId }));
    set({ workflowId, projectId });
  },
  setSnapshot: (snapshot) => {
    sessionStorage.setItem(WORKFLOW_SNAPSHOT_KEY, JSON.stringify(snapshot));
    set({ snapshot });
  },
  setResult: (result) => set({ result }),
  hydrate: () => {
    try {
      const active = JSON.parse(sessionStorage.getItem(WORKFLOW_STORAGE_KEY) ?? 'null') as {
        workflowId?: string;
        projectId?: string;
      } | null;
      const snapshot = JSON.parse(sessionStorage.getItem(WORKFLOW_SNAPSHOT_KEY) ?? 'null') as WorkflowEvent | null;
      set({ workflowId: active?.workflowId ?? null, projectId: active?.projectId ?? null, snapshot });
    } catch {
      sessionStorage.removeItem(WORKFLOW_STORAGE_KEY);
      sessionStorage.removeItem(WORKFLOW_SNAPSHOT_KEY);
    }
  },
  clear: () => {
    sessionStorage.removeItem(WORKFLOW_STORAGE_KEY);
    sessionStorage.removeItem(WORKFLOW_SNAPSHOT_KEY);
    set({ workflowId: null, projectId: null, snapshot: null, result: null });
  },
}));
