export interface Contact {
  id: string;
  job_id: string | null;
  company: string;
  contact_name: string;
  contact_title: string | null;
  contact_type: 'hiring_manager' | 'warm_connection' | 'informational';
  source: string | null;
  message_sent_at: string;
  status: 'active' | 'responded' | 'closed';
  next_follow_up_due: string | null;
  last_touch_at: string;
  follow_up_count: number;
  notes: string | null;
  confirmed: boolean;
  created_at: string;
  updated_at: string;
}
