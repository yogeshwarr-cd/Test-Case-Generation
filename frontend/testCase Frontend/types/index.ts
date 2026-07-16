export type WorkflowStatus =
  | 'pending'
  | 'preparing_context'
  | 'generating_scenarios'
  | 'validating_scenarios'
  | 'scenario_manual_review'
  | 'generating_test_cases'
  | 'validating_test_cases'
  | 'testcase_manual_review'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface TechStack {
  frontend: string;
  backend: string;
  database: string;
  testing: string;
  other: string;
}

export interface ManualInputPayload {
  user_stories: string[];
  acceptance_criteria: string[];
  functional_requirements: string[];
  non_functional_requirements: string[];
  epics: string[];
  features: string[];
  business_rules: string[];
  dependencies: string[];
  constraints: string[];
  tech_stack: TechStack;
}

export interface WorkflowStartRequest {
  source_type: 'manual';
  input_payload: ManualInputPayload;
}

export interface WorkflowStartResponse {
  workflow_id: string;
  project_id: string;
  status: WorkflowStatus;
  message?: string;
}

export interface ValidationIssue {
  issue_code?: string;
  severity?: string;
  description: string;
  affected_entity_id?: string | null;
  recommendation?: string | null;
}

export interface ValidationResult {
  confidence_score?: number;
  score_breakdown?: Record<string, number>;
  status?: string;
  issues?: ValidationIssue[];
  failed_entity_ids?: string[];
  regeneration_instructions?: string[];
}

export interface Scenario {
  scenario_id: string;
  title: string;
  description: string;
  scenario_type?: string;
  priority?: string;
  preconditions?: string[];
  test_data_requirements?: string[];
  expected_business_outcome?: string;
  requirement_ids?: string[];
  feature_ids?: string[];
  user_story_ids?: string[];
  acceptance_criteria_ids?: string[];
  confidence_score?: number;
  validation_status?: string;
}

export interface TestStep {
  step_number: number;
  action: string;
  expected_result: string;
}

export interface TestCase {
  test_case_id: string;
  scenario_id: string;
  title: string;
  description: string;
  test_case_type?: string;
  priority?: string;
  preconditions?: string[];
  test_data?: Record<string, unknown>;
  steps?: TestStep[];
  postconditions?: string[];
  requirement_ids?: string[];
  acceptance_criteria_ids?: string[];
  automation_candidate?: boolean;
  confidence_score?: number;
  validation_status?: string;
}

export interface StructuredContext {
  epics?: unknown[];
  features?: unknown[];
  user_stories?: unknown[];
  acceptance_criteria?: unknown[];
  requirements?: unknown[];
  traceability_map?: unknown;
  [key: string]: unknown;
}

export interface WorkflowEvent {
  status: WorkflowStatus;
  current_stage: string;
  progress_percentage?: number;
  message?: string;
  confidence_score?: number;
  scenario_attempt_count?: number;
  testcase_attempt_count?: number;
  errors?: string[];
}

export interface WorkflowResult {
  workflow_id: string;
  status: WorkflowStatus;
  structured_context?: StructuredContext | null;
  scenarios: Scenario[];
  scenario_validation?: ValidationResult | null;
  test_cases: TestCase[];
  testcase_validation?: ValidationResult | null;
  manual_intervention_reason?: string;
}

export interface ResumeRequest {
  stage: 'scenario_manual_review' | 'testcase_manual_review';
  feedback: string;
  corrected_data: Record<string, unknown>;
}

export interface ResultFilters {
  search: string;
  priority: string;
  testType: string;
  validationStatus: string;
  requirement: string;
  minConfidence: number;
}
