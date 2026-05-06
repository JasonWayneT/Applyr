import React from 'react';
import { Job } from '../types/job';

type Status = Job['status'];

const STATUS_CONFIG: Record<Status, { chipClass: string; dotClass: string; label: string }> = {
  'New':                 { chipClass: 'chip chip-new',              dotClass: 'bg-primary',           label: 'Ready to Apply' },
  'Backlog':              { chipClass: 'chip chip-backlog',          dotClass: 'bg-primary',            label: 'Ready to Apply' },
  'Applied':             { chipClass: 'chip chip-applied',           dotClass: 'bg-on-surface-variant', label: 'Applied' },
  'Recruiter Screen':    { chipClass: 'chip chip-recruiter-screen',  dotClass: 'bg-on-surface-variant', label: 'Screening' },
  'Core Interviews':     { chipClass: 'chip chip-core-interviews',   dotClass: 'bg-secondary',          label: 'Interviewing' },
  'Offer and Negotiation': { chipClass: 'chip chip-offer',          dotClass: 'bg-primary',            label: 'Offer' },
  'Drafted':              { chipClass: 'chip chip-closed',          dotClass: 'bg-on-surface-variant', label: 'Drafting…' },
  'Closed':              { chipClass: 'chip chip-closed',            dotClass: 'bg-on-surface-variant', label: 'Closed' },
};

interface StatusChipProps {
  status: Status;
  long?: boolean; // show full label like "Recruiter Screen" vs short "Screening"
  hasAssets?: boolean;
}

const StatusChip: React.FC<StatusChipProps> = ({ status, long = false, hasAssets = true }) => {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG['Closed'];
  let label = long ? status : config.label;
  
  if ((status === 'New' || status === 'Backlog') && !hasAssets) {
    label = 'Pending';
  }

  return (
    <span className={config.chipClass}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotClass}`} />
      {label}
    </span>
  );
};

export default StatusChip;
