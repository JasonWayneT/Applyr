import React from 'react';
import type { Job } from '../../types/job';

export interface TimelineStep {
  label: string;
  done: boolean;
  active: boolean;
}

/** Pure function computing timeline stepper state from a job status.
 * Extracted for testability (CR-104 Epic 6 Story 6.3). */
export function computeTimelineSteps(status: string): TimelineStep[] {
  return [
    { label: 'Backlog',            done: true,                                                                          active: status === 'Backlog' || status === 'Drafted' },
    { label: 'Applied',            done: ['Applied','Recruiter Screen','Core Interviews','Offer and Negotiation'].includes(status), active: status === 'Applied' },
    { label: 'Recruiter Screen',   done: ['Core Interviews','Offer and Negotiation'].includes(status),              active: status === 'Recruiter Screen' },
    { label: 'Core Interviews',    done: status === 'Offer and Negotiation',                                        active: status === 'Core Interviews' },
    { label: 'Offer',              done: status === 'Offer and Negotiation',                                        active: status === 'Offer and Negotiation' },
  ];
}

interface StatusSectionProps {
  status: Job['status'];
}

/** Application Status timeline stepper — extracted from JobDetailPanel (CR-104 Story 1.1). */
const StatusSection: React.FC<StatusSectionProps> = ({ status }) => {
  const timelineSteps = computeTimelineSteps(status);

  return (
    <section className="bg-surface-container-low p-6 rounded-2xl">
      <h3 className="text-lg font-headline font-bold text-on-surface mb-4">Application Status</h3>
      <div className="space-y-5 relative">
        <div className="absolute left-3 top-3 bottom-3 w-px bg-outline-variant/30" />
        {timelineSteps.map((step, i) => (
          <div key={i} className="flex gap-4 relative">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center z-10 shrink-0 ${
              step.active ? 'bg-secondary ring-4 ring-secondary-container/50' :
              step.done  ? 'bg-primary' :
              'bg-surface-container-highest border border-outline-variant'
            }`}>
              {step.done && <span className="material-symbols-outlined text-white text-[14px]">check</span>}
            </div>
            <div className={step.done ? '' : 'opacity-50'}>
              <p className="text-sm font-bold text-on-surface">{step.label}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default StatusSection;
