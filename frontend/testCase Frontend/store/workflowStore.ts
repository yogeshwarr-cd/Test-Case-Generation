'use client';

import { create } from 'zustand';
import type { ExecutionReport, ScriptGeneration, TraceabilityComparisonReport, WorkflowEvent, WorkflowResult } from '../types';
import { WORKFLOW_SNAPSHOT_KEY, WORKFLOW_STORAGE_KEY } from '../constants';

interface WorkflowStore {
  workflowId: string | null;
  projectId: string | null;
  snapshot: WorkflowEvent | null;
  result: WorkflowResult | null;
  projects: TestProjectRecord[];
  setWorkflow: (workflowId: string, projectId?: string | null) => void;
  setSnapshot: (snapshot: WorkflowEvent) => void;
  setResult: (result: WorkflowResult | null) => void;
  deleteProject: (workflowId: string) => void;
  hydrate: () => void;
  clear: () => void;
}

export interface TestProjectRecord {
  workflowId: string;
  projectId: string | null;
  name: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  scenarioCount: number;
  testCaseCount: number;
  scriptCount: number;
  execution?: { executionId: string; passed: number; failed: number; total: number; successPercentage: number };
}

const PROJECTS_KEY = 'testcase-project-history';
const artifactsKey = (workflowId: string) => `testcase-project-artifacts:${workflowId}`;
const readProjects = (): TestProjectRecord[] => {
  try { return JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? '[]') as TestProjectRecord[]; } catch { return []; }
};
const saveProjects = (projects: TestProjectRecord[]) => localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));

export interface SavedTestProjectArtifacts { generation?: ScriptGeneration; report?: ExecutionReport; comparison?: TraceabilityComparisonReport }
export function loadTestProjectArtifacts(workflowId: string): SavedTestProjectArtifacts | null {
  try { return JSON.parse(localStorage.getItem(artifactsKey(workflowId)) ?? 'null') as SavedTestProjectArtifacts | null; } catch { return null; }
}

export function saveTestProjectArtifacts(workflowId: string, generation?: ScriptGeneration | null, report?: ExecutionReport | null, comparison?: TraceabilityComparisonReport | null) {
  const projects = readProjects();
  const index = projects.findIndex((item) => item.workflowId === workflowId);
  if (index < 0) return;
  projects[index] = {
    ...projects[index], updatedAt: new Date().toISOString(),
    scriptCount: generation?.scripts.length ?? projects[index].scriptCount,
    execution: report ? { executionId: report.execution_id, passed: report.passed_scripts, failed: report.failed_scripts, total: report.total_scripts, successPercentage: report.success_percentage } : projects[index].execution,
  };
  saveProjects(projects);
  try {
    const saved = loadTestProjectArtifacts(workflowId) ?? {};
    localStorage.setItem(artifactsKey(workflowId), JSON.stringify({ generation: generation ?? saved.generation, report: report ?? saved.report, comparison: comparison ?? saved.comparison }));
  } catch {
    // Keep the lightweight project summary when browser storage is full.
  }
}

export const useTestCaseWorkflowStore = create<WorkflowStore>((set) => ({
  workflowId: null,
  projectId: null,
  snapshot: null,
  result: null,
  projects: [],
  setWorkflow: (workflowId, projectId = null) => {
    sessionStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify({ workflowId, projectId }));
    const projects = readProjects();
    if (!projects.some((item) => item.workflowId === workflowId)) {
      const now = new Date().toISOString();
      projects.unshift({ workflowId, projectId, name: `Test project ${String(projectId || workflowId).slice(0, 8)}`, status: 'processing', createdAt: now, updatedAt: now, scenarioCount: 0, testCaseCount: 0, scriptCount: 0 });
      saveProjects(projects);
    }
    set({ workflowId, projectId, projects });
  },
  setSnapshot: (snapshot) => {
    sessionStorage.setItem(WORKFLOW_SNAPSHOT_KEY, JSON.stringify(snapshot));
    set({ snapshot });
  },
  setResult: (result) => {
    const projects = readProjects();
    if (result) {
      const index = projects.findIndex((item) => item.workflowId === result.workflow_id);
      if (index >= 0) projects[index] = { ...projects[index], status: result.status, updatedAt: new Date().toISOString(), scenarioCount: result.scenarios.length, testCaseCount: result.test_cases.length };
      saveProjects(projects);
    }
    set({ result, projects });
  },
  deleteProject: (workflowId) => {
    const projects = readProjects().filter((item) => item.workflowId !== workflowId);
    saveProjects(projects);
    localStorage.removeItem(artifactsKey(workflowId));
    try {
      const active = JSON.parse(sessionStorage.getItem(WORKFLOW_STORAGE_KEY) ?? 'null') as { workflowId?: string } | null;
      if (active?.workflowId === workflowId) {
        sessionStorage.removeItem(WORKFLOW_STORAGE_KEY);
        sessionStorage.removeItem(WORKFLOW_SNAPSHOT_KEY);
      }
    } catch {
      sessionStorage.removeItem(WORKFLOW_STORAGE_KEY);
      sessionStorage.removeItem(WORKFLOW_SNAPSHOT_KEY);
    }
    set((state) => state.workflowId === workflowId
      ? { projects, workflowId: null, projectId: null, snapshot: null, result: null }
      : { projects });
  },
  hydrate: () => {
    try {
      const active = JSON.parse(sessionStorage.getItem(WORKFLOW_STORAGE_KEY) ?? 'null') as {
        workflowId?: string;
        projectId?: string;
      } | null;
      const snapshot = JSON.parse(sessionStorage.getItem(WORKFLOW_SNAPSHOT_KEY) ?? 'null') as WorkflowEvent | null;
      const projects = readProjects();
      if (active?.workflowId && !projects.some((item) => item.workflowId === active.workflowId)) {
        const now = new Date().toISOString();
        projects.unshift({ workflowId: active.workflowId, projectId: active.projectId ?? null, name: `Test project ${String(active.projectId || active.workflowId).slice(0, 8)}`, status: snapshot?.status || 'processing', createdAt: now, updatedAt: now, scenarioCount: 0, testCaseCount: 0, scriptCount: 0 });
        saveProjects(projects);
      }
      set({ workflowId: active?.workflowId ?? null, projectId: active?.projectId ?? null, snapshot, projects });
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
