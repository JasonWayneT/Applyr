import React from 'react';
import { Job } from '../types/job';
import StatusChip from '../components/StatusChip';

interface TodayViewProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
}

const TodayView: React.FC<TodayViewProps> = ({ jobs, onJobClick }) => {
  const backlogs = jobs.filter(j => j.status === 'Backlog');
  const applied = jobs.filter(j => j.status === 'Applied');
  const activeJobs = jobs.filter(j => !['Closed'].includes(j.status));
  const interviews = jobs
    .filter(j => j.interview_date && !['Closed'].includes(j.status))
    .sort((a, b) => new Date(a.interview_date!).getTime() - new Date(b.interview_date!).getTime());
  
  const nextInterview = interviews.find(j => new Date(j.interview_date!).getTime() > Date.now()) || interviews[0];
  const screenings = jobs.filter(j => j.status === 'Recruiter Screen');
  const offers = jobs.filter(j => j.status === 'Offer and Negotiation');

  const getBarHeight = (count: number, total: number) => {
    if (count === 0) return '4px';
    const percentage = (count / Math.max(total, 1)) * 100;
    return `${Math.max(12, percentage)}%`;
  };

  const statusCounts = [
    { label: 'Backlog', count: backlogs.length, height: getBarHeight(backlogs.length, jobs.length) },
    { label: 'Applied', count: applied.length, height: getBarHeight(applied.length, jobs.length) },
    { label: 'Screening', count: screenings.length, height: getBarHeight(screenings.length, jobs.length) },
    { label: 'Interviews', count: interviews.length, height: getBarHeight(interviews.length, jobs.length) },
    { label: 'Offers', count: offers.length, height: getBarHeight(offers.length, jobs.length) },
  ];

  return (
    <div className="space-y-10">
      {/* Welcome Header */}
      <section className="mb-2">
        <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-2">
          Good morning, Jason.
        </h1>
        <p className="text-on-surface-variant text-lg">
          You have <span className="text-secondary font-bold">{activeJobs.length} active applications</span> in progress. Take a deep breath.
        </p>
      </section>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Application Progress Chart */}
        <div className="lg:col-span-8 bg-surface-container-lowest rounded-[2rem] p-8 editorial-shadow relative overflow-hidden">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-headline font-bold text-on-surface">Application Progress</h3>
              <p className="text-sm text-on-surface-variant">Your journey this month</p>
            </div>
            <select className="input-sanctuary rounded-lg text-xs font-bold py-1 pl-3 pr-8">
              <option>Last 30 Days</option>
              <option>Last Quarter</option>
            </select>
          </div>

          {/* Bar Chart */}
          <div className="h-52 flex items-end gap-4 relative">
            {statusCounts.map((item, i) => (
              <div
                key={item.label}
                className={`flex-1 rounded-t-lg transition-all duration-500 hover:opacity-80 relative group ${
                  item.count === 0 
                    ? 'bg-outline-variant/20' 
                    : i === 2 ? 'bg-primary' : i === 4 ? 'bg-secondary-container' : 'bg-primary-container/50'
                }`}
                style={{ height: item.height }}
              >
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-on-surface text-surface text-[10px] px-2 py-1 rounded whitespace-nowrap">
                  {item.count} {item.label}
                </div>
              </div>
            ))}
            {/* Grid lines */}
            <div className="absolute inset-x-0 top-1/4 border-b border-outline-variant/10 border-dashed"></div>
            <div className="absolute inset-x-0 top-2/4 border-b border-outline-variant/10 border-dashed"></div>
            <div className="absolute inset-x-0 top-3/4 border-b border-outline-variant/10 border-dashed"></div>
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-2">
            {statusCounts.map(s => <span key={s.label}>{s.label}</span>)}
          </div>
        </div>

        {/* Next Interview / Quick Stats */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {nextInterview ? (
            <div className="bg-primary text-on-primary rounded-[2rem] p-8 flex-1 flex flex-col justify-between shadow-xl shadow-primary/10 transition-all hover:-translate-y-1">
              <div>
                <span className="material-symbols-outlined text-4xl mb-4" style={{ fontVariationSettings: "'FILL' 1" }}>calendar_today</span>
                <h3 className="text-xl font-headline font-bold mb-2">Next Interview</h3>
                <p className="text-on-primary/80 text-sm mb-6">{nextInterview.title} at {nextInterview.company}</p>
                <div className="bg-on-primary/10 backdrop-blur-md rounded-2xl p-4 border border-on-primary/5">
                  <p className="text-xs font-bold uppercase tracking-widest opacity-60">Scheduled</p>
                  <p className="text-lg font-bold">
                    {new Date(nextInterview.interview_date!).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
              <button 
                onClick={() => onJobClick(nextInterview)}
                className="mt-6 flex items-center justify-center gap-2 bg-on-primary text-primary font-bold py-3 rounded-xl hover:bg-on-primary-container transition-colors"
              >
                Prep for Interview
              </button>
            </div>
          ) : (
            <div className="bg-surface-container-lowest rounded-[2rem] p-8 flex-1 flex flex-col justify-center items-center editorial-shadow text-center">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-3">event_available</span>
              <h3 className="text-lg font-headline font-bold text-on-surface mb-1">No interviews yet</h3>
              <p className="text-sm text-on-surface-variant">Keep applying and you'll land one soon.</p>
            </div>
          )}
        </div>

        {/* Active Applications List */}
        <div className="lg:col-span-12 mt-2">
          <h3 className="text-2xl font-headline font-bold text-on-surface mb-6">Active Applications</h3>
          <div className="space-y-4">
            {activeJobs.slice(0, 8).map(job => (
              <div
                key={job.id}
                onClick={() => onJobClick(job)}
                className="group bg-surface-container-lowest p-6 rounded-3xl flex flex-col md:flex-row md:items-center gap-4 editorial-shadow hover:shadow-lg transition-all border border-transparent hover:border-outline-variant/10 cursor-pointer"
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary text-lg">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h4 className="font-bold text-lg text-on-surface">{job.company}</h4>
                    <p className="text-sm text-on-surface-variant">{job.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  {job.score && (
                    <div className="hidden lg:block">
                      <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Fit Score</p>
                      <p className={`text-sm font-bold ${job.score >= 80 ? 'text-primary' : 'text-on-surface-variant'}`}>{job.score}</p>
                    </div>
                  )}
                  <div className="min-w-[130px]">
                  <StatusChip status={job.status} />
                  </div>
                  <button className="w-10 h-10 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container transition-colors">
                    <span className="material-symbols-outlined">more_vert</span>
                  </button>
                </div>
              </div>
            ))}
            {activeJobs.length === 0 && (
              <div className="bg-surface-container-lowest rounded-3xl p-12 text-center editorial-shadow">
                <span className="material-symbols-outlined text-5xl text-on-surface-variant/30 mb-3">work_outline</span>
                <p className="text-on-surface-variant">No active applications yet. Start your journey.</p>
              </div>
            )}
          </div>
        </div>

        {/* Upcoming Interviews Schedule */}
        <div className="lg:col-span-12 mt-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-headline font-bold text-on-surface">Upcoming Interviews</h3>
            <div className="flex gap-2">
              <span className="badge bg-secondary/10 text-secondary text-xs">{interviews.length} Scheduled</span>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {interviews.map(job => (
              <div 
                key={job.id}
                onClick={() => onJobClick(job)}
                className="bg-surface-container-lowest p-6 rounded-3xl editorial-shadow border border-outline-variant/10 hover:border-primary/20 transition-all cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="w-12 h-12 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Date</p>
                    <p className="text-sm font-bold text-on-surface">
                      {new Date(job.interview_date!).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </p>
                  </div>
                </div>
                <h4 className="font-bold text-on-surface group-hover:text-primary transition-colors">{job.company}</h4>
                <p className="text-xs text-on-surface-variant mb-4">{job.title}</p>
                <div className="flex items-center gap-2 pt-4 border-t border-outline-variant/5">
                  <span className="material-symbols-outlined text-sm text-secondary">schedule</span>
                  <span className="text-xs font-bold text-secondary">
                    {new Date(job.interview_date!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
            {interviews.length === 0 && (
              <div className="col-span-full py-12 bg-surface-container-low/30 border border-dashed border-outline-variant/20 rounded-3xl text-center">
                <p className="text-on-surface-variant text-sm">No future interviews scheduled.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mt-4 pb-8">
        {[
          { label: 'Total Active', value: activeJobs.length, icon: 'trending_up' },
          { label: 'Screening', value: screenings.length, icon: 'hourglass_top' },
          { label: 'Interviewing', value: interviews.length, icon: 'record_voice_over', accent: true },
          { label: 'Response Rate', value: jobs.length > 0 ? `${Math.round((screenings.length + interviews.length + offers.length) / jobs.length * 100)}%` : '0%', icon: 'insights', accent: true },
        ].map(stat => (
          <div key={stat.label} className="bg-surface-container-lowest rounded-2xl p-6 editorial-shadow">
            <div className="flex items-center justify-between mb-3">
              <span className="material-symbols-outlined text-on-surface-variant/40">{stat.icon}</span>
            </div>
            <span className={`text-3xl font-headline font-extrabold ${stat.accent ? 'text-primary' : 'text-on-surface'}`}>{stat.value}</span>
            <p className="text-xs text-on-surface-variant mt-1 font-medium">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TodayView;
