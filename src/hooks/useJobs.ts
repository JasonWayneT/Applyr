import { useState, useEffect, useCallback } from 'react';
import { Job } from '../types/job';
import { fetchJobs } from '../lib/api';

const POLL_INTERVAL_MS = 5000;

export function useJobs() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [isLoaded, setIsLoaded] = useState(false);
    const [selectedJob, setSelectedJob] = useState<Job | null>(null);

    useEffect(() => {
        fetchJobs().then(data => {
            setJobs(data as Job[]);
            setIsLoaded(true);
        });
        const interval = setInterval(async () => {
            setJobs((await fetchJobs()) as Job[]);
        }, POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, []);

    const handleStatusChange = useCallback(async (id: string, newStatus: string) => {
        setSelectedJob(null);
        // Refetch so applied_at (and other status-side fields) stay in sync
        try {
            setJobs((await fetchJobs()) as Job[]);
        } catch {
            setJobs(prev => prev.map(j => j.id === id ? { ...j, status: newStatus as Job['status'] } : j));
        }
    }, []);

    return { jobs, isLoaded, selectedJob, setSelectedJob, handleStatusChange };
}
