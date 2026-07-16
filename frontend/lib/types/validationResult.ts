export interface ValidationResult {
  id: string;
  entity_type: 'requirement' | 'user_story' | 'epic';
  entity_id: string;
  score: number;
  passed: boolean;
  attempt_number: number;
}
