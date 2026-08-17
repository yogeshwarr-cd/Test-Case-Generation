import type {
  ResumeRequest,
  WorkflowEvent,
  WorkflowResult,
  WorkflowStartRequest,
  WorkflowStartResponse,
  ScriptGeneration,
  ExecutionReport,
  ExecutionJob,
  TraceabilityComparisonReport,
  CrawlGenerationResponse,
  CrawlJob,
  CrawlAnalysis,
  WorkflowCrawlJob,
  HumanExecutionSession,
  DocumentSession,
  ParsedDocumentStory,
} from '../types';
import { parseWorkflowEvent } from '../utils';

const BASE_URL = (process.env.NEXT_PUBLIC_TESTCASE_API_BASE_URL ?? 'http://127.0.0.1:8006').replace(/\/$/, '');

export const automationArtifactUrl = (path: string) =>
  `${BASE_URL}/api/v1/automation/artifacts?path=${encodeURIComponent(path)}`;

export const automationArtifactPdfUrl = (path: string) =>
  `${BASE_URL}/api/v1/automation/artifacts/pdf?path=${encodeURIComponent(path)}`;

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
  async uploadDocument(document: File) {
    const form = new FormData();
    form.append('document', document);
    const response = await fetch(`${BASE_URL}/api/v1/documents/upload`, {
      method: 'POST',
      body: form,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(String(body.detail ?? body.message ?? `Document upload failed (${response.status})`));
    }
    return response.json() as Promise<DocumentSession>;
  },

  updateDocumentSession(sessionId: string, stories: ParsedDocumentStory[]) {
    return request<DocumentSession>(`/api/v1/documents/${sessionId}`, {
      method: 'PUT',
      body: JSON.stringify({ stories }),
    });
  },

  crawlApplication(workflowId: string, applicationUrl: string) {
    return request<CrawlAnalysis>('/api/v1/automation/scripts/crawl', {
      method: 'POST',
      body: JSON.stringify({ workflow_id: workflowId, application_url: applicationUrl }),
    }, 600000);
  },

  generateScripts(workflowId: string, applicationUrl: string, crawlId: string) {
    return request<ScriptGeneration>('/api/v1/automation/scripts/generate', {
      method: 'POST', body: JSON.stringify({
        workflow_id: workflowId, application_url: applicationUrl, crawl_id: crawlId,
      }),
    });
  },

  crawlAndGenerate(url: string, options?: {
    page_limit?: number;
    depth_limit?: number;
    max_execution_time_seconds?: number;
    testing_scope?: 'full_application' | 'specific_page';
    authentication?: any;
  }) {
    return request<CrawlGenerationResponse>('/api/v1/automation/url-crawl', {
      method: 'POST',
      body: JSON.stringify({ url, ...options }),
    }, 600000); // up to 10 min for deep crawls
  },

  executeScripts(
    generationId: string,
    mode: 'automated' | 'manual',
    authentication?: any,
    executionProfile: 'fast' | 'standard' | 'diagnostic' = 'fast',
    testingScope: 'full_application' | 'specific_page' = 'full_application',
  ) {
    return request<ExecutionReport>('/api/v1/automation/executions', {
      method: 'POST',
      body: JSON.stringify({ generation_id: generationId, mode, authentication, execution_profile: executionProfile, testing_scope: testingScope }),
    }, 1800000);
  },

  startExecutionJob(
    generationId: string,
    mode: 'automated' | 'manual',
    authentication?: any,
    executionProfile: 'fast' | 'standard' | 'diagnostic' = 'fast',
    testingScope: 'full_application' | 'specific_page' = 'full_application',
  ) {
    return request<ExecutionJob>('/api/v1/automation/executions/jobs', {
      method: 'POST',
      body: JSON.stringify({ generation_id: generationId, mode, authentication, execution_profile: executionProfile, testing_scope: testingScope }),
    });
  },

  getExecutionJob(jobId: string) {
    return request<ExecutionJob>(`/api/v1/automation/executions/jobs/${jobId}`);
  },

  startWorkflowCrawlJob(workflowId: string, applicationUrl: string, options?: {
    testing_scope?: 'full_application' | 'specific_page';
    authentication?: any;
  }) {
    return request<WorkflowCrawlJob>('/api/v1/automation/scripts/crawl/jobs', {
      method: 'POST',
      body: JSON.stringify({
        workflow_id: workflowId,
        application_url: applicationUrl,
        ...options,
      }),
    });
  },

  getWorkflowCrawlJob(jobId: string) {
    return request<WorkflowCrawlJob>(`/api/v1/automation/scripts/crawl/jobs/${jobId}`);
  },

  stopWorkflowCrawlJob(jobId: string) {
    return request<WorkflowCrawlJob>(
      `/api/v1/automation/scripts/crawl/jobs/${jobId}/stop`,
      { method: 'POST' },
    );
  },

  startCrawlJob(url: string, options?: {
    page_limit?: number;
    depth_limit?: number;
    max_execution_time_seconds?: number;
    testing_scope?: 'full_application' | 'specific_page';
    authentication?: any;
  }) {
    return request<CrawlJob>('/api/v1/automation/url-crawl/jobs', {
      method: 'POST',
      body: JSON.stringify({ url, ...options }),
    });
  },

  getCrawlJob(jobId: string) {
    return request<CrawlJob>(`/api/v1/automation/url-crawl/jobs/${jobId}`);
  },

  stopCrawlJob(jobId: string) {
    return request<CrawlJob>(`/api/v1/automation/url-crawl/jobs/${jobId}/stop`, {
      method: 'POST',
    });
  },
  startHumanExecution(payload: {
    workflow_id: string;
    scenario_id: string;
    test_case_id: string;
    application_url: string;
  }) {
    return request<HumanExecutionSession>('/api/v1/human-execution/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, 120000);
  },
  getHumanExecution(sessionId: string) {
    return request<HumanExecutionSession>(`/api/v1/human-execution/sessions/${sessionId}`);
  },
  finishHumanExecution(sessionId: string) {
    return request<HumanExecutionSession>(`/api/v1/human-execution/sessions/${sessionId}/finish`, {
      method: 'POST',
    }, 120000);
  },
  cancelHumanExecution(sessionId: string) {
    return request<HumanExecutionSession>(`/api/v1/human-execution/sessions/${sessionId}/cancel`, {
      method: 'POST',
    });
  },
  getExecutionReport(executionId: string) {
    return request<ExecutionReport>(`/api/v1/automation/executions/${executionId}`);
  },
  compareExecution(executionId: string) {
    return request<TraceabilityComparisonReport>('/api/v1/automation/executions/compare', {
      method: 'POST', body: JSON.stringify({ execution_id: executionId }),
    }, 120000);
  },

  async uploadImage(image: File, imageDescription: string, confidenceThreshold = .95) {
    const form = new FormData();form.append('image', image);form.append('confidence_threshold', String(confidenceThreshold));if (imageDescription.trim()) form.append('image_description', imageDescription.trim());
    const response = await fetch(`${BASE_URL}/api/v1/images/upload`, { method: 'POST', body: form });
    if (!response.ok) { const body = await response.json().catch(() => ({}));throw new Error(String(body.detail ?? `Image upload failed (${response.status})`)); }
    return response.json() as Promise<{ image_id: string; status: string; screen_type: string; analysis_confidence: number; confidence_threshold: number; threshold_met: boolean; warnings: string[]; cached: boolean }>;
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
