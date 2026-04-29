import React from 'react';
import { Job } from '../types/job';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  jobs: Job[];
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, jobs }) => {
  const newJobsCount = jobs.filter(j => j.status === 'New' || j.status === 'Backlog').length;

  const mainNav = [
    { name: 'Dashboard', icon: 'grid_view' },
    { name: 'Applications', icon: 'view_kanban' },
    { name: 'Scout', icon: 'radar' },
    { name: 'Add Job', icon: 'post_add' },
  ];

  return (
    <aside className="w-64 bg-surface-container-low flex flex-col h-full py-8 px-6 shrink-0">
      {/* Brand */}
      <div className="mb-10 flex items-center gap-3 px-2">
        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
          <span className="material-symbols-outlined text-on-primary text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>spa</span>
        </div>
        <div>
          <h2 className="text-lg font-bold text-primary font-headline tracking-tight leading-tight">The Sanctuary</h2>
          <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">Curated Job Search</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        {mainNav.map((item) => (
          <button
            key={item.name}
            onClick={() => setActiveTab(item.name)}
            className={`w-full flex items-center gap-3 py-3 px-4 rounded-xl text-sm transition-all active:translate-x-1 duration-200 ${
              activeTab === item.name
                ? 'text-primary font-bold border-r-2 border-primary bg-surface-container'
                : 'text-on-surface-variant hover:text-primary'
            }`}
          >
            <span
              className="material-symbols-outlined"
              style={activeTab === item.name ? { fontVariationSettings: "'FILL' 1" } : undefined}
            >
              {item.icon}
            </span>
            <span className="font-headline tracking-tight">{item.name}</span>
            {item.name === 'Dashboard' && newJobsCount > 0 && (
              <span className="ml-auto bg-secondary text-on-secondary text-[10px] font-bold px-2 py-0.5 rounded-full">
                {newJobsCount}
              </span>
            )}
          </button>
        ))}
      </nav>



      {/* Footer */}
      <div className="mt-6 space-y-1">
        <button
          onClick={() => setActiveTab('My profile')}
          className={`w-full flex items-center gap-3 py-3 px-4 rounded-xl text-sm transition-all ${
            activeTab === 'My profile' ? 'text-primary font-bold' : 'text-on-surface-variant hover:text-primary'
          }`}
        >
          <span className="material-symbols-outlined">person</span>
          <span className="font-headline tracking-tight">My Profile</span>
        </button>
        <div className="px-4 pt-3">
          <p className="text-[10px] text-on-surface-variant">Active applications</p>
          <p className="text-sm font-bold text-primary mt-0.5">{jobs.length} open</p>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
