import React from 'react';
import { api } from '../../lib/api';
import DocumentEditor from '../DocumentEditor';

interface JobFile {
  name: string;
}

interface AssetsSectionProps {
  jobId: string;
  jobTitle: string;
  jobCompany: string;
  jobUrl?: string | null;
  files: JobFile[];
  loadingFiles: boolean;
  editingFile: string | null;
  editingContent: string;
  pdfReloadKey: number;
  onStartEdit: (filename: string) => void;
  onClearEditingFile: () => void;
  onSaveSuccess: () => void;
}

/** Your Assets & Links — extracted from JobDetailPanel (CR-104 Story 1.7). */
const AssetsSection: React.FC<AssetsSectionProps> = ({
  jobId,
  jobTitle,
  jobCompany,
  jobUrl,
  files,
  loadingFiles,
  editingFile,
  editingContent,
  pdfReloadKey,
  onStartEdit,
  onClearEditingFile,
  onSaveSuccess,
}) => {
  const fileIcon = (name: string) => {
    if (name.endsWith('.pdf')) return 'picture_as_pdf';
    if (name.endsWith('.md'))  return 'description';
    if (name.endsWith('.json')) return 'data_object';
    return 'insert_drive_file';
  };

  return (
    <>
      <section>
        <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Your Assets & Links</h3>
        {loadingFiles ? (
          <p className="text-xs text-on-surface-variant animate-pulse">Loading files...</p>
        ) : (
          <div className="space-y-2">
            {/* Original Job URL */}
            {jobUrl && (
              <a
                href={jobUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low cursor-pointer transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-secondary-container rounded-lg">
                    <span className="material-symbols-outlined text-secondary text-base">link</span>
                  </div>
                  <span className="text-sm text-on-surface group-hover:text-secondary transition-colors">Original Job Posting</span>
                </div>
                <span className="material-symbols-outlined text-on-surface-variant text-base">open_in_new</span>
              </a>
            )}

            {/* Original JD text — viewable/editable */}
            {files.some(f => f.name === 'Original_JD.txt') && (
              <div className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low transition-colors group">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-secondary-container rounded-lg">
                    <span className="material-symbols-outlined text-secondary text-base">description</span>
                  </div>
                  <span className="text-sm text-on-surface group-hover:text-secondary transition-colors">
                    Job Description
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onStartEdit('Original_JD.txt')}
                    title="View and edit job description"
                    className="w-9 h-9 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-secondary transition-all flex items-center justify-center shrink-0"
                  >
                    <span className="material-symbols-outlined text-lg">edit</span>
                  </button>
                  <a
                    href={api(`/api/jobs/${jobId}/files/${encodeURIComponent('Original_JD.txt')}`)}
                    download="Original_JD.txt"
                    title="Download Original_JD.txt"
                    className="w-9 h-9 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-primary transition-all flex items-center justify-center shrink-0"
                  >
                    <span className="material-symbols-outlined text-lg">download</span>
                  </a>
                </div>
              </div>
            )}

            {/* PDF Assets with inline Actions */}
            {files.filter(f => f.name.endsWith('.pdf')).map(file => {
              const mdFilename = file.name.replace('.pdf', '.md');
              const hasMd = files.some(f => f.name === mdFilename);
              const isCheatSheet = /cheat.?sheet/i.test(file.name);

              return (
                <div
                  key={file.name}
                  className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary-container rounded-lg">
                      <span className="material-symbols-outlined text-primary text-base">
                        {isCheatSheet ? 'fact_check' : fileIcon(file.name)}
                      </span>
                    </div>
                    <span className="text-sm text-on-surface group-hover:text-primary transition-colors">
                      {isCheatSheet ? 'Interview Cheat Sheet' : file.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasMd && (
                      <button
                        onClick={() => onStartEdit(mdFilename)}
                        title={`Edit ${file.name.replace('.pdf', '')}`}
                        className="w-9 h-9 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-secondary transition-all flex items-center justify-center shrink-0"
                      >
                        <span className="material-symbols-outlined text-lg">edit</span>
                      </button>
                    )}
                    <a
                      href={api(`/api/jobs/${jobId}/files/${encodeURIComponent(file.name)}`)}
                      download={file.name}
                      title={`Download ${file.name}`}
                      className="w-9 h-9 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-primary transition-all flex items-center justify-center shrink-0"
                    >
                      <span className="material-symbols-outlined text-lg">download</span>
                    </a>
                  </div>
                </div>
              );
            })}

            {files.filter(f => f.name.endsWith('.pdf')).length === 0 && (
              <p className="text-xs text-on-surface-variant italic px-2 pt-2">No PDF assets generated yet.</p>
            )}
          </div>
        )}
      </section>

      {editingFile && (
        <div className="fixed inset-0 z-50 bg-surface flex overflow-hidden animate-fade-in">
          {/* Left Pane: Compiled PDF preview (50% width) — only for .md files with a .pdf counterpart */}
          {editingFile.endsWith('.md') && (
            <div className="w-1/2 h-full bg-surface-container-lowest flex flex-col relative border-r border-outline-variant/10">
              <div className="px-6 py-4 bg-surface-container-low border-b border-outline-variant/10 flex justify-between items-center">
                <div>
                  <h4 className="text-xs font-headline font-extrabold text-on-surface uppercase tracking-wider flex flex-center gap-1.5">
                    <span className="material-symbols-outlined text-primary text-base">picture_as_pdf</span>
                    PDF Preview
                  </h4>
                  <p className="text-[10px] text-on-surface-variant">Live generated asset preview</p>
                </div>
                <a
                  href={api(`/api/jobs/${jobId}/files/${editingFile.replace('.md', '.pdf')}`)}
                  download={editingFile.replace('.md', '.pdf')}
                  className="btn-secondary text-[11px] py-1.5 px-3 rounded-lg flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  Download PDF
                </a>
              </div>
              <div className="flex-1 bg-surface-container-low">
                <iframe
                  src={api(`/api/jobs/${jobId}/files/${editingFile.replace('.md', '.pdf')}?t=${pdfReloadKey}`)}
                  className="w-full h-full border-0"
                  title="PDF Preview"
                />
              </div>
            </div>
          )}

          {/* Right Pane: Toast UI rich document editor */}
          <div className={editingFile.endsWith('.md') ? 'w-1/2 h-full' : 'w-full h-full'}>
            <DocumentEditor
              jobId={jobId}
              filename={editingFile}
              initialValue={editingContent}
              jobTitle={jobTitle}
              jobCompany={jobCompany}
              onSaveSuccess={onSaveSuccess}
              onClose={onClearEditingFile}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default AssetsSection;
