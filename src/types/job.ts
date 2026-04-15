export interface Job {
  id: string;
  company: string;
  title: string;
  url: string;
  score: number | null;
  status: 'Backlog' | 'Applied' | 'Recruiter Screen' | 'Core Interviews' | 'Offer and Negotiation' | 'Closed';
  summary: string | null;
  created_at: string;
}
