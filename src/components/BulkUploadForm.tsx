import React, { useState, useRef, DragEvent } from 'react';
import Papa from 'papaparse';

export interface ParsedJob {
  company: string;
  jd: string;
  url?: string;
}

interface BulkUploadFormProps {
  onBatchRun: (jobs: ParsedJob[]) => void;
  isLoading: boolean;
}

const BulkUploadForm: React.FC<BulkUploadFormProps> = ({ onBatchRun, isLoading }) => {
  const [dragActive, setDragActive] = useState(false);
  const [parsedJobs, setParsedJobs] = useState<ParsedJob[]>([]);
  const [errorMsg, setErrorMsg] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file: File) => {
    if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
      setErrorMsg('Please upload a valid .csv file');
      return;
    }

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const validJobs = results.data.filter((row: any) =>
          row.Company || row.company || row['Company Name']
        );

        if (validJobs.length === 0) {
          setErrorMsg('Could not find a valid Company column in the CSV. Make sure you have headers.');
          setParsedJobs([]);
          return;
        }

        const mapped = validJobs.map((row: any) => ({
          company: row.Company || row.company || row['Company Name'] || '',
          jd: row['Job Description'] || row.JD || row.jd || row.description || '',
          url: row.URL || row.url || row.Link || row.url_string || ''
        }));

        setParsedJobs(mapped);
        setErrorMsg('');
      },
      error: () => setErrorMsg('Failed to parse CSV file.')
    });
  };

  return (
    <div className="space-y-6">
      {!parsedJobs.length ? (
        <div
          className={`w-full h-[400px] flex flex-col items-center justify-center border-2 border-dashed rounded-2xl transition-colors cursor-pointer ${dragActive ? 'border-primary bg-primary-container/20' : 'border-outline-variant bg-surface-container-lowest hover:border-primary/30'}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
             ref={inputRef}
             type="file"
             accept=".csv"
             className="hidden"
             onChange={handleChange}
          />
          <div className="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center mb-4">
            <span className="material-symbols-outlined text-3xl text-on-surface-variant">upload_file</span>
          </div>
          <h3 className="text-lg font-headline font-bold text-on-surface">Upload CSV</h3>
          <p className="text-sm text-on-surface-variant mt-2 max-w-xs text-center">
            Drag and drop your spreadsheet here, or click to browse.
          </p>
          <div className="text-[10px] text-on-surface-variant uppercase tracking-widest mt-8 space-y-1 text-center font-medium">
            <p>Required Column: Company</p>
            <p>Optional: Job Description, URL</p>
          </div>

          {errorMsg && (
            <div className="mt-6 px-4 py-2 bg-error/10 border border-error/20 text-error text-xs rounded-xl">
              {errorMsg}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-surface-container-lowest rounded-2xl p-6 space-y-6 editorial-shadow">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-headline font-bold text-primary">CSV Parsed Successfully</h3>
              <p className="text-sm text-on-surface-variant mt-1">Found {parsedJobs.length} potential matching jobs.</p>
            </div>
            <button
               onClick={() => setParsedJobs([])}
               className="text-xs text-on-surface-variant hover:text-on-surface transition-colors"
               disabled={isLoading}
            >
              Clear & re-upload
            </button>
          </div>

          <div className="max-h-[300px] overflow-y-auto space-y-2 border-y border-outline-variant/10 py-4 sanctuary-scrollbar">
             {parsedJobs.slice(0, 5).map((job, idx) => (
                <div key={idx} className="flex gap-4 p-3 bg-surface-container-low rounded-xl">
                  <div className="w-[120px] font-bold text-sm truncate text-on-surface">{job.company}</div>
                  <div className="flex-1 text-xs text-on-surface-variant truncate">
                    {job.jd ? 'Has Description' : 'No description'} {job.url && '· Has URL'}
                  </div>
                </div>
             ))}
             {parsedJobs.length > 5 && (
                <div className="text-center text-xs text-on-surface-variant py-2">
                  + {parsedJobs.length - 5} more jobs
                </div>
             )}
          </div>

          <button
            onClick={() => onBatchRun(parsedJobs)}
            disabled={isLoading}
            className="w-full btn-primary h-12 flex items-center justify-center gap-2"
          >
            {isLoading ? (
               <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <span className="material-symbols-outlined text-base">check_circle</span>
                Run {parsedJobs.length} jobs in batch
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default BulkUploadForm;
