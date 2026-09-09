import React, { useState, useRef, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TodayView from './pages/TodayView';
import AllJobsView from './pages/AllJobsView';
import SyncActivityView from './pages/SyncActivityView';
import JobDetailPanel from './components/JobDetailPanel';
import NotificationPanel from './components/NotificationPanel';
import TuningLogView from './pages/TuningLogView';
import SettingsView from './components/SettingsView';
import ReviewCenterView from './pages/ReviewCenterView';
import ErrorBoundary from './components/ErrorBoundary';
import { useReviewCenter } from './hooks/useReviewCenter';
import { companyOpportunityKey } from './lib/reviewCenter';
import { useJobs } from './hooks/useJobs';
import type { OpportunitiesFilter } from './types/opportunities';

function App() {
  // CR-104 Epic 11: initialize state from URL search params for deep-link/back-button support.
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tab') || 'Dashboard';
  });
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [opportunitiesFilter, setOpportunitiesFilter] = useState<OpportunitiesFilter>(() => {
    const params = new URLSearchParams(window.location.search);
    return (params.get('filter') as OpportunitiesFilter) || 'All';
  });
  const mainRef = useRef<HTMLElement>(null);
  const { jobs, isLoaded, selectedJob, setSelectedJob, handleStatusChange } = useJobs();
  const reviewCenter = useReviewCenter();
  const restoredJobFromUrlRef = useRef(false);

  // Sync state changes to URL (replaceState, no page reload)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tab', activeTab);
    if (opportunitiesFilter !== 'All') params.set('filter', opportunitiesFilter);
    else params.delete('filter');
    if (selectedJob) params.set('job', selectedJob.id);
    else params.delete('job');
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
  }, [activeTab, opportunitiesFilter, selectedJob]);

  // Restore the selected job from the URL once jobs have loaded (deep link / refresh).
  // `job` isn't in the initial useState the way tab/filter are, because it needs the
  // full Job object from the loaded `jobs` list, not just an id.
  useEffect(() => {
    if (restoredJobFromUrlRef.current || !isLoaded) return;
    restoredJobFromUrlRef.current = true;
    const jobId = new URLSearchParams(window.location.search).get('job');
    if (!jobId) return;
    const job = jobs.find((j) => j.id === jobId);
    if (job) setSelectedJob(job);
  }, [isLoaded, jobs, setSelectedJob]);

  // Restore state from URL on browser back/forward
  useEffect(() => {
    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab) setActiveTab(tab);
      const filter = params.get('filter') as OpportunitiesFilter | null;
      setOpportunitiesFilter(filter || 'All');
      const jobId = params.get('job');
      setSelectedJob(jobId ? jobs.find((j) => j.id === jobId) || null : null);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [jobs, setSelectedJob]);

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
      // Implements FR-285: expose Review Center within the existing application shell.
      case 'Review Center':
        return (
          <ReviewCenterView
            items={reviewCenter.items}
            isLoading={reviewCenter.isLoading}
            available={reviewCenter.available}
            error={reviewCenter.error}
            onRefresh={() => { void reviewCenter.refresh(); }}
            onAnswer={reviewCenter.answer}
            onVerifyPromotion={reviewCenter.verifyPromotion}
            onOpenJob={(jobId) => {
              // The opportunity_key is a folder slug (e.g. "workday_practice"),
              // which may not exactly match any job's id or company slug.
              // Try exact match first, then a starts-with fallback so a folder
              // like "acme_practice" still finds the job at company "Acme".
              const job = jobs.find(candidate => {
                const slug = companyOpportunityKey(candidate.company);
                return candidate.id === jobId
                  || slug === jobId
                  || jobId.startsWith(slug)
                  || slug.startsWith(jobId);
              });
              if (job) {
                setSelectedJob(job);
              } else {
                // No matching job in the DB — switch to Opportunities so the
                // user can find it manually instead of a silent dead click.
                setActiveTab('Opportunities');
              }
            }}
          />
        );
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
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        jobs={jobs}
        reviewPendingCount={reviewCenter.pendingCount}
      />

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
            {isLoaded ? (
              <ErrorBoundary
                fallback={
                  <div className="flex flex-col items-center justify-center h-64 text-on-surface-variant text-sm gap-4">
                    <p>Something went wrong. Try reloading the page.</p>
                    <button
                      onClick={() => window.location.reload()}
                      className="btn-primary text-xs px-4 py-2 rounded-xl"
                    >
                      Reload
                    </button>
                  </div>
                }
              >
                {renderPage()}
              </ErrorBoundary>
            ) : (
              <div className="flex items-center justify-center h-64 text-on-surface-variant text-sm gap-2">
                <span className="material-symbols-outlined animate-spin">progress_activity</span>
                Loading...
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Slide-out Job Detail Panel — isolated boundary so a panel crash
          doesn't take out the rest of the app (CR-104 Epic 4 Story 4.3) */}
      <ErrorBoundary
        fallback={
          <div className="fixed right-0 top-0 h-full w-[520px] bg-surface z-50 editorial-shadow animate-slide-in p-8">
            <p className="text-sm text-on-surface-variant">
              This panel encountered an error. Close and reopen the job to try again.
            </p>
            <button
              onClick={() => setSelectedJob(null)}
              className="mt-4 text-xs text-primary hover:underline"
            >
              Close panel
            </button>
          </div>
        }
      >
        <JobDetailPanel
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onStatusChange={handleStatusChange}
          onNavigateToReviewCenter={() => setActiveTab('Review Center')}
        />
      </ErrorBoundary>
    </div>
  );
}

export default App;
