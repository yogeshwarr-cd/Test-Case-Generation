import type { WorkflowResult } from '../types';

const scenarioIds = ['mock-scenario-checkout', 'mock-scenario-card-decline', 'mock-scenario-session-timeout'];

export const MOCK_WORKFLOW_RESULT: WorkflowResult = {
  workflow_id: 'mock-workflow-ui-preview',
  status: 'completed',
  scenarios: [
    {
      scenario_id: scenarioIds[0], title: 'Complete checkout with valid payment',
      description: 'Verify that a signed-in customer can purchase an in-stock product using a valid card and receives an order confirmation.',
      scenario_type: 'positive', priority: 'high', validation_status: 'passed',
      preconditions: ['Customer is signed in', 'Product is in stock'], test_data_requirements: ['Valid Visa card', 'Deliverable address'],
      expected_business_outcome: 'The order is created once, inventory is reserved, and confirmation is sent.',
      requirement_ids: ['REQ-CHECKOUT-01'], user_story_ids: ['US-CHECKOUT-01'], acceptance_criteria_ids: ['AC-CHECKOUT-01'],
    },
    {
      scenario_id: scenarioIds[1], title: 'Reject a declined payment card',
      description: 'Verify that checkout remains incomplete when the payment provider declines the customer card.',
      scenario_type: 'negative', priority: 'high', validation_status: 'passed',
      preconditions: ['Customer has items in the cart'], test_data_requirements: ['Declined test card'],
      expected_business_outcome: 'No order is created and the customer receives a useful payment error.',
      requirement_ids: ['REQ-CHECKOUT-02'], user_story_ids: ['US-CHECKOUT-01'], acceptance_criteria_ids: ['AC-CHECKOUT-02'],
    },
    {
      scenario_id: scenarioIds[2], title: 'Checkout after session timeout',
      description: 'Verify system behavior when the customer session expires immediately before order submission.',
      scenario_type: 'boundary', priority: 'medium', validation_status: 'needs_review',
      preconditions: ['Customer session is near expiry'], test_data_requirements: ['Expired session token'],
      expected_business_outcome: 'The customer is asked to sign in again without creating a duplicate order.',
      requirement_ids: ['REQ-SESSION-01'], user_story_ids: ['US-CHECKOUT-01'], acceptance_criteria_ids: ['AC-SESSION-01'],
    },
  ],
  scenario_validation: {
    confidence_score: 0.92, status: 'failed', entity_scores: {
      [scenarioIds[0]]: 0.96, [scenarioIds[1]]: 0.93, [scenarioIds[2]]: 0.87,
    },
    score_breakdown: { requirement_coverage: 0.95, acceptance_criteria_coverage: 0.91, traceability: 0.94, completeness: 0.9 },
    issues: [{ description: 'The session-timeout scenario needs more precise recovery-state assertions.', recommendation: 'Specify cart restoration and authentication behavior.' }],
  },
  test_cases: [
    {
      test_case_id: 'mock-case-checkout-success', scenario_id: scenarioIds[0], title: 'Place an order using a valid card',
      description: 'Confirm successful payment, order creation, stock reservation, and customer notification.', test_case_type: 'functional', priority: 'high', validation_status: 'passed', automation_candidate: true,
      preconditions: ['Customer is signed in', 'Cart contains an in-stock product'], test_data: { card: 'Visa success token', quantity: 1 },
      steps: [{ step_number: 1, action: 'Submit checkout using the valid payment token.', expected_result: 'Payment succeeds and exactly one confirmed order is created.' }],
      requirement_ids: ['REQ-CHECKOUT-01'], acceptance_criteria_ids: ['AC-CHECKOUT-01'],
    },
    {
      test_case_id: 'mock-case-declined-card', scenario_id: scenarioIds[1], title: 'Attempt checkout using a declined card',
      description: 'Confirm that a decline is handled without order creation or inventory reservation.', test_case_type: 'negative', priority: 'high', validation_status: 'passed', automation_candidate: true,
      preconditions: ['Customer has an active cart'], test_data: { card: 'Decline token' },
      steps: [{ step_number: 1, action: 'Submit checkout using the decline token.', expected_result: 'A payment error appears and no order is stored.' }],
      requirement_ids: ['REQ-CHECKOUT-02'], acceptance_criteria_ids: ['AC-CHECKOUT-02'],
    },
    {
      test_case_id: 'mock-case-timeout', scenario_id: scenarioIds[2], title: 'Submit checkout after authentication expires',
      description: 'Confirm safe recovery when authentication expires during checkout.', test_case_type: 'boundary', priority: 'medium', validation_status: 'needs_review', automation_candidate: false,
      preconditions: ['Session is expired'], test_data: { session: 'Expired token' },
      steps: [{ step_number: 1, action: 'Submit the pending checkout.', expected_result: 'The user is redirected to authentication.' }],
      requirement_ids: ['REQ-SESSION-01'], acceptance_criteria_ids: ['AC-SESSION-01'],
    },
  ],
  testcase_validation: {
    confidence_score: 0.9267, status: 'failed', entity_scores: {
      'mock-case-checkout-success': 0.98, 'mock-case-declined-card': 0.92, 'mock-case-timeout': 0.88,
    },
    score_breakdown: { scenario_coverage: 1, acceptance_criteria_coverage: 0.93, step_completeness: 0.91, expected_result_quality: 0.9 },
    issues: [{ description: 'The timeout test case does not verify cart restoration after reauthentication.', recommendation: 'Add recovery and duplicate-order assertions.' }],
  },
};
