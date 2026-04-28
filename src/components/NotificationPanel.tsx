import React from 'react';
import { Job } from '../types/job';

interface Notification {
  id: string;
  icon: string;
  iconClass: string;
  title: string;
  detail: string;
  time: string;
  action?: () => void;
}

interface NotificationPanelProps {
  jobs: Job[];
  isOpen: boolean;
  onClose: () => void;
  onJobClick: (job: Job) => void;
  onNavigate: (tab: string) => void;
}

const NotificationPanel: React.FC<NotificationPanelProps> = ({ jobs, isOpen, onClose, onJobClick, onNavigate }) => {
  if (!isOpen) return null;

  const notifications: Notification[] = [];
  const now = Date.now();

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
      action: () => { onNavigate('Applications'); onClose(); },
    });
  }

  // 2. Backlog items waiting for review
  const backlog = jobs.filter(j => j.status === 'Backlog');
  if (backlog.length > 0) {
    notifications.push({
      id: 'backlog',
      icon: 'priority_high',
      iconClass: 'bg-status-backlog-bg text-status-backlog-text',
      title: `${backlog.length} job${backlog.length > 1 ? 's' : ''} need review`,
      detail: 'Backlog items waiting for your decision.',
      time: 'Action needed',
      action: () => { onNavigate('Applications'); onClose(); },
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
      action: () => { onNavigate('Applications'); onClose(); },
    });
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-50" onClick={onClose} />

      {/* Panel */}
      <div className="absolute right-8 top-14 z-50 w-96 bg-surface-container-lowest rounded-2xl editorial-shadow border border-outline-variant/10 animate-slide-up overflow-hidden">
        <div className="px-5 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <h3 className="text-sm font-headline font-bold text-on-surface">Notifications</h3>
          <span className="text-[10px] text-on-surface-variant">{notifications.length} active</span>
        </div>

        <div className="max-h-[400px] overflow-y-auto sanctuary-scrollbar">
          {notifications.length === 0 ? (
            <div className="py-12 text-center">
              <span className="material-symbols-outlined text-3xl text-on-surface-variant/30 mb-2 block">notifications_off</span>
              <p className="text-sm text-on-surface-variant">All clear. Nothing needs your attention.</p>
            </div>
          ) : (
            notifications.map(n => (
              <button
                key={n.id}
                onClick={n.action}
                className="w-full px-5 py-4 flex items-start gap-3 hover:bg-surface-container transition-colors text-left border-b border-outline-variant/5 last:border-b-0"
              >
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${n.iconClass}`}>
                  <span className="material-symbols-outlined text-base">{n.icon}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-on-surface">{n.title}</p>
                  <p className="text-xs text-on-surface-variant mt-0.5 truncate">{n.detail}</p>
                </div>
                <span className="text-[10px] text-on-surface-variant whitespace-nowrap mt-0.5">{n.time}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </>
  );
};

export default NotificationPanel;
