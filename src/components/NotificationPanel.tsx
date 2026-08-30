import React, { useEffect, useState } from 'react';
import { Job } from '../types/job';
import { api } from '../lib/api';

interface Notification {
  id: string;
  icon: string;
  iconClass: string;
  title: string;
  detail: string;
  time: string;
  action?: () => void;
}

interface GmailSyncNotification {
  id: number;
  timestamp: string;
  category: 'confirmation' | 'rejection' | 'interview';
  job_id: string | null;
  company: string | null;
  subject: string | null;
  message: string;
}

// CR-106
interface LlmUsageNotification {
  id: number;
  timestamp: string;
  provider: string | null;
  reason: string | null;
  message: string;
}

interface NotificationPanelProps {
  jobs: Job[];
  isOpen: boolean;
  onClose: () => void;
  onJobClick: (job: Job) => void;
  onNavigate: (tab: string) => void;
}

/** Coarse "time ago" label — matches the plain-language style of this panel's other time labels. */
function timeAgo(timestamp: string): string {
  const then = new Date(timestamp + ' Z').getTime();
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

// Polls independently of the Job Search page's own log console — this component stays mounted for the
// whole session (App.tsx renders it unconditionally, gating visibility internally), so it picks up
// findings from both the manual "Check Gmail Now" button and the 10-minute background scheduler without
// either trigger needing to know about the Notifications panel at all.
const GMAIL_POLL_MS = 10000;

const NotificationPanel: React.FC<NotificationPanelProps> = ({ jobs, isOpen, onClose, onJobClick, onNavigate }) => {
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [gmailNotifs, setGmailNotifs] = useState<GmailSyncNotification[]>([]);
  const [llmNotifs, setLlmNotifs] = useState<LlmUsageNotification[]>([]);

  useEffect(() => {
    let cancelled = false;
    const fetchGmailNotifs = async () => {
      try {
        const res = await fetch(api('/api/gmail-sync/notifications'));
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && Array.isArray(data)) setGmailNotifs(data);
      } catch {
        // silent — notification panel shouldn't surface its own fetch errors
      }
    };
    // CR-106: independent poll, same interval — a provider cascade/exhaustion event is exactly
    // as "found out from a log Jason isn't watching" as a missed Gmail sync finding otherwise.
    const fetchLlmNotifs = async () => {
      try {
        const res = await fetch(api('/api/llm-usage/notifications'));
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && Array.isArray(data)) setLlmNotifs(data);
      } catch {
        // silent — same as above
      }
    };
    fetchGmailNotifs();
    fetchLlmNotifs();
    const interval = setInterval(() => {
      fetchGmailNotifs();
      fetchLlmNotifs();
    }, GMAIL_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!isOpen) return null;

  const notifications: Notification[] = [];
  const now = Date.now();

  // 0. Gmail sync findings (manual "Check Gmail Now" or the 10-minute background scheduler — both
  // write to the same activity_log source, so this one list covers both without extra plumbing).
  for (const g of gmailNotifs) {
    const job = g.job_id ? jobs.find(j => j.id === g.job_id) : undefined;
    const icon =
      g.category === 'rejection' ? 'mail' : g.category === 'interview' ? 'event_available' : 'mark_email_read';
    const iconClass =
      g.category === 'rejection'
        ? 'bg-error-container text-on-error-container'
        : g.category === 'interview'
          ? 'bg-success-container text-on-success-container'
          : 'bg-secondary-container text-on-secondary-container';
    const title =
      g.category === 'rejection'
        ? `Rejected: ${g.company ?? 'Unknown company'}`
        : g.category === 'interview'
          ? `Interview detected: ${g.company ?? 'Unknown company'}`
          : `Application confirmed: ${g.company ?? 'Unknown company'}`;
    const detail =
      g.category === 'rejection'
        ? `Job closed automatically — "${g.subject ?? ''}"`
        : g.category === 'interview'
          ? g.message // CR-106: orchestrator's own message already says whether status changed
          : `${g.subject ?? ''}`;
    notifications.push({
      id: `gmail-${g.id}`,
      icon,
      iconClass,
      title,
      detail,
      time: timeAgo(g.timestamp),
      action: job ? () => { onJobClick(job); onClose(); } : () => { onNavigate('Job Search'); onClose(); },
    });
  }

  // 0.5 LLM provider cascade/exhaustion events (CR-106) — a task's default provider hit a real
  // rate limit or daily cap and either cascaded to the next configured provider or got disabled
  // for 24h. Routes to Settings rather than a job, since there's no single job this concerns.
  for (const l of llmNotifs) {
    notifications.push({
      id: `llm-${l.id}`,
      icon: 'bolt',
      iconClass: 'bg-tertiary-container text-on-tertiary-container',
      title: `${l.provider ? l.provider.charAt(0).toUpperCase() + l.provider.slice(1) : 'A provider'} rate-limited`,
      detail: l.message,
      time: timeAgo(l.timestamp),
      action: () => { onNavigate('Settings'); onClose(); },
    });
  }

  // 1. New jobs from scout (status = 'New')
  const newJobs = jobs.filter(j => j.status === 'New');
  if (newJobs.length > 0) {
    notifications.push({
      id: 'new-jobs',
      icon: 'fiber_new',
      iconClass: 'bg-status-new-bg text-status-new-text',
      title: `${newJobs.length} new role${newJobs.length > 1 ? 's' : ''} found`,
      detail: newJobs.slice(0, 3).map(j => j.company).join(', ') + (newJobs.length > 3 ? ` +${newJobs.length - 3} more` : ''),
      time: 'From last scout',
      action: () => { onNavigate('Opportunities'); onClose(); },
    });
  }

  // 2. Backlog items ready to apply
  const backlog = jobs.filter(j => j.status === 'Backlog');
  if (backlog.length > 0) {
    notifications.push({
      id: 'backlog',
      icon: 'star',
      iconClass: 'bg-status-applied-bg text-status-applied-text',
      title: `${backlog.length} matched role${backlog.length > 1 ? 's' : ''} ready to apply`,
      detail: 'New opportunities ready for your application.',
      time: 'Ready to Apply',
      action: () => { onNavigate('Opportunities'); onClose(); },
    });
  }

  // 3. Upcoming interviews (interview_date in the future, within 3 days)
  const upcomingInterviews = jobs.filter(j => {
    if (!j.interview_date) return false;
    const d = new Date(j.interview_date).getTime();
    return d > now && d - now < 3 * 24 * 60 * 60 * 1000;
  });
  for (const job of upcomingInterviews) {
    const interviewDate = new Date(job.interview_date!);
    const diffHours = Math.round((interviewDate.getTime() - now) / (1000 * 60 * 60));
    const timeLabel = diffHours < 24 ? `In ${diffHours} hours` : `In ${Math.round(diffHours / 24)} day${Math.round(diffHours / 24) > 1 ? 's' : ''}`;

    notifications.push({
      id: `interview-${job.id}`,
      icon: 'event',
      iconClass: 'bg-secondary-container text-on-secondary-container',
      title: `Interview: ${job.company}`,
      detail: `${job.title} on ${interviewDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}`,
      time: timeLabel,
      action: () => { onJobClick(job); onClose(); },
    });
  }

  // 4. Active screening/interviews (general awareness)
  const activeInterviews = jobs.filter(j => ['Recruiter Screen', 'Core Interviews'].includes(j.status));
  if (activeInterviews.length > 0) {
    notifications.push({
      id: 'active-interviews',
      icon: 'record_voice_over',
      iconClass: 'bg-secondary-container text-on-secondary-container',
      title: `${activeInterviews.length} active interview process${activeInterviews.length > 1 ? 'es' : ''}`,
      detail: activeInterviews.map(j => j.company).join(', '),
      time: 'In progress',
      action: () => { onNavigate('Opportunities'); onClose(); },
    });
  }

  const visibleNotifications = notifications.filter(n => !dismissedIds.has(n.id));

  const dismiss = (id: string) => {
    setDismissedIds(prev => new Set(prev).add(id));
  };

  const clearAll = () => {
    setDismissedIds(prev => {
      const next = new Set(prev);
      notifications.forEach(n => next.add(n.id));
      return next;
    });
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-50" onClick={onClose} />

      {/* Panel */}
      <div className="absolute right-8 top-14 z-50 w-96 bg-surface-container-lowest rounded-2xl editorial-shadow animate-slide-up overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="text-sm font-headline font-bold text-on-surface">Notifications</h3>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-on-surface-variant">{visibleNotifications.length} active</span>
            {visibleNotifications.length > 0 && (
              <button
                type="button"
                onClick={clearAll}
                className="text-[10px] font-extrabold text-primary uppercase tracking-wider hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        <div className="max-h-[400px] overflow-y-auto applyr-scrollbar">
          {visibleNotifications.length === 0 ? (
            <div className="py-12 text-center">
              <span className="material-symbols-outlined text-3xl text-on-surface-variant/30 mb-2 block">notifications_off</span>
              <p className="text-sm text-on-surface-variant">All clear. Nothing needs your attention.</p>
            </div>
          ) : (
            visibleNotifications.map(n => (
              <div
                key={n.id}
                role="button"
                tabIndex={0}
                onClick={n.action}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); n.action?.(); }
                }}
                className="w-full px-5 py-4 flex items-start gap-3 hover:bg-surface-container transition-colors text-left border-b border-outline-variant/5 last:border-b-0 cursor-pointer"
              >
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${n.iconClass}`}>
                  <span className="material-symbols-outlined text-base">{n.icon}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-on-surface">{n.title}</p>
                  <p className="text-xs text-on-surface-variant mt-0.5 truncate">{n.detail}</p>
                </div>
                <span className="text-[10px] text-on-surface-variant whitespace-nowrap mt-0.5">{n.time}</span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); dismiss(n.id); }}
                  className="text-on-surface-variant/50 hover:text-on-surface-variant hover:bg-surface-container-high rounded-full w-9 h-9 flex items-center justify-center shrink-0 -my-2 -mr-2"
                  title="Dismiss"
                >
                  <span className="material-symbols-outlined text-base">close</span>
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
};

export default NotificationPanel;
