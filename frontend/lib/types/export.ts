export interface Export {
  id: string;
  project_id: string;
  format: 'csv' | 'pdf' | 'json';
  url: string;
  created_at: string;
}
