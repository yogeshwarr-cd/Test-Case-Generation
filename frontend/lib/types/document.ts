export interface Document {
  id: string;
  project_id: string;
  name: string;
  file_size: string;
  total_pages: number;
  uploaded_at: string;
}

export interface UploadedDocument {
  name: string;
  uploaded_at: string;
  file_size: string;
  total_pages: number;
}

export type StepStatus = 'completed' | 'processing' | 'pending';

export interface ProcessingStep {
  time: string;
  label: string;
  status: StepStatus;
}

export interface RequirementItem {
  id: string;
  text: string;
}

export interface RequirementCategory {
  id: string;
  label: string;
  items: RequirementItem[];
}

