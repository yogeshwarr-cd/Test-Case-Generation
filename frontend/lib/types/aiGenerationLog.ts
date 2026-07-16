export interface AIGenerationLog {
  id: string;
  project_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  model: string;
  created_at: string;
}
