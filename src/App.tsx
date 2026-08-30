import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TodayView from './pages/TodayView';
import AllJobsView from './pages/AllJobsView';
import SyncActivityView from './pages/SyncActivityView';
import JobDetailPanel from './components/JobDetailPanel';
import NotificationPanel from './components/NotificationPanel';
import TuningLogView from './pages/TuningLogView';
import SettingsView from './components/SettingsView';
import { useJobs } from './hooks/useJobs';
import type { OpportunitiesFilter } from './types/opportunities';

function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [opportunitiesFilter, setOpportunitiesFilter] = useState<OpportunitiesFilter>('All');
  const mainRef = useRef<HTMLElement>(null);
  const { jobs, isLoaded, selectedJob, setSelectedJob, handleStatusChange } = useJobs();

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [activeTab]);

  const navigateToOpportunities = (filter: OpportunitiesFilter) => {
    setOpportunitiesFilter(filter);
    setActiveTab('Opportunities');
  };

  const renderPage = () => {
    switch (activeTab) {
      case 'Dashboard':
        return (
          <TodayView
            jobs={jobs}
            onJobClick={setSelectedJob}
            onNavigateToOpportunities={navigateToOpportunities}
            onStatusChange={handleStatusChange}
          />
        );
      case 'Opportunities':
        return (
          <AllJobsView
            jobs={jobs}
            onJobClick={setSelectedJob}
            activeFilter={opportunitiesFilter}
            onFilterChange={setOpportunitiesFilter}
          />
        );
      case 'Job Search':
        return <SyncActivityView />;
      case 'Settings':
        return <SettingsView />;
      case 'Tuning Log':
        return <TuningLogView jobs={jobs} onJobClick={setSelectedJob} />;
      default:
        return (
          <div className="flex items-center justify-center h-64 text-on-surface-variant text-sm">
            Page not found.
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-surface text-on-surface">
      {/* Sidebar Navigation */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} jobs={jobs} />

      {/* Top Header */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 glass-nav flex items-center justify-between px-8 z-40 border-b border-outline-variant shrink-0">
          <div className="flex items-center gap-4 flex-1">
            {/* Future global search or action bar can go here */}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsNotifOpen(prev => !prev)}
              className="p-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-colors active:scale-95 relative"
            >
              <span className="material-symbols-outlined">notifications</span>
              {jobs.filter(j => ['New', 'Backlog', 'Drafted'].includes(j.status)).length > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-secondary rounded-full" />
              )}
            </button>
            <NotificationPanel
              jobs={jobs}
              isOpen={isNotifOpen}
              onClose={() => setIsNotifOpen(false)}
              onJobClick={(job) => { setSelectedJob(job); setIsNotifOpen(false); }}
              onNavigate={(tab) => { setActiveTab(tab); setIsNotifOpen(false); }}
            />
            <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary text-sm font-bold ml-1">
              JT
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main ref={mainRef} className="flex-1 overflow-y-auto px-8 pt-8 pb-12 applyr-scrollbar">
          <div className="max-w-7xl mx-auto">
            {isLoaded ? renderPage() : (
              <div className="flex items-center justify-center h-64 text-on-surface-variant text-sm gap-2">
                <span className="material-symbols-outlined animate-spin">progress_activity</span>
                Loading...
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Slide-out Job Detail Panel */}
      <JobDetailPanel
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onStatusChange={handleStatusChange}
      />
    </div>
  );
}

export default App;
