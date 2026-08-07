import React, { useState, useRef, useEffect } from 'react';
import { Job } from '../types/job';
import { api } from '../lib/api';
import logoMark from '../assets/logo-mark.png';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  jobs: Job[];
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, jobs }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [accountLabel, setAccountLabel] = useState('Local account');
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  const menuRef = useRef<HTMLDivElement>(null);

  const toggleTheme = () => {
    const next = !isDark;
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('applyr-theme', next ? 'dark' : 'light');
    setIsDark(next);
  };

  const newJobsCount = jobs.filter(j => j.status === 'Backlog' && j.has_assets).length;

  const mainNav = [
    { name: 'Dashboard', icon: 'grid_view' },
    { name: 'Opportunities', icon: 'view_kanban' },
    { name: 'Job Search', icon: 'radar' },
    { name: 'Add Job', icon: 'post_add' },
    { name: 'Tuning Log', icon: 'tune' },
    { name: 'Settings', icon: 'account_circle' },
  ];

  useEffect(() => {
    fetch(api('/api/profile/identity'))
      .then(r => r.json())
      .then(data => {
        if (data?.email) setAccountLabel(data.email);
        else if (data?.name) setAccountLabel(data.name);
      })
      .catch(() => {});
  }, []);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
        setIsHelpOpen(false);
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
    <aside className="w-64 bg-sidebar-bg border-r border-sidebar-border flex flex-col h-full shrink-0 relative">
      {/* Brand — same h-16 row height as the top header, so the two align */}
      <div className="h-16 flex items-center gap-3 px-6 shrink-0">
        <span
          className="w-10 h-10 shrink-0"
          role="img"
          aria-label="Applyr"
          style={{
            backgroundColor: 'var(--color-logo-icon)',
            WebkitMaskImage: `url(${logoMark})`,
            maskImage: `url(${logoMark})`,
            WebkitMaskSize: 'contain',
            maskSize: 'contain',
            WebkitMaskRepeat: 'no-repeat',
            maskRepeat: 'no-repeat',
            WebkitMaskPosition: 'center',
            maskPosition: 'center',
          }}
        />
        <div>
          <h2 className="text-lg font-bold text-sidebar-text-active font-headline tracking-tight leading-tight">Applyr</h2>
          <p className="text-[10px] text-sidebar-text uppercase tracking-widest font-bold">Curated Job Search</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-6 pt-6">
        {mainNav.map((item) => (
          <button
            key={item.name}
            onClick={() => handleNavigate(item.name)}
            className={`w-full flex items-center gap-3 py-3 px-4 rounded-xl text-sm transition-all active:translate-x-1 duration-200 border ${
              activeTab === item.name
                ? 'text-sidebar-text-active font-bold border-transparent bg-sidebar-active'
                : 'text-sidebar-text border-transparent hover:text-sidebar-text-active hover:bg-sidebar-hover'
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
      <div className="mt-auto pt-6 pb-8 px-6 border-t border-sidebar-border relative" ref={menuRef}>

        {/* Floating Popup Menu */}
        {isMenuOpen && (
          <div className="absolute bottom-full mb-3 left-6 right-6 bg-sidebar-container border border-sidebar-border rounded-2xl p-2 shadow-2xl animate-fade-in z-50 overflow-hidden">
            {/* Account Header */}
            <div className="px-3 py-2 border-b border-sidebar-border mb-1">
              <p className="text-[10px] text-sidebar-text font-bold uppercase tracking-widest leading-none">Account</p>
              <p className="text-xs text-sidebar-text-active truncate font-semibold mt-1">{accountLabel}</p>
            </div>

            {/* Menu Items */}
            <div className="space-y-0.5">
              <button
                onClick={() => {
                  setActiveTab('Settings');
                  setIsMenuOpen(false);
                }}
                className="w-full flex items-center gap-3.5 px-3 py-2 hover:bg-sidebar-hover rounded-xl text-xs font-semibold text-sidebar-text hover:text-sidebar-text-active transition-colors"
              >
                <span className="material-symbols-outlined text-sm">settings</span>
                Settings
              </button>

              <div className="h-[1px] bg-sidebar-border my-1" />

              <button
                onClick={() => setIsHelpOpen(prev => !prev)}
                className="w-full flex items-center justify-between gap-3.5 px-3 py-2 hover:bg-sidebar-hover rounded-xl text-xs font-semibold text-sidebar-text hover:text-sidebar-text-active transition-colors"
              >
                <span className="flex items-center gap-3.5">
                  <span className="material-symbols-outlined text-sm">help</span>
                  Help
                </span>
                <span className="material-symbols-outlined text-sm">
                  {isHelpOpen ? 'expand_less' : 'expand_more'}
                </span>
              </button>
              {isHelpOpen && (
                <div className="px-3 pb-2 pt-1 text-[11px] text-sidebar-text leading-relaxed">
                  Applyr v2.5 Multi-LLM Agent. All services connected and running on local SQLite.
                </div>
              )}

              <button
                onClick={toggleTheme}
                className="w-full flex items-center justify-between gap-3.5 px-3 py-2 hover:bg-sidebar-hover rounded-xl text-xs font-semibold text-sidebar-text hover:text-sidebar-text-active transition-colors"
              >
                <span className="flex items-center gap-3.5">
                  <span className="material-symbols-outlined text-sm">{isDark ? 'dark_mode' : 'light_mode'}</span>
                  {isDark ? 'Dark mode' : 'Light mode'}
                </span>
                <span className={`relative w-8 h-4.5 rounded-full overflow-hidden transition-colors ${isDark ? 'bg-sidebar-active' : 'bg-sidebar-text/30'}`}>
                  <span className={`absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-transform ${isDark ? 'translate-x-3.5' : 'translate-x-0'}`} />
                </span>
              </button>

              <div className="h-[1px] bg-sidebar-border my-1" />

              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                className="w-full flex items-center gap-3.5 px-3 py-2 hover:bg-sidebar-hover rounded-xl text-xs font-semibold text-error/80 hover:text-error transition-colors"
              >
                <span className="material-symbols-outlined text-sm">restart_alt</span>
                Reset local session
              </button>
            </div>
          </div>
        )}

        {/* User Card Trigger */}
        <button
          onClick={() => setIsMenuOpen(prev => !prev)}
          className={`w-full flex items-center gap-3 p-2.5 rounded-2xl transition-all border duration-200 ${
            isMenuOpen
              ? 'bg-sidebar-container border-sidebar-border scale-98 shadow-sm'
              : 'border-transparent hover:bg-sidebar-hover hover:scale-[1.01]'
          }`}
        >
          {/* Avatar */}
          <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-on-primary text-xs font-extrabold shadow-sm">
            JT
          </div>
          {/* Name */}
          <div className="text-left flex-1 min-w-0">
            <p className="text-xs font-extrabold text-sidebar-text-active truncate leading-tight">{accountLabel}</p>
          </div>
          {/* Chevron */}
          <span className="material-symbols-outlined text-sidebar-text text-base select-none">
            {isMenuOpen ? 'expand_less' : 'expand_more'}
          </span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
