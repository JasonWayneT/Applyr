import { describe, it, expect } from 'vitest';
import { computeTimelineSteps } from '../../src/components/job-detail/StatusSection';

describe('computeTimelineSteps', () => {
  it('marks Backlog as active for Backlog status', () => {
    const steps = computeTimelineSteps('Backlog');
    expect(steps[0].active).toBe(true);
    expect(steps[0].done).toBe(true);
    expect(steps[1].active).toBe(false);
  });

  it('marks Backlog as active for Drafted status (pre-application)', () => {
    const steps = computeTimelineSteps('Drafted');
    expect(steps[0].active).toBe(true);
    expect(steps[0].done).toBe(true);
    expect(steps[1].active).toBe(false);
    expect(steps[1].done).toBe(false);
  });

  it('marks Applied as active and done for Applied status', () => {
    const steps = computeTimelineSteps('Applied');
    expect(steps[0].done).toBe(true);
    expect(steps[1].active).toBe(true);
    expect(steps[1].done).toBe(true);
    expect(steps[2].active).toBe(false);
    expect(steps[2].done).toBe(false);
  });

  it('marks Recruiter Screen as active (not done) when in that status', () => {
    const steps = computeTimelineSteps('Recruiter Screen');
    expect(steps[2].active).toBe(true);
    expect(steps[2].done).toBe(false); // active = currently here, done = completed and past it
    expect(steps[0].done).toBe(true);
    expect(steps[1].done).toBe(true);
    expect(steps[3].done).toBe(false);
  });

  it('marks through Core Interviews as done when in Core Interviews', () => {
    const steps = computeTimelineSteps('Core Interviews');
    expect(steps[3].active).toBe(true);
    expect(steps[3].done).toBe(false);
    expect(steps[0].done).toBe(true);
    expect(steps[1].done).toBe(true);
    expect(steps[2].done).toBe(true);
  });

  it('marks everything through Offer as done at Offer and Negotiation', () => {
    const steps = computeTimelineSteps('Offer and Negotiation');
    expect(steps[4].active).toBe(true);
    expect(steps[4].done).toBe(true);
    expect(steps[0].done).toBe(true);
    expect(steps[1].done).toBe(true);
    expect(steps[2].done).toBe(true);
    expect(steps[3].done).toBe(true);
  });

  it('marks nothing past Backlog for unknown statuses', () => {
    const steps = computeTimelineSteps('Closed');
    expect(steps[0].done).toBe(true);
    expect(steps[1].done).toBe(false);
    expect(steps[1].active).toBe(false);
    expect(steps[4].active).toBe(false);
  });
});
