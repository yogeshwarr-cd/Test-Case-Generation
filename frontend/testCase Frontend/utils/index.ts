import type { ManualInputPayload, TestCase, WorkflowEvent } from '../types';

type FriendlyIdKind = 'requirement' | 'userStory' | 'acceptanceCriteria' | 'scenario' | 'case' | 'script' | 'workflow' | 'execution';

const friendlyIdPrefixes: Record<FriendlyIdKind, string> = {
  requirement: 'REQ',
  userStory: 'US',
  acceptanceCriteria: 'AC',
  scenario: 'TS',
  case: 'TC',
  script: 'PW',
  workflow: 'WF',
  execution: 'EX',
};

const displayWidths: Partial<Record<FriendlyIdKind, number>> = {
  scenario: 3,
  case: 3,
  script: 3,
};

const friendlyIdRegistry: Record<FriendlyIdKind, Map<string, number>> = {
  requirement: new Map(), userStory: new Map(), acceptanceCriteria: new Map(),
  scenario: new Map(), case: new Map(), script: new Map(), workflow: new Map(), execution: new Map(),
};

/**
 * Assigns a sequential label to each unique source ID in its UI entity context.
 * This registry is presentation-only; source IDs are never changed or returned.
 */
export function friendlyId(kind: FriendlyIdKind, value?: string | null): string {
  if (!value) return '';
  const registry = friendlyIdRegistry[kind];
  let sequence = registry.get(value);
  if (sequence === undefined) {
    sequence = registry.size + 1;
    registry.set(value, sequence);
  }
  const width = displayWidths[kind];
  return `${friendlyIdPrefixes[kind]}-${width ? String(sequence).padStart(width, '0') : sequence}`;
}

/** Registers an ordered collection before rendering it in multiple views. */
export function registerFriendlyIds(kind: FriendlyIdKind, values: Array<string | null | undefined>): void {
  values.forEach((value) => friendlyId(kind, value));
}

/** Test-only reset; production code has no path that mutates source IDs. */
export function resetFriendlyIdRegistry(): void {
  Object.values(friendlyIdRegistry).forEach((registry) => registry.clear());
}

export function friendlyIdList(kind: FriendlyIdKind, values?: string[] | null): string | undefined {
  return values?.map((value) => friendlyId(kind, value)).join(', ');
}

export function cleanPayload(payload: ManualInputPayload): ManualInputPayload {
  const cleanList = (items: string[]) => items.map((item) => item.trim()).filter(Boolean);
  return {
    user_stories: cleanList(payload.user_stories),
    acceptance_criteria: cleanList(payload.acceptance_criteria),
    functional_requirements: cleanList(payload.functional_requirements),
    non_functional_requirements: cleanList(payload.non_functional_requirements),
    epics: cleanList(payload.epics),
    features: cleanList(payload.features),
    business_rules: cleanList(payload.business_rules),
    dependencies: cleanList(payload.dependencies),
    constraints: cleanList(payload.constraints),
    image_ids: payload.image_ids,
    tech_stack: Object.fromEntries(
      Object.entries(payload.tech_stack).map(([key, value]) => [key, value.trim()])
    ) as ManualInputPayload['tech_stack'],
  };
}

export function friendlyError(error: unknown): string {
  const message = error instanceof Error ? error.message : 'An unexpected error occurred.';
  const lower = message.toLowerCase();
  if (lower.includes('abort') || lower.includes('timeout') || lower.includes('timed out')) {
    return 'The Playwright suite exceeded the execution window. The run was not restarted. Reduce the suite size or try again when the target application is responding faster.';
  }
  if (lower.includes('429') || lower.includes('rate') || lower.includes('quota')) {
    return 'The AI provider is busy or its quota has been reached. Please wait and try again.';
  }
  if (lower.includes('401') || lower.includes('403')) return 'You are not authorized to perform this action.';
  if (lower.includes('404')) return 'The workflow could not be found. It may have expired.';
  if (lower.includes('422') || lower.includes('validation')) return 'Some submitted data is invalid. Review the form and try again.';
  if (lower.includes('backend request failed (400):')) {
    return message.split('Backend request failed (400):', 2)[1]?.trim() || message;
  }
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('failed to')) {
    return 'The Test Case Generation service is unavailable. Check the service and your connection.';
  }
  return message || 'The request could not be completed. Please try again.';
}

export function parseWorkflowEvent(raw: string): WorkflowEvent | null {
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object') return null;
    const candidate = value as Record<string, unknown>;
    if (typeof candidate.status !== 'string' || typeof candidate.current_stage !== 'string') return null;
    return candidate as unknown as WorkflowEvent;
  } catch {
    return null;
  }
}

export function confidencePercent(score?: number): number {
  if (score === undefined || !Number.isFinite(score)) return 0;
  return Math.round(Math.max(0, Math.min(1, score)) * 100);
}

export function testCaseText(testCase: TestCase): string {
  const steps = (testCase.steps ?? [])
    .map((step) => `${step.step_number}. ${step.action}\n   Expected: ${step.expected_result}`)
    .join('\n');
  return [
    `${friendlyId('case', testCase.test_case_id)}: ${testCase.title}`,
    testCase.description,
    `Priority: ${testCase.priority ?? 'Not specified'}`,
    `Type: ${testCase.test_case_type ?? 'Not specified'}`,
    testCase.preconditions?.length ? `Preconditions: ${testCase.preconditions.join('; ')}` : '',
    steps ? `Steps:\n${steps}` : '',
  ].filter(Boolean).join('\n\n');
}

export function downloadFile(name: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}
