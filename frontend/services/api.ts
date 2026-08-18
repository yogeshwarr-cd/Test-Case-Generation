import { apiClient } from './apiClient';

/**
 * Resolve the backend workflow_id for a project.
 */
function resolveWorkflowId(projectId: string): string {
  if (typeof window === 'undefined') return projectId;
  return localStorage.getItem(`wf_id_${projectId}`) || projectId;
}

export const api = {
  // ── Workflow lifecycle ──────────────────────────────────────────────────────

  getWorkflowState: async (projectId: string): Promise<any> => {
    return apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}`);
  },

  getWorkflowStatus: async (projectId: string): Promise<any> => {
    return apiClient.get(`/api/workflow/${resolveWorkflowId(projectId)}/status`);
  },

  importDocument: async (file: File): Promise<{ extracted_text: string; file_path: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.postMultipart('/api/documents/import', formData);
  },

  startWorkflow: async (
    filePath: string,
    confidenceThreshold: number,
    maxRetryAttempts: number,
    projectId: string
  ): Promise<any> => {
    return apiClient.post('/api/workflow/start', {
      workflow_id: projectId,
      file_path: filePath,
      project_id: projectId,
      confidence_threshold: confidenceThreshold,
      max_retry_attempts: maxRetryAttempts,
    });
  },
};
