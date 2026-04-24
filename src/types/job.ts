export interface Job {
  id: string;
  company: string;
  title: string;
  url: string;
  score: number | null;
  status: 'Backlog' | 'Applied' | 'Recruiter Screen' | 'Core Interviews' | 'Offer and Negotiation' | 'Closed';
  rejection_stage?: string | null;
  rejection_type?: 'Ghosted' | 'Rejected' | 'Withdrawn' | 'Other' | null;
  outcome_notes?: string | null;
  interview_date?: string | null;
  summary: string | null;
  created_at: string;
}
