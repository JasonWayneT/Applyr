export const OPPORTUNITIES_FILTERS = [
  'All',
  'Backlog',
  'Applied',
  'Screening',
  'Interviews',
  'Offers',
  'Retry',
  'Closed',
] as const;
export type OpportunitiesFilter = (typeof OPPORTUNITIES_FILTERS)[number];

/** Dashboard funnel / stat label → Opportunities tab filter (1:1 stage alignment) */
export const DASHBOARD_FILTER_MAP: Record<string, OpportunitiesFilter> = {
  Backlog: 'Backlog',
  'Ready to Apply': 'Backlog',
  Applied: 'Applied',
  Screening: 'Screening',
  Interviews: 'Interviews',
  Offers: 'Offers',
  'Total Active': 'All',
  Interviewing: 'Interviews',
};

/** Job statuses included per stage filter */
export const FILTER_STATUS_MAP: Record<OpportunitiesFilter, string[] | null> = {
  All: null,
  Backlog: ['New', 'Backlog'],
  Applied: ['Applied'],
  Screening: ['Recruiter Screen'],
  Interviews: ['Core Interviews'],
  Offers: ['Offer and Negotiation'],
  Retry: ['Needs Retry'],
  Closed: ['Closed'],
};
