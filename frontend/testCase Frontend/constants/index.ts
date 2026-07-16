import type { ManualInputPayload } from '../types';

export const WORKFLOW_STORAGE_KEY = 'testcase-active-workflow';
export const WORKFLOW_SNAPSHOT_KEY = 'testcase-workflow-snapshot';

export const WORKFLOW_STAGES = [
  { key: 'preparing_context', label: 'Preparing context', optional: false },
  { key: 'generating_scenarios', label: 'Generating scenarios', optional: false },
  { key: 'validating_scenarios', label: 'Validating scenarios', optional: false },
  { key: 'scenario_regeneration', label: 'Regenerating scenarios', optional: true },
  { key: 'generating_test_cases', label: 'Generating test cases', optional: false },
  { key: 'validating_test_cases', label: 'Validating test cases', optional: false },
  { key: 'testcase_regeneration', label: 'Regenerating test cases', optional: true },
  { key: 'completed', label: 'Completed', optional: false },
] as const;

export const EMPTY_PAYLOAD: ManualInputPayload = {
  user_stories: [''],
  acceptance_criteria: [''],
  functional_requirements: [''],
  non_functional_requirements: [''],
  epics: [''],
  features: [''],
  business_rules: [''],
  dependencies: [''],
  constraints: [''],
  tech_stack: { frontend: '', backend: '', database: '', testing: '', other: '' },
};

export const FIELD_LABELS: Record<Exclude<keyof ManualInputPayload, 'tech_stack'>, string> = {
  user_stories: 'User stories',
  acceptance_criteria: 'Acceptance criteria',
  functional_requirements: 'Functional requirements',
  non_functional_requirements: 'Non-functional requirements',
  epics: 'Epics',
  features: 'Features',
  business_rules: 'Business rules',
  dependencies: 'Dependencies',
  constraints: 'Constraints',
};
