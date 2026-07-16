export interface Project {
  id: string;
  name: string;
  description: string;
  confidence_threshold: number;
  max_regeneration_attempts: number;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'processing' | 'completed';
  doc_count: number;
  story_count: number;
  updated_at: string;
}

export type WorkspaceStatus = Workspace['status'];

