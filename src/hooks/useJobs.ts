import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Job } from '../types/job';
import { fetchJobs } from '../lib/api';

const POLL_INTERVAL_MS = 5000;

export function useJobs() {
    const queryClient = useQueryClient();
    const [selectedJob, setSelectedJob] = useState<Job | null>(null);

    const { data: jobs = [], isLoading } = useQuery<Job[]>({
        queryKey: ['jobs'],
        queryFn: async () => (await fetchJobs()) as Job[],
        refetchInterval: POLL_INTERVAL_MS,
        staleTime: POLL_INTERVAL_MS,
    });

    const isLoaded = !isLoading;

    const handleStatusChange = useCallback(async (_id: string, _newStatus: string) => {
        setSelectedJob(null);
        // Invalidate so applied_at (and other status-side fields) stay in sync
        await queryClient.invalidateQueries({ queryKey: ['jobs'] });
    }, [queryClient]);

    return { jobs, isLoaded, selectedJob, setSelectedJob, handleStatusChange };
}
