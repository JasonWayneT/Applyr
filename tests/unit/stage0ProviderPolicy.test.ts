import { readFileSync } from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import { normalizeStage0EvidencePolicy } from '../../server/services/stage0Policy.js';

type PolicyCase = {
  name: string;
  settings: Record<string, unknown>;
  expected: Record<string, unknown>;
};

const fixture = JSON.parse(
  readFileSync(path.join(process.cwd(), 'tests', 'fixtures', 'stage0_provider_policy.json'), 'utf8'),
) as { cases: PolicyCase[] };

describe('Stage 0 provider policy normalization', () => {
  for (const testCase of fixture.cases) {
    it(`matches the shared fixture: ${testCase.name}`, () => {
      expect(normalizeStage0EvidencePolicy(testCase.settings)).toEqual(testCase.expected);
    });
  }
});
