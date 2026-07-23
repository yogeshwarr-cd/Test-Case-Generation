import type {
  ResumeRequest,
  WorkflowEvent,
  WorkflowResult,
  WorkflowStartRequest,
  WorkflowStartResponse,
  ScriptGeneration,
  ExecutionReport,
} from '../types';
import { parseWorkflowEvent } from '../utils';

const BASE_URL = (process.env.NEXT_PUBLIC_TESTCASE_API_BASE_URL ?? 'http://127.0.0.1:8001').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
    const text = await response.text();
    if (!response.ok) {
      let detail = text;
      try {
        const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown };
        detail = String(parsed.detail ?? parsed.message ?? text);
      } catch {}
      throw new Error(`Backend request failed (${response.status}): ${detail}`);
    }
    if (!text) return {} as T;
    return JSON.parse(text) as T;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const testCaseApi = {
  generateScripts(workflowId: string, applicationUrl: string) {
    return request<ScriptGeneration>('/api/v1/automation/scripts/generate', {
      method: 'POST', body: JSON.stringify({ workflow_id: workflowId, application_url: applicationUrl }),
    });
  },

  executeScripts(generationId: string, mode: 'automated' | 'manual') {
    return request<ExecutionReport>('/api/v1/automation/executions', {
      method: 'POST', body: JSON.stringify({ generation_id: generationId, mode }),
    }, 600000);
  },

  async uploadImage(image: File, imageDescription: string) {
    const form = new FormData();form.append('image', image);if (imageDescription.trim()) form.append('image_description', imageDescription.trim());
    const response = await fetch(`${BASE_URL}/api/v1/images/upload`, { method: 'POST', body: form });
    if (!response.ok) { const body = await response.json().catch(() => ({}));throw new Error(String(body.detail ?? `Image upload failed (${response.status})`)); }
    return response.json() as Promise<{ image_id: string; status: string; screen_type: string; analysis_confidence: number; warnings: string[]; cached: boolean }>;
  },
  startWorkflow(payload: WorkflowStartRequest) {
    return request<WorkflowStartResponse>('/api/v1/workflows/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getWorkflow(workflowId: string) {
    return request<WorkflowEvent & { workflow_id: string; project_id?: string }>(`/api/v1/workflows/${workflowId}`);
  },

  getWorkflowResult(workflowId: string) {
    return request<WorkflowResult>(`/api/v1/workflows/${workflowId}/result`);
  },

  resumeWorkflow(workflowId: string, payload: ResumeRequest) {
    return request<WorkflowEvent>(`/api/v1/workflows/${workflowId}/resume`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  cancelWorkflow(workflowId: string) {
    return request<WorkflowEvent>(`/api/v1/workflows/${workflowId}/cancel`, { method: 'POST' });
  },

  regenerateScenario(scenarioId: string, feedback: string) {
    return request<{ status: string; feedback_id: string }>(`/api/v1/scenarios/${scenarioId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ feedback }),
    });
  },

  regenerateTestCase(testCaseId: string, feedback: string) {
    return request<{ status: string; feedback_id: string }>(`/api/v1/testcases/${testCaseId}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ feedback }),
    });
  },

  regenerateWorkflowItem(workflowId: string, entityType: 'scenario' | 'testCase', entityId: string, feedback: string) {
    return request<{ status: string; result: Pick<WorkflowResult, 'scenarios' | 'scenario_validation' | 'test_cases' | 'testcase_validation'> }>(`/api/v1/workflows/${workflowId}/regenerate`, {
      method: 'POST', body: JSON.stringify({ entity_type: entityType, entity_id: entityId, feedback }),
    });
  },

  saveDecision(workflowId: string, entityType: 'scenario' | 'testCase', entityId: string, decision: 'approved' | 'rejected') {
    return request<{ status: string }>(`/api/v1/workflows/${workflowId}/decision`, {
      method: 'POST', body: JSON.stringify({ entity_type: entityType, entity_id: entityId, decision }),
    });
  },

  saveAllDecisions(workflowId: string, entityType: 'scenario' | 'testCase') {
    return request<{ status: string; count: number }>(`/api/v1/workflows/${workflowId}/decision/all`, {
      method: 'POST', body: JSON.stringify({ entity_type: entityType, decision: 'approved' }),
    });
  },

  approveManualReview(workflowId: string, stage: 'scenario_manual_review' | 'testcase_manual_review') {
    return request<WorkflowEvent>(`/api/v1/workflows/${workflowId}/review/approve`, {
      method: 'POST', body: JSON.stringify({ stage }),
    });
  },

  connectToWorkflowEvents(
    workflowId: string,
    handlers: { onEvent: (event: WorkflowEvent) => void; onError: () => void; onOpen?: () => void }
  ): () => void {
    const source = new EventSource(`${BASE_URL}/api/v1/workflows/${workflowId}/events`);
    source.onopen = () => handlers.onOpen?.();
    source.onmessage = (message) => {
      const event = parseWorkflowEvent(message.data);
      if (event) handlers.onEvent(event);
    };
    source.onerror = handlers.onError;
    return () => source.close();
  },
};
