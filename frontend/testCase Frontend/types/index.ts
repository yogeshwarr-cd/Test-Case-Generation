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
  intelligence?: FailureIntelligence;
}

export interface RequirementMapping {
  epic: Array<{ id: string; title: string }>;
  feature: Array<{ id: string; title: string }>;
  user_story: Array<{ id: string; title: string }>;
  acceptance_criteria: Array<{ id: string; title: string }>;
  scenario: Array<{ id: string; title: string }>;
  test_case: Array<{ id: string; title: string }>;
  requirement_ids: string[];
}

export interface DeveloperImplementationPlan {
  ticket_title: string;
  feature_affected: string;
  user_story_reference: string[];
  test_scenario_reference: string;
  test_case_reference: string;
  problem_summary: string;
  missing_functionality: string;
  root_cause_analysis: string;
  expected_behavior: string;
  actual_behavior: string;
  ui_changes_required: string[];
  backend_api_changes_required: string[];
  database_changes: string[];
  validation_rules: string[];
  acceptance_criteria_to_satisfy: string[];
  suggested_implementation_steps: string[];
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  estimated_development_effort: string;
  jira_description: string;
}

export interface FailureIntelligence {
  root_cause_category:
    | 'Missing application functionality'
    | 'Incorrect business logic'
    | 'UI implementation issue'
    | 'Locator or automation issue'
    | 'Requirement mismatch'
    | 'Navigation problem'
    | 'Validation issue'
    | 'API/Backend failure'
    | 'Environment or configuration issue';
  confidence: number;
  is_application_issue: boolean;
  deviation_step: Record<string, unknown>;
  requirement_mapping: RequirementMapping;
  root_cause_analysis: string;
  expected_behavior: string;
  actual_behavior: string;
  evidence: {
    screenshot?: string;
    dom_snapshot?: string;
    playwright_trace?: string;
    failed_locator?: string;
    page_url?: string;
    console_findings: string[];
    network_findings: string[];
    evidence_summary: string[];
  };
  developer_implementation_plan?: DeveloperImplementationPlan;
  automation_recommendation?: {
    script_changes: string[];
    locator_strategy: string[];
    wait_strategy: string[];
    assertion_strategy: string[];
    navigation_strategy: string[];
  };
  acceptance_criteria_checklist: Array<{ id: string; criterion: string; satisfied: boolean; verification: string }>;
  recommended_fix: string[];
  retest_strategy: {
    reuse_generation_id: boolean;
    original_script_id: string;
    steps: string[];
    verification_scope: string[];
    acceptance_criteria_checklist: Array<Record<string, unknown>>;
  };
}

export interface DeveloperExecutionReport {
  issue_title: string;
  affected_feature_user_story: {
    feature: string;
    user_stories: string[];
  };
  problem_description: string;
  expected_vs_actual_application_behavior: {
    expected: string;
    actual: string;
  };
  missing_functionality: string;
  developer_implementation_requirements: {
    ui: string[];
    backend_api: string[];
    validation: string[];
    database: string[];
  };
  acceptance_criteria: Array<{ id: string; title: string }>;
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
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
    application_failures?: number;
    automation_failures?: number;
    verified_fixes?: number;
  };
  requirement_coverage: {
    total_mapped_requirements: number;
    executed_requirement_references: string[];
    failed_requirement_references: string[];
    covered_percentage: number;
  };
  failed_requirement_mapping: Array<Record<string, unknown>>;
  developer_ready_tickets: DeveloperImplementationPlan[];
  developer_execution_reports: DeveloperExecutionReport[];
  retest_verification: Array<{ script_id: string; previous_status: string; current_status: string; verified: boolean; message: string }>;
}
