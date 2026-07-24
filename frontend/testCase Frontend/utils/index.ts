import type { ManualInputPayload, TestCase, WorkflowEvent } from '../types';

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
  if (lower.includes('429') || lower.includes('rate') || lower.includes('quota')) {
    return 'The AI provider is busy or its quota has been reached. Please wait and try again.';
  }
  if (lower.includes('401') || lower.includes('403')) return 'You are not authorized to perform this action.';
  if (lower.includes('404')) return 'The workflow could not be found. It may have expired.';
  if (lower.includes('422') || lower.includes('validation')) return 'Some submitted data is invalid. Review the form and try again.';
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('failed to')) {
    return 'The Test Case Generation service is unavailable. Check the service and your connection.';
  }
  return 'The request could not be completed. Please try again.';
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
  // Temporary fixed confidence value for all UI displays.
  void score;
  return 80;
}

export function testCaseText(testCase: TestCase): string {
  const steps = (testCase.steps ?? [])
    .map((step) => `${step.step_number}. ${step.action}\n   Expected: ${step.expected_result}`)
    .join('\n');
  return [
    `${testCase.test_case_id}: ${testCase.title}`,
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
