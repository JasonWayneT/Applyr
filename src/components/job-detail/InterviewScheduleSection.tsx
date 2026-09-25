import React from 'react';
import { statusRequiresInterviewDateTime } from 'shared/domain/jobPipeline';

interface Progression {
  label: string;
  next: string;
  icon: string;
}

interface InterviewScheduleSectionProps {
  interviewDate: string;
  onDateChange: (date: string) => void;
  progression?: Progression;
}

/** Interview Schedule — extracted from JobDetailPanel (CR-104 Story 1.2). */
const InterviewScheduleSection: React.FC<InterviewScheduleSectionProps> = ({
  interviewDate,
  onDateChange,
  progression,
}) => {
  return (
    <section className="bg-primary/5 p-6 rounded-2xl border border-primary/10">
      <div className="flex items-center gap-3 mb-4">
        <span className="material-symbols-outlined text-primary">calendar_month</span>
        <h3 className="text-lg font-headline font-bold text-on-surface">Interview Schedule</h3>
      </div>
      <div className="space-y-4">
        <div>
          <label htmlFor="interview-date-input" className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Date & Time</label>
          <input
            id="interview-date-input"
            type="datetime-local"
            value={interviewDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="input-applyr w-full text-sm rounded-xl py-2.5 px-4"
            required={!!progression && statusRequiresInterviewDateTime(progression.next)}
          />
        </div>
        {progression && statusRequiresInterviewDateTime(progression.next) && (
          <p className="text-[11px] text-on-surface-variant">
            Required before &ldquo;{progression.label}&rdquo;
          </p>
        )}
        {interviewDate && (
          <p className="text-[11px] text-primary font-medium flex items-center gap-1">
            <span className="material-symbols-outlined text-sm">notifications_active</span>
            Scheduled for {new Date(interviewDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
          </p>
        )}
      </div>
    </section>
  );
};

export default InterviewScheduleSection;
