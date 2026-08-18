import { friendlyId, registerFriendlyIds, resetFriendlyIdRegistry, setActiveProjectId } from './index';

function expectEqual(actual: string, expected: string): void {
  if (actual !== expected) throw new Error(`Expected ${expected}, received ${actual}`);
}

console.log('Running friendlyId unit and regression tests...');

// 1. Single Project Baseline
resetFriendlyIdRegistry();
const firstScenario = '123e4567-e89b-12d3-a456-426614174000';
const secondScenario = 'a1b2c3d4-1111-2222-3333-444455556666';
registerFriendlyIds('scenario', [firstScenario, secondScenario]);
expectEqual(friendlyId('scenario', firstScenario), 'TS-001');
expectEqual(friendlyId('scenario', secondScenario), 'TS-002');
expectEqual(friendlyId('scenario', firstScenario), 'TS-001');
expectEqual(friendlyId('case', 'b2c3d4e5-7777-8888-9999-aaaabbbbcccc'), 'TC-001');
expectEqual(friendlyId('script', 'non-standard-script-id'), 'PW-001');

// 2. Multi-Project Scope Isolation Regression Tests (Requirement 8)
resetFriendlyIdRegistry();

// Project A Setup
const projectA = 'wf_project_alpha';
setActiveProjectId(projectA);

const scenA1 = 'scen-a1-uuid';
const scenA2 = 'scen-a2-uuid';
const caseA1 = 'case-a1-uuid';
const caseA2 = 'case-a2-uuid';
const storyA1 = 'story-a1-uuid';
const scriptA1 = 'script-a1-uuid';

registerFriendlyIds('userStory', [storyA1], projectA);
registerFriendlyIds('scenario', [scenA1, scenA2], projectA);
registerFriendlyIds('case', [caseA1, caseA2], projectA);
registerFriendlyIds('script', [scriptA1], projectA);

// Assert Project A IDs start at TS-001 / TC-001
expectEqual(friendlyId('userStory', storyA1, projectA), 'US-1');
expectEqual(friendlyId('scenario', scenA1, projectA), 'TS-001');
expectEqual(friendlyId('scenario', scenA2, projectA), 'TS-002');
expectEqual(friendlyId('case', caseA1, projectA), 'TC-001');
expectEqual(friendlyId('case', caseA2, projectA), 'TC-002');
expectEqual(friendlyId('script', scriptA1, projectA), 'PW-001');

// Project B Setup (A completely new project)
const projectB = 'wf_project_beta';
setActiveProjectId(projectB);

const scenB1 = 'scen-b1-uuid';
const scenB2 = 'scen-b2-uuid';
const caseB1 = 'case-b1-uuid';
const caseB2 = 'case-b2-uuid';
const storyB1 = 'story-b1-uuid';
const scriptB1 = 'script-b1-uuid';

registerFriendlyIds('userStory', [storyB1], projectB);
registerFriendlyIds('scenario', [scenB1, scenB2], projectB);
registerFriendlyIds('case', [caseB1, caseB2], projectB);
registerFriendlyIds('script', [scriptB1], projectB);

// Assert Project B starts AGAIN at TS-001 / TC-001 (Requirement 1, 2, 3)
expectEqual(friendlyId('userStory', storyB1, projectB), 'US-1');
expectEqual(friendlyId('scenario', scenB1, projectB), 'TS-001');
expectEqual(friendlyId('scenario', scenB2, projectB), 'TS-002');
expectEqual(friendlyId('case', caseB1, projectB), 'TC-001');
expectEqual(friendlyId('case', caseB2, projectB), 'TC-002');
expectEqual(friendlyId('script', scriptB1, projectB), 'PW-001');

// Navigating back to Project A (Requirement 5: Stability across workflow/navigation)
setActiveProjectId(projectA);
expectEqual(friendlyId('userStory', storyA1, projectA), 'US-1');
expectEqual(friendlyId('scenario', scenA1, projectA), 'TS-001');
expectEqual(friendlyId('scenario', scenA2, projectA), 'TS-002');
expectEqual(friendlyId('case', caseA1, projectA), 'TC-001');
expectEqual(friendlyId('case', caseA2, projectA), 'TC-002');
expectEqual(friendlyId('script', scriptA1, projectA), 'PW-001');

// Traceability check (Requirement 4: US -> TS -> TC -> PW traceability intact)
const traceabilityA = `${friendlyId('userStory', storyA1)} -> ${friendlyId('scenario', scenA1)} -> ${friendlyId('case', caseA1)} -> ${friendlyId('script', scriptA1)}`;
expectEqual(traceabilityA, 'US-1 -> TS-001 -> TC-001 -> PW-001');

setActiveProjectId(projectB);
const traceabilityB = `${friendlyId('userStory', storyB1)} -> ${friendlyId('scenario', scenB1)} -> ${friendlyId('case', caseB1)} -> ${friendlyId('script', scriptB1)}`;
expectEqual(traceabilityB, 'US-1 -> TS-001 -> TC-001 -> PW-001');

console.log('All friendlyId unit and regression tests passed successfully!');
