import type {
  ResumeRequest,
  WorkflowEvent,
  WorkflowResult,
  WorkflowStartRequest,
  WorkflowStartResponse,
} from '../types';
import { parseWorkflowEvent } from '../utils';

const BASE_URL = (process.env.NEXT_PUBLIC_TESTCASE_API_BASE_URL ?? 'http://127.0.0.1:8001').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30000);
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
