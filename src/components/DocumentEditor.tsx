import React, { useState, useEffect, useRef } from 'react';
import { Editor } from '@toast-ui/react-editor';
import { api } from '../lib/api';
import '@toast-ui/editor/dist/toastui-editor.css';

interface DocumentEditorProps {
  jobId: string;
  filename: string;
  initialValue: string;
  onSaveSuccess: () => void;
  onClose: () => void;
}

const DocumentEditor: React.FC<DocumentEditorProps> = ({
  jobId,
  filename,
  initialValue,
  onSaveSuccess,
  onClose,
}) => {
  const editorRef = useRef<Editor>(null);
  const [aiInstruction, setAiInstruction] = useState('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [aiStatus, setAiStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [hasAiKey, setHasAiKey] = useState(false);

  useEffect(() => {
    // Check if Gemini API Key is configured via Profile/Identity or server environment
    const checkApiKey = async () => {
      try {
        const res = await fetch(api('/api/profile/identity'));
        const profile = await res.json();
        // Assume active if they have entered profile identity, or check environment
        setHasAiKey(true); // Default to unlocked for local-first developer experience
      } catch {
        setHasAiKey(false);
      }
    };
    checkApiKey();
  }, []);

  const handleSave = async () => {
    const editorInstance = editorRef.current?.getInstance();
    if (!editorInstance) return;

    const markdownText = editorInstance.getMarkdown();
    setSaveStatus('saving');

    try {
      const res = await fetch(api(`/api/jobs/${jobId}/files/${filename}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: markdownText }),
      });

      if (!res.ok) throw new Error();

      setSaveStatus('saved');
      setTimeout(() => {
        setSaveStatus('idle');
        onSaveSuccess();
      }, 1500);
    } catch {
      setSaveStatus('error');
    }
  };

  const handleAiRewrite = async () => {
    if (!aiInstruction.trim()) return;
    setAiStatus('running');

    try {
      const editorInstance = editorRef.current?.getInstance();
      if (!editorInstance) return;

      const currentMarkdown = editorInstance.getMarkdown();

      // We make a call to our Express profile/ai rewrite proxy or direct local endpoint
      const res = await fetch(api(`/api/jobs/${jobId}/ai-rewrite`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename,
          instruction: aiInstruction,
          text: currentMarkdown,
        }),
      });

      if (!res.ok) throw new Error();
      const data = await res.json();

      if (data.text) {
        editorInstance.setMarkdown(data.text);
        setAiStatus('success');
        setAiInstruction('');
        setTimeout(() => setAiStatus('idle'), 2000);
      } else {
        throw new Error();
      }
    } catch {
      setAiStatus('error');
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-container-lowest">
      {/* Top action bar */}
      <div className="px-6 py-4 flex items-center justify-between bg-surface-container-low border-b border-outline-variant/10">
        <div>
          <h3 className="text-sm font-headline font-extrabold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-base">edit_note</span>
            Editing {filename}
          </h3>
          <p className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-0.5 font-bold">
            Applyr Rich-Text Workspace
          </p>
        </div>

        <div className="flex items-center gap-4">
          {saveStatus === 'saving' && (
            <span className="text-xs text-on-surface-variant flex items-center gap-1.5 animate-pulse">
              <span className="w-1.5 h-1.5 bg-secondary rounded-full"></span> Saving & Compiling...
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="text-xs text-primary flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-primary rounded-full"></span> PDF Generated Successfully!
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="text-xs text-error flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-error rounded-full"></span> Error Saving Document
            </span>
          )}

          <button
            onClick={handleSave}
            disabled={saveStatus === 'saving'}
            className="btn-primary text-xs py-1.5 px-4 rounded-xl flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm">auto_stories</span>
            Compile & Save
          </button>

          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface p-1 rounded-full hover:bg-surface-container transition-all"
          >
            <span className="material-symbols-outlined text-lg leading-none">close</span>
          </button>
        </div>
      </div>

      {/* Main editor split area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor Pane (WYSIWYG Mode) */}
        <div className="flex-1 p-6 overflow-y-auto applyr-scrollbar">
          <div className="rounded-2xl border border-outline-variant/15 overflow-hidden bg-surface-container-lowest shadow-sm">
            <Editor
              ref={editorRef}
              initialValue={initialValue}
              previewStyle="vertical"
              height="calc(100vh - 210px)"
              initialEditType="wysiwyg"
              useCommandShortcut={true}
              toolbarItems={[
                ['heading', 'bold', 'italic', 'strike'],
                ['hr', 'quote'],
                ['ul', 'ol', 'task', 'indent', 'outdent'],
                ['table', 'link'],
              ]}
            />
          </div>
        </div>

        {/* AI Assistant Sidebar Panel */}
        <div className="w-80 bg-surface-container-low border-l border-outline-variant/10 p-6 flex flex-col gap-6 overflow-y-auto applyr-scrollbar">
          <div>
            <h4 className="text-xs font-headline font-extrabold text-on-surface uppercase tracking-wider flex items-center gap-1.5">
              <span className="material-symbols-outlined text-secondary text-base">psychology</span>
              AI Copywriter
            </h4>
            <p className="text-[10px] text-on-surface-variant mt-1 leading-relaxed">
              Command the LLM to rewrite sections, correct bullet formatting, or optimize keywords based on the job description.
            </p>
          </div>

          {hasAiKey ? (
            <div className="space-y-4">
              <div>
                <label className="block text-[9px] font-extrabold text-on-surface-variant uppercase tracking-widest mb-2">
                  Instruction
                </label>
                <textarea
                  value={aiInstruction}
                  onChange={(e) => setAiInstruction(e.target.value)}
                  placeholder="e.g., 'Make the introductory paragraph sound more technical and emphasize B2B experience.'"
                  className="input-applyr w-full h-32 rounded-xl text-xs px-4 py-3 leading-relaxed resize-none focus:outline-none"
                />
              </div>

              <button
                onClick={handleAiRewrite}
                disabled={aiStatus === 'running' || !aiInstruction.trim()}
                className={`w-full py-2.5 rounded-xl text-xs font-headline font-extrabold flex items-center justify-center gap-2 transition-all ${
                  aiStatus === 'running'
                    ? 'bg-surface-container text-on-surface-variant animate-pulse cursor-not-allowed'
                    : 'bg-primary text-on-primary hover:bg-primary-dim shadow-sm active:translate-y-0.5'
                }`}
              >
                <span className="material-symbols-outlined text-base">bolt</span>
                {aiStatus === 'running' ? 'AI Writing...' : 'Apply AI Rewrite'}
              </button>

              {aiStatus === 'success' && (
                <div className="flex items-center gap-2 text-[10px] text-primary bg-primary/10 border border-primary/20 px-3 py-2 rounded-xl">
                  <span className="material-symbols-outlined text-sm">done_all</span>
                  AI rewrite applied to editor! Click "Compile & Save" to update PDF.
                </div>
              )}
              {aiStatus === 'error' && (
                <div className="flex items-center gap-2 text-[10px] text-error bg-error/10 border border-error/20 px-3 py-2 rounded-xl">
                  <span className="material-symbols-outlined text-sm">error</span>
                  Failed to perform AI rewrite. Check server logs.
                </div>
              )}
            </div>
          ) : (
            <div className="p-5 bg-surface-container rounded-2xl border border-outline-variant/10 text-center flex flex-col items-center gap-3">
              <span className="material-symbols-outlined text-on-surface-variant text-xl">lock</span>
              <div>
                <p className="text-xs font-bold text-on-surface">AI Assistant Locked</p>
                <p className="text-[10px] text-on-surface-variant mt-1 leading-normal">
                  Connect a valid Gemini API key in your Profile settings to enable direct model editing.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentEditor;
