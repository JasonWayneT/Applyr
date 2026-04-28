import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TodayView from './pages/TodayView';
import AllJobsView from './pages/AllJobsView';
import FindNewJobsView from './pages/FindNewJobsView';
import SyncActivityView from './pages/SyncActivityView';
import ProfileView from './pages/ProfileView';
import JobDetailPanel from './components/JobDetailPanel';
import NotificationPanel from './components/NotificationPanel';
import { Job } from './types/job';
import { api } from './lib/api';

function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(api('/api/jobs'));
        const data = await res.json();
        setJobs(data);
      } catch (err) {
        console.error('Failed to fetch jobs in App.tsx:', err);
      }
    };
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const renderPage = () => {
    switch (activeTab) {
      case 'Dashboard':
        return <TodayView jobs={jobs} onJobClick={setSelectedJob} />;
      case 'Applications':
        return <AllJobsView jobs={jobs} onJobClick={setSelectedJob} />;
      case 'Add Job':
        return <FindNewJobsView />;
      case 'Scout':
        return <SyncActivityView />;
      case 'My profile':
        return <ProfileView />;
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
        <header className="h-16 glass-nav flex items-center justify-between px-8 z-40 editorial-shadow shrink-0">
          <div className="flex items-center gap-4 flex-1">
            {/* Future global search or action bar can go here */}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsNotifOpen(prev => !prev)}
              className="p-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-colors active:scale-95 relative"
            >
              <span className="material-symbols-outlined">notifications</span>
              {jobs.filter(j => j.status === 'New' || j.status === 'Backlog').length > 0 && (
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
            <button
              onClick={() => setActiveTab('My profile')}
              className="p-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-colors active:scale-95"
            >
              <span className="material-symbols-outlined">settings</span>
            </button>
            <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary text-sm font-bold ml-1">
              JT
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto px-8 pt-8 pb-12 sanctuary-scrollbar">
          <div className="max-w-7xl mx-auto">
            {renderPage()}
          </div>
        </main>
      </div>

      {/* Slide-out Job Detail Panel */}
      <JobDetailPanel
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
      />
    </div>
  );
}

export default App;
