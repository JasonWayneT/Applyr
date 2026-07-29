export interface Job {
  id: string;
  company: string;
  title: string;
  url: string;
  score: number | null;
  status: 'New' | 'Backlog' | 'Drafted' | 'Needs Retry' | 'Rejected' | 'Applied' | 'Recruiter Screen' | 'Core Interviews' | 'Offer and Negotiation' | 'Closed';
  retry_count?: number;
  rejection_stage?: string | null;
  rejection_type?: 'Ghosted' | 'Rejected' | 'Withdrawn' | 'Other' | 'Self-Rejected' | 'No Longer Available' | null;
  outcome_notes?: string | null;
  interview_date?: string | null;
  /** When the application was submitted (null until Applied+). Separate from created_at (discovered). */
  applied_at?: string | null;
  summary: string | null;
  created_at: string;
  has_assets?: boolean;
  sources?: string[];
  score_total?: number | null;
  score_breakdown_json?: string | null;
  reason_summary?: string | null;
}
