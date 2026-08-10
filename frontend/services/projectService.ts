import { apiClient } from './apiClient';

export interface BackendProject {
  id: string;
  name: string;
  description?: string;
  external_project_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const projectService = {
  getProjects: async (): Promise<BackendProject[]> => {
    try {
      return await apiClient.get('/api/v1/projects');
    } catch {
      return [];
    }
  },
  createProject: async (data: { name: string; description?: string }) => {
    return await apiClient.post('/api/v1/projects', data);
  },
  deleteProject: async (id: string) => {
    return await apiClient.delete ? apiClient.delete(`/api/v1/projects/${id}`) : Promise.resolve();
  },
  updateProject: async (id: string, data: { name?: string; description?: string }) => {
    try {
      return await apiClient.patch(`/api/v1/projects/${id}`, data);
    } catch {
      return null;
    }
  }
};
