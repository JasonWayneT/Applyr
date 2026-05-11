import React, { useState, useRef, useEffect } from 'react';
import { Job } from '../types/job';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  jobs: Job[];
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, jobs }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  
  const newJobsCount = jobs.filter(j => j.status === 'Backlog' && j.has_assets).length;

  const mainNav = [
    { name: 'Dashboard', icon: 'grid_view' },
    { name: 'Opportunities', icon: 'view_kanban' },
    { name: 'Job Search', icon: 'radar' },
    { name: 'Add Job', icon: 'post_add' },
    { name: 'Tuning Log', icon: 'tune' },
  ];

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNavigate = (tab: string, subtab?: string) => {
    if (subtab) {
      localStorage.setItem('profile_subtab', subtab);
    }
    setActiveTab(tab);
    setIsMenuOpen(false);
  };

  return (
    <aside className="w-64 bg-surface-container-low flex flex-col h-full py-8 px-6 shrink-0 relative">
      {/* Brand */}
      <div className="mb-10 flex items-center gap-3 px-2">
        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
          <span className="material-symbols-outlined text-on-primary text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>spa</span>
        </div>
        <div>
          <h2 className="text-lg font-bold text-primary font-headline tracking-tight leading-tight">Applyr</h2>
          <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">Curated Job Search</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1">
        {mainNav.map((item) => (
          <button
            key={item.name}
            onClick={() => handleNavigate(item.name)}
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

      {/* ChatGPT-Style Profile & Settings Footer Menu */}
      <div className="mt-auto pt-6 border-t border-outline-variant/10 relative" ref={menuRef}>
        
        {/* Floating Popup Menu */}
        {isMenuOpen && (
          <div className="absolute bottom-full mb-3 left-0 right-0 bg-surface-container-high border border-outline-variant/20 rounded-2xl p-2 shadow-2xl animate-fade-in z-50 overflow-hidden w-[220px]">
            {/* Account Header */}
            <div className="px-3 py-2 border-b border-outline-variant/10 mb-1">
              <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest leading-none">Account</p>
              <p className="text-xs text-on-surface truncate font-semibold mt-1">[REDACTED_EMAIL]</p>
            </div>
            
            {/* Menu Items */}
            <div className="space-y-0.5">
              <button
                onClick={() => {
                  setActiveTab('Profile');
                  setIsMenuOpen(false);
                }}
                className="w-full flex items-center gap-3.5 px-3 py-2 hover:bg-surface-container-lowest rounded-xl text-xs font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-sm text-tertiary">settings</span>
                Settings
              </button>
              
              <div className="h-[1px] bg-outline-variant/10 my-1" />
              
              <button
                onClick={() => {
                  alert("Applyr v2.5 Multi-LLM Agent. All services connected and running on local SQLite.");
                  setIsMenuOpen(false);
                }}
                className="w-full flex items-center gap-3.5 px-3 py-2 hover:bg-surface-container-lowest rounded-xl text-xs font-semibold text-on-surface-variant hover:text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-sm">help</span>
                Help
              </button>
              
              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                className="w-full flex items-center gap-3.5 px-3 py-2 hover:bg-surface-container-lowest rounded-xl text-xs font-semibold text-error/80 hover:text-error transition-colors"
              >
                <span className="material-symbols-outlined text-sm">logout</span>
                Log out
              </button>
            </div>
          </div>
        )}

        {/* User Card Trigger */}
        <button
          onClick={() => setIsMenuOpen(prev => !prev)}
          className={`w-full flex items-center gap-3 p-2.5 rounded-2xl transition-all border duration-200 ${
            isMenuOpen 
              ? 'bg-surface-container border-outline-variant/30 scale-98 shadow-sm' 
              : 'border-transparent hover:bg-surface-container/60 hover:scale-[1.01]'
          }`}
        >
          {/* Avatar */}
          <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-extrabold shadow-sm">
            JT
          </div>
          {/* Name & Plan Details */}
          <div className="text-left flex-1 min-w-0">
            <p className="text-xs font-extrabold text-on-surface truncate leading-tight">soylaertes</p>
            <p className="text-[9px] font-bold text-primary uppercase tracking-wider leading-none mt-0.5">Plus</p>
          </div>
          {/* Chevron */}
          <span className="material-symbols-outlined text-on-surface-variant text-base select-none">
            {isMenuOpen ? 'expand_less' : 'expand_more'}
          </span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
