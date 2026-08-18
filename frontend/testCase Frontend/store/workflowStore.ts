'use client';

import { create } from 'zustand';
import type { CrawlAnalysis, ExecutionReport, ScriptGeneration, TraceabilityComparisonReport, WorkflowEvent, WorkflowResult } from '../types';
import { WORKFLOW_SNAPSHOT_KEY, WORKFLOW_STORAGE_KEY } from '../constants';

import { setActiveProjectId } from '../utils';

interface WorkflowStore {
  workflowId: string | null;
  projectId: string | null;
  snapshot: WorkflowEvent | null;
  result: WorkflowResult | null;
  projects: TestProjectRecord[];
  setWorkflow: (workflowId: string, projectId?: string | null, projectName?: string) => void;
  setSnapshot: (snapshot: WorkflowEvent) => void;
  setResult: (result: WorkflowResult | null) => void;
  deleteProject: (workflowId: string) => void;
  renameProject: (workflowId: string, newName: string) => void;
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
const automationActivityKey = (workflowId: string) => `testcase-automation-activity:${workflowId}`;
const readProjects = (): TestProjectRecord[] => {
  try { return JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? '[]') as TestProjectRecord[]; } catch { return []; }
};
const saveProjects = (projects: TestProjectRecord[]) => localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));

export function loadActiveProjectName(): string {
  try {
    const active = JSON.parse(sessionStorage.getItem(WORKFLOW_STORAGE_KEY) ?? 'null') as { workflowId?: string } | null;
    if (!active?.workflowId) return '';
    return readProjects().find((project) => project.workflowId === active.workflowId)?.name ?? '';
  } catch {
    return '';
  }
}

export interface SavedTestProjectArtifacts {
  generation?: ScriptGeneration;
  crawl?: CrawlAnalysis;
  report?: ExecutionReport;
  comparison?: TraceabilityComparisonReport;
  applicationUrl?: string;
  crawlJobId?: string;
  executionJobId?: string;
  humanSessionId?: string;
}
export function loadTestProjectArtifacts(workflowId: string): SavedTestProjectArtifacts | null {
  try {
    const artifacts = JSON.parse(localStorage.getItem(artifactsKey(workflowId)) ?? 'null') as SavedTestProjectArtifacts | null;
    const activity = JSON.parse(localStorage.getItem(automationActivityKey(workflowId)) ?? 'null') as SavedTestProjectArtifacts | null;
    return artifacts || activity ? { ...(artifacts ?? {}), ...(activity ?? {}) } : null;
  } catch { return null; }
}

export function saveTestProjectArtifacts(workflowId: string, generation?: ScriptGeneration | null, report?: ExecutionReport | null, comparison?: TraceabilityComparisonReport | null, crawl?: CrawlAnalysis | null) {
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
    localStorage.setItem(artifactsKey(workflowId), JSON.stringify({ ...saved, generation: generation ?? saved.generation, report: report ?? saved.report, comparison: comparison ?? saved.comparison, crawl: crawl ?? saved.crawl }));
  } catch {
    // Keep the lightweight project summary when browser storage is full.
  }
}

export function saveAutomationActivity(
  workflowId: string,
  activity: Pick<SavedTestProjectArtifacts, 'applicationUrl' | 'crawlJobId' | 'executionJobId' | 'humanSessionId'>,
) {
  try {
    const saved = JSON.parse(localStorage.getItem(automationActivityKey(workflowId)) ?? '{}') as SavedTestProjectArtifacts;
    const next = { ...saved };
    if (activity.applicationUrl) next.applicationUrl = activity.applicationUrl;
    if (activity.crawlJobId) next.crawlJobId = activity.crawlJobId;
    if (activity.executionJobId) next.executionJobId = activity.executionJobId;
    if (activity.humanSessionId) next.humanSessionId = activity.humanSessionId;
    localStorage.setItem(automationActivityKey(workflowId), JSON.stringify(next));
  } catch {
    // Polling can still continue in the current view when storage is unavailable.
  }
}

export const useTestCaseWorkflowStore = create<WorkflowStore>((set) => ({
  workflowId: null,
  projectId: null,
  snapshot: null,
  result: null,
  projects: [],
  setWorkflow: (workflowId, projectId = null, projectName?: string) => {
    sessionStorage.setItem(WORKFLOW_STORAGE_KEY, JSON.stringify({ workflowId, projectId }));
    setActiveProjectId(workflowId);
    const projects = readProjects();
    const existingIndex = projects.findIndex((item) => item.workflowId === workflowId);
    if (existingIndex < 0) {
      const now = new Date().toISOString();
      const name = projectName && projectName.trim() ? projectName.trim() : `Test project ${String(projectId || workflowId).slice(0, 8)}`;
      projects.unshift({ workflowId, projectId, name, status: 'processing', createdAt: now, updatedAt: now, scenarioCount: 0, testCaseCount: 0, scriptCount: 0 });
      saveProjects(projects);
    } else if (projectName && projectName.trim()) {
      projects[existingIndex].name = projectName.trim();
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
  renameProject: (workflowId, newName) => {
    const projects = readProjects();
    const index = projects.findIndex((item) => item.workflowId === workflowId);
    if (index >= 0) {
      projects[index] = { ...projects[index], name: newName, updatedAt: new Date().toISOString() };
      saveProjects(projects);
    }
    set({ projects });
  },
  deleteProject: (workflowId) => {
    const projects = readProjects().filter((item) => item.workflowId !== workflowId);
    saveProjects(projects);
    localStorage.removeItem(artifactsKey(workflowId));
    localStorage.removeItem(automationActivityKey(workflowId));
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
      if (active?.workflowId) {
        setActiveProjectId(active.workflowId);
        if (!projects.some((item) => item.workflowId === active.workflowId)) {
          const now = new Date().toISOString();
          projects.unshift({ workflowId: active.workflowId, projectId: active.projectId ?? null, name: `Test project ${String(active.projectId || active.workflowId).slice(0, 8)}`, status: snapshot?.status || 'processing', createdAt: now, updatedAt: now, scenarioCount: 0, testCaseCount: 0, scriptCount: 0 });
          saveProjects(projects);
        }
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
    setActiveProjectId('default');
    set({ workflowId: null, projectId: null, snapshot: null, result: null });
  },
}));
