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
  image_ids: string[];
  tech_stack: TechStack;
}

export interface WorkflowStartRequest {
  source_type: 'manual';
  input_payload: ManualInputPayload;
  mock_mode?: boolean;
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
  entity_scores?: Record<string, number>;
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
  source_references?: string[];
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
  source_references?: string[];
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
  current_stage?: string;
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

export interface GeneratedScript {
  script_id: string;
  test_case_id: string;
  scenario_id: string;
  name: string;
  source: string;
  download_path: string;
  requirement_ids: string[];
  user_story_ids: string[];
}

export interface ScriptGeneration {
  generation_id: string;
  application_url: string;
  reachable: boolean;
  page_title?: string;
  discovered_elements: Array<{ role?: string; name?: string; label?: string; test_id?: string; tag: string }>;
  scripts: GeneratedScript[];
}

export interface FailureAnalysis {
  test_case_id: string;
  failed_step?: number;
  expected_result?: string;
  actual_result?: string;
  failure_reason: string;
  /**
   * Precise categories emitted by the backend (v2+).
   * Legacy short labels kept for backwards compat with stored reports.
   */
  failure_category:
    | 'Locator Failure'
    | 'Navigation Failure'
    | 'Application Feature Missing'
    | 'Page Load Timeout'
    | 'Assertion Failure'
    | 'Environment Issue'
    // legacy
    | 'Script Generation'
    | 'Locator'
    | 'Navigation'
    | 'Application';
  page_url?: string;
  ui_element?: string;
  screenshot?: string;
  /** Path to saved DOM snapshot HTML (on failure) */
  dom_snapshot?: string;
  /** Path to saved Playwright trace .zip (on failure) */
  trace_path?: string;
  console_logs: string[];
  network_errors: string[];
  stack_trace?: string;
  skyvern_attempted: boolean;
  skyvern_succeeded: boolean;
}

export interface ExecutionReport {
  execution_id: string;
  generation_id: string;
  mode: 'automated' | 'manual';
  total_scripts: number;
  passed_scripts: number;
  failed_scripts: number;
  skipped_scripts: number;
  rejected_scripts: number;
  execution_time_seconds: number;
  success_percentage: number;
  results: Array<{
    script_id: string;
    script_name: string;
    test_case_id: string;
    scenario_id: string;
    status: 'passed' | 'failed' | 'skipped';
    duration_seconds: number;
    error_message?: string;
    failure?: FailureAnalysis;
    traceability: Record<string, unknown>;
  }>;
  rejected_results: Array<{
    test_case_id: string;
    test_case_name: string;
    status: 'rejected/unsupported';
    reason: string;
    duration_seconds: number;
    screenshot?: string;
    logs: string[];
  }>;
  overall_summary: {
    total_tests: number;
    executed_tests: number;
    passed: number;
    failed: number;
    skipped: number;
    rejected: number;
    pass_rate: number;
  };
}

export interface TraceabilityReport {
  comparison_id: string;
  execution_id: string;
  generation_id: string;
  workflow_id: string;
  total_scenarios: number;
  total_test_cases: number;
  covered: number;
  partial: number;
  missing: number;
  overall_coverage_percentage: number;
  summary: string;
  items: Array<{
    artifact_type: 'scenario' | 'test_case';
    artifact_id: string;
    title: string;
    status: 'covered' | 'partial' | 'missing';
    coverage_percentage: number;
    matched_script_ids: string[];
    matched_evidence: string[];
    gaps: string[];
  }>;
  uncovered_ui_scripts: Array<{
    script_id: string;
    page_url: string;
    reason: string;
  }>;
}
