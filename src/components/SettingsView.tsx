import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';

interface ProfileData {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  portfolio: string;
  github: string;
}

interface PreferenceData {
  minSalary: number;
  environment: string;
  titleBlocklist: string;
  industryBlocklist: string;
}

interface LlmSettings {
  provider: 'gemini' | 'claude' | 'local';
  geminiApiKey: string;
  claudeApiKey: string;
  localUrl: string;
  localModel: string;
}

interface StatsData {
  total: number;
  byStatus: { status: string; count: number }[];
  byRejectionStage: { rejection_stage: string; count: number }[];
  byRejectionType: { rejection_type: string; count: number }[];
}

const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('Profile');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // Unified States
  const [profile, setProfile] = useState<ProfileData>({
    name: '', email: '', phone: '', location: '', linkedin: '', portfolio: '', github: ''
  });
  const [preferences, setPreferences] = useState<PreferenceData>({
    minSalary: 0, environment: 'Remote', titleBlocklist: '', industryBlocklist: ''
  });
  const [llmSettings, setLlmSettings] = useState<LlmSettings>({
    provider: 'gemini',
    geminiApiKey: '',
    claudeApiKey: '',
    localUrl: 'http://localhost:11434',
    localModel: 'llama3',
  });
  const [experience, setExperience] = useState('');
  const [experienceDirty, setExperienceDirty] = useState(false);
  const [stats, setStats] = useState<StatsData | null>(null);

  // Debounce Ref
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch all profile/preference/experience/stats datasets on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileRes, prefRes, expRes, statsRes, llmRes] = await Promise.all([
          fetch(api('/api/profile/identity')),
          fetch(api('/api/profile/preferences')),
          fetch(api('/api/experience')),
          fetch(api('/api/jobs/stats')),
          fetch(api('/api/profile/llm_settings')),
        ]);

        const [profileData, prefData, expData, statsData, llmData] = await Promise.all([
          profileRes.json(),
          prefRes.json(),
          expRes.json(),
          statsRes.json(),
          llmRes.json(),
        ]);

        if (profileData && typeof profileData === 'object') {
          setProfile(prev => ({ ...prev, ...profileData }));
        }
        if (prefData && typeof prefData === 'object') {
          setPreferences(prev => ({ ...prev, ...prefData }));
        }
        setExperience(expData.content ?? '');
        if (statsData && !statsData.error) {
          setStats(statsData);
        }
        if (llmData && llmData.provider) {
          setLlmSettings(prev => ({ ...prev, ...llmData }));
        }
      } catch (err) {
        console.error('Failed to load SettingsView configurations:', err);
      }
    };

    loadData();
  }, []);

  // Debounced auto-saving function
  const debouncedSave = useCallback((key: string, data: any) => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    setSaveStatus('saving');
    debounceTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(api(`/api/profile/${key}`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
        if (res.ok) {
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus('idle'), 2000);
        } else {
          setSaveStatus('error');
        }
      } catch {
        setSaveStatus('error');
      }
    }, 1000);
  }, []);

  const saveExperience = async () => {
    setSaveStatus('saving');
    try {
      const res = await fetch(api('/api/experience'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: experience }),
      });
      if (res.ok) {
        setExperienceDirty(false);
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        setSaveStatus('error');
      }
    } catch {
      setSaveStatus('error');
    }
  };

  const tabs = [
    { id: 'Profile', icon: 'account_circle' },
    { id: 'Job Preferences', icon: 'tune' },
    { id: 'Experience', icon: 'work' },
    { id: 'API or Connections', icon: 'hub' },
    { id: 'Analytics', icon: 'analytics' },
  ];

  return (
    <div className="flex flex-col md:flex-row gap-8 min-h-[calc(100vh-12rem)] animate-fade-in text-on-surface">
      
      {/* Left Sidebar Menu */}
      <div className="w-full md:w-64 shrink-0 flex flex-col gap-4">
        <div className="bg-surface-container-lowest border border-outline-variant/10 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-base font-headline font-extrabold text-on-surface tracking-tight">Settings</h2>
            {saveStatus === 'saving' && (
              <span className="text-[10px] bg-secondary/10 text-secondary border border-secondary/20 font-bold px-2 py-0.5 rounded-full animate-pulse">Saving...</span>
            )}
            {saveStatus === 'saved' && (
              <span className="text-[10px] bg-primary/10 text-primary border border-primary/20 font-bold px-2 py-0.5 rounded-full animate-fade-in">Saved</span>
            )}
          </div>
          <nav className="space-y-1.5">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 py-2.5 px-4 rounded-xl text-xs font-semibold transition-all duration-200 text-left ${
                  activeTab === tab.id
                    ? 'bg-primary/10 text-primary border-l-2 border-primary'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low'
                }`}
              >
                <span className="material-symbols-outlined text-base leading-none">{tab.icon}</span>
                {tab.id}
                {tab.id === 'Experience' && experienceDirty && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-secondary" title="Unsaved changes"></span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Informational Card */}
        <div className="bg-surface-container-low/60 border border-outline-variant/10 rounded-2xl p-5 text-[11px] text-on-surface-variant leading-relaxed">
          <p className="font-bold mb-1 text-on-surface">Local Workspace Mode</p>
          All configurations save automatically and reside inside your secure, local-first SQLite database.
        </div>
      </div>

      {/* Right Content Workspace */}
      <div className="flex-1 bg-surface-container-lowest border border-outline-variant/10 rounded-2xl p-8 shadow-sm">
        
        {/* Profile Tab */}
        {activeTab === 'Profile' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h3 className="text-base font-headline font-bold text-on-surface">Professional Profile</h3>
              <p className="text-xs text-on-surface-variant mt-1">Configure your personal contact details, portfolio sites, and code links used for matching.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-4 border-t border-outline-variant/10">
              {[
                { label: 'Full Name', key: 'name', type: 'text', placeholder: 'Jason Taylor' },
                { label: 'Email Address', key: 'email', type: 'email', placeholder: '[REDACTED_EMAIL]' },
                { label: 'Phone Number', key: 'phone', type: 'text', placeholder: '+1 (555) 019-2834' },
                { label: 'Location', key: 'location', type: 'text', placeholder: 'City, State' },
                { label: 'LinkedIn URL', key: 'linkedin', type: 'text', placeholder: 'https://linkedin.com/in/...' },
                { label: 'Portfolio Link', key: 'portfolio', type: 'text', placeholder: 'https://portfolio.me' },
              ].map(({ label, key, type, placeholder }) => (
                <div key={key} className="space-y-1.5">
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">{label}</label>
                  <input
                    type={type}
                    value={(profile as any)[key] ?? ''}
                    placeholder={placeholder}
                    onChange={(e) => {
                      const next = { ...profile, [key]: e.target.value };
                      setProfile(next);
                      debouncedSave('identity', next);
                    }}
                    className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors"
                  />
                </div>
              ))}
              <div className="md:col-span-2 space-y-1.5">
                <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">GitHub Profile Link</label>
                <input
                  type="text"
                  value={profile.github ?? ''}
                  placeholder="https://github.com/..."
                  onChange={(e) => {
                    const next = { ...profile, github: e.target.value };
                    setProfile(next);
                    debouncedSave('identity', next);
                  }}
                  className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors"
                />
              </div>
            </div>
          </div>
        )}

        {/* Job Preferences Tab */}
        {activeTab === 'Job Preferences' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h3 className="text-base font-headline font-bold text-on-surface">Search & Evaluation Parameters</h3>
              <p className="text-xs text-on-surface-variant mt-1">Fine-tune the scoring thresholds, preferred work environments, and keyword filters.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-4 border-t border-outline-variant/10">
              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Minimum Target Salary</label>
                <input
                  type="number"
                  value={preferences.minSalary}
                  onChange={(e) => {
                    const next = { ...preferences, minSalary: Number(e.target.value) };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors"
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Default Work Setting</label>
                <select
                  value={preferences.environment}
                  onChange={(e) => {
                    const next = { ...preferences, environment: e.target.value };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors cursor-pointer"
                >
                  <option value="On-site">On-site</option>
                  <option value="Hybrid">Hybrid</option>
                  <option value="Remote">Remote</option>
                </select>
              </div>
              <div className="md:col-span-2 space-y-1.5">
                <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Title Keyword Blocklist</label>
                <input
                  type="text"
                  value={preferences.titleBlocklist ?? ''}
                  placeholder="e.g., Senior, Manager, Director (comma-separated)"
                  onChange={(e) => {
                    const next = { ...preferences, titleBlocklist: e.target.value };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors"
                />
              </div>
              <div className="md:col-span-2 space-y-1.5">
                <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Industry & Sector Blocklist</label>
                <input
                  type="text"
                  value={preferences.industryBlocklist ?? ''}
                  placeholder="e.g., Crypto, Betting, Casino (comma-separated)"
                  onChange={(e) => {
                    const next = { ...preferences, industryBlocklist: e.target.value };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 transition-colors"
                />
              </div>
            </div>
          </div>
        )}

        {/* Experience Tab */}
        {activeTab === 'Experience' && (
          <div className="space-y-6 flex flex-col h-full min-h-[450px] animate-fade-in">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-headline font-bold text-on-surface">Master Career Experience File</h3>
                <p className="text-xs text-on-surface-variant mt-1">Your core raw text work history stored in <code className="bg-surface-container-low px-1 py-0.5 rounded text-[10px] font-mono">data/workExperience.md</code>.</p>
              </div>
              <button
                onClick={saveExperience}
                disabled={!experienceDirty || saveStatus === 'saving'}
                className={`text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-1.5 transition-all ${
                  experienceDirty
                    ? 'bg-primary text-on-primary hover:bg-primary-dim shadow-sm cursor-pointer'
                    : 'bg-surface-container-low border border-outline-variant/10 text-on-surface-variant cursor-not-allowed'
                }`}
              >
                <span className="material-symbols-outlined text-sm">save</span>
                Save & Sync AI
              </button>
            </div>
            <div className="flex-1 bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden min-h-[300px] flex flex-col pt-2">
              <textarea
                value={experience}
                onChange={(e) => { setExperience(e.target.value); setExperienceDirty(true); }}
                className="w-full flex-1 bg-transparent px-6 py-4 text-xs font-mono leading-relaxed text-on-surface focus:outline-none applyr-scrollbar resize-none h-full"
                spellCheck={false}
              />
            </div>
          </div>
        )}

        {/* API or Connections Tab */}
        {activeTab === 'API or Connections' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h3 className="text-base font-headline font-bold text-on-surface">Active LLM Provider</h3>
              <p className="text-xs text-on-surface-variant mt-1">Select the intelligence engine used for job description parsing, fit evaluation, and drafting assets.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-outline-variant/10">
              {[
                { id: 'gemini', name: 'Google Gemini', desc: 'Default fast cloud model', icon: 'google' },
                { id: 'claude', name: 'Anthropic Claude', desc: 'Premium reasoning cloud model', icon: 'psychology' },
                { id: 'local', name: 'Local LLM (Ollama)', desc: 'Privacy-focused execution', icon: 'terminal' }
              ].map((prov) => (
                <button
                  key={prov.id}
                  onClick={() => {
                    const next = { ...llmSettings, provider: prov.id as any };
                    setLlmSettings(next);
                    debouncedSave('llm_settings', next);
                  }}
                  className={`p-5 rounded-2xl border text-left transition-all relative overflow-hidden flex flex-col justify-between h-32 ${
                    llmSettings.provider === prov.id
                      ? 'bg-primary/5 border-primary shadow-sm scale-98'
                      : 'border-outline-variant/20 bg-surface-container-low hover:bg-surface-container hover:border-outline-variant/40'
                  }`}
                >
                  <div className="flex justify-between items-start w-full">
                    <span className="material-symbols-outlined text-primary text-lg">{prov.icon}</span>
                    {llmSettings.provider === prov.id && (
                      <span className="material-symbols-outlined text-primary text-base" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-bold text-on-surface leading-tight">{prov.name}</p>
                    <p className="text-[10px] text-on-surface-variant mt-1 leading-snug">{prov.desc}</p>
                  </div>
                </button>
              ))}
            </div>

            {/* Dynamic Settings Fields */}
            <div className="pt-4 border-t border-outline-variant/10 space-y-5">
              {llmSettings.provider === 'gemini' && (
                <div className="space-y-1.5">
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Gemini API Key</label>
                  <input
                    type="password"
                    value={llmSettings.geminiApiKey ?? ''}
                    onChange={(e) => {
                      const next = { ...llmSettings, geminiApiKey: e.target.value };
                      setLlmSettings(next);
                      debouncedSave('llm_settings', next);
                    }}
                    className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 font-mono"
                    placeholder="AIzaSy..."
                  />
                  <p className="text-[9px] text-on-surface-variant italic">Auto-saves to database instantly on change.</p>
                </div>
              )}

              {llmSettings.provider === 'claude' && (
                <div className="space-y-1.5">
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Claude API Key</label>
                  <input
                    type="password"
                    value={llmSettings.claudeApiKey ?? ''}
                    onChange={(e) => {
                      const next = { ...llmSettings, claudeApiKey: e.target.value };
                      setLlmSettings(next);
                      debouncedSave('llm_settings', next);
                    }}
                    className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 font-mono"
                    placeholder="sk-ant-api03..."
                  />
                  <p className="text-[9px] text-on-surface-variant italic">Auto-saves to database instantly on change.</p>
                </div>
              )}

              {llmSettings.provider === 'local' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Local Endpoint Base URL</label>
                    <input
                      type="text"
                      value={llmSettings.localUrl ?? ''}
                      onChange={(e) => {
                        const next = { ...llmSettings, localUrl: e.target.value };
                        setLlmSettings(next);
                        debouncedSave('llm_settings', next);
                      }}
                      className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 font-mono"
                      placeholder="http://localhost:11434"
                    />
                    <p className="text-[9px] text-on-surface-variant italic">Use http://localhost:11434 for Ollama or http://localhost:1234/v1 for LM Studio.</p>
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Model Identifier / Name</label>
                    <input
                      type="text"
                      value={llmSettings.localModel ?? ''}
                      onChange={(e) => {
                        const next = { ...llmSettings, localModel: e.target.value };
                        setLlmSettings(next);
                        debouncedSave('llm_settings', next);
                      }}
                      className="w-full text-xs px-4 py-2.5 rounded-xl bg-surface-container-low border border-outline-variant/10 text-on-surface focus:outline-none focus:border-primary/40 font-mono"
                      placeholder="llama3"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'Analytics' && (
          <div className="space-y-6 animate-fade-in">
            <div>
              <h3 className="text-base font-headline font-bold text-on-surface">Pipeline Analytics</h3>
              <p className="text-xs text-on-surface-variant mt-1">Real-time statistics on your job search status and application throughput.</p>
            </div>

            {stats ? (
              <div className="space-y-6 pt-4 border-t border-outline-variant/10">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-surface-container-low border border-outline-variant/10 p-5 rounded-2xl">
                    <p className="text-[9px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Total Leads</p>
                    <p className="text-2xl font-headline font-extrabold text-primary">{stats.total}</p>
                  </div>
                  <div className="bg-surface-container-low border border-outline-variant/10 p-5 rounded-2xl text-error">
                    <p className="text-[9px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Rejected</p>
                    <p className="text-2xl font-headline font-extrabold">{stats.byRejectionType.find(t => t.rejection_type === 'Rejected')?.count || 0}</p>
                  </div>
                  <div className="bg-surface-container-low border border-outline-variant/10 p-5 rounded-2xl text-on-surface-variant">
                    <p className="text-[9px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Ghosted</p>
                    <p className="text-2xl font-headline font-extrabold">{stats.byRejectionType.find(t => t.rejection_type === 'Ghosted')?.count || 0}</p>
                  </div>
                  <div className="bg-surface-container-low border border-outline-variant/10 p-5 rounded-2xl text-primary">
                    <p className="text-[9px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Active</p>
                    <p className="text-2xl font-headline font-extrabold">{stats.byStatus.find(s => s.status === 'Ready to Apply' || s.status === 'Backlog')?.count || 0}</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="bg-surface-container-low border border-outline-variant/10 p-6 rounded-2xl">
                    <h4 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-4">By Submission Status</h4>
                    <div className="space-y-3">
                      {stats.byStatus.map((row, i) => (
                        <div key={i} className="flex justify-between items-center text-xs">
                          <span className="text-on-surface-variant font-medium">{row.status}</span>
                          <span className="font-bold text-on-surface bg-surface-container-lowest px-2.5 py-1 rounded-lg border border-outline-variant/10">{row.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="bg-surface-container-low border border-outline-variant/10 p-6 rounded-2xl">
                    <h4 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-4">By Rejection Stage</h4>
                    <div className="space-y-3">
                      {stats.byRejectionStage.map((row, i) => (
                        <div key={i} className="flex justify-between items-center text-xs">
                          <span className="text-on-surface-variant font-medium">{row.rejection_stage || 'N/A'}</span>
                          <span className="font-bold text-on-surface bg-surface-container-lowest px-2.5 py-1 rounded-lg border border-outline-variant/10">{row.count}</span>
                        </div>
                      ))}
                      {stats.byRejectionStage.length === 0 && (
                        <p className="text-xs italic text-on-surface-variant py-4">No rejection stage telemetry logged yet.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-10 bg-surface-container-low border border-outline-variant/10 rounded-2xl text-center text-xs text-on-surface-variant animate-pulse">
                Loading pipeline statistics...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsView;
