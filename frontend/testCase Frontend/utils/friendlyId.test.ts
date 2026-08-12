import { friendlyId, registerFriendlyIds, resetFriendlyIdRegistry } from './index';

function expectEqual(actual: string, expected: string): void {
  if (actual !== expected) throw new Error(`Expected ${expected}, received ${actual}`);
}

resetFriendlyIdRegistry();
const firstScenario = '123e4567-e89b-12d3-a456-426614174000';
const secondScenario = 'a1b2c3d4-1111-2222-3333-444455556666';
registerFriendlyIds('scenario', [firstScenario, secondScenario]);
expectEqual(friendlyId('scenario', firstScenario), 'TS-001');
expectEqual(friendlyId('scenario', secondScenario), 'TS-002');
expectEqual(friendlyId('scenario', firstScenario), 'TS-001');
expectEqual(friendlyId('case', 'b2c3d4e5-7777-8888-9999-aaaabbbbcccc'), 'TC-001');
expectEqual(friendlyId('script', 'non-standard-script-id'), 'PW-001');
expectEqual(firstScenario, '123e4567-e89b-12d3-a456-426614174000');
expectEqual(secondScenario, 'a1b2c3d4-1111-2222-3333-444455556666');
