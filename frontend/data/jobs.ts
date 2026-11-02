// Tasks (crudkit.jobs): long-running actions the signed-in person started.
// Their progress is pushed over the change stream as `job` frames and kept in
// the React Query cache under JOBS_KEY; the REST list seeds it on load and
// stands in for the socket while it is down.
import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query';
import CrudKitAPIClient from './api';
import { invalidateObject } from './invalidate';
import { useRealtimeConnected } from './realtime';

export type Job = {
  id: string;
  label: string;
  status: 'running' | 'succeeded' | 'failed';
  done: number;
  total: number | null;
  message: string;
  error: string;
  target: string | null;
  target_label?: string;
  started_at: string;
  finished_at: string | null;
};

export const JOBS_KEY = ['jobs'];
const POLL_MS = 5_000;

// Upsert `incoming` into `jobs`, newest first.
export function mergeJobs(jobs: Job[] = [], incoming: Job[]): Job[] {
  const byId = new Map(jobs.map((job) => [job.id, job]));
  incoming.forEach((job) => byId.set(job.id, { ...byId.get(job.id), ...job }));
  return [...byId.values()].sort((a, b) => b.started_at.localeCompare(a.started_at));
}

export function receiveJob(qc: QueryClient, job: Job) {
  const previous = qc.getQueryData<Job[]>(JOBS_KEY)?.find((j) => j.id === job.id);
  qc.setQueryData<Job[]>(JOBS_KEY, (jobs) => mergeJobs(jobs, [job]));
  // What the task did to its record is only worth refetching once it is done.
  if (job.status !== 'running' && previous?.status !== job.status && job.target) {
    invalidateObject(qc, job.target);
  }
}

export function dismissJob(qc: QueryClient, id: string) {
  qc.setQueryData<Job[]>(JOBS_KEY, (jobs) => (jobs || []).filter((job) => job.id !== id));
}

const client = new CrudKitAPIClient();

export function useJobs(): Job[] {
  const qc = useQueryClient();
  const connected = useRealtimeConnected();
  const { data } = useQuery({
    queryKey: JOBS_KEY,
    queryFn: async () => {
      const page = await client.list('JOB', { page_size: 10 });
      const known = qc.getQueryData<Job[]>(JOBS_KEY) || [];
      const ids = new Set(known.map((job) => job.id));
      // Update the tasks on screen; only bring in others that are still running.
      const listed = (page.results || []).filter((job: Job) => ids.has(job.id) || job.status === 'running');
      return mergeJobs(known, listed);
    },
    refetchInterval: (query) =>
      !connected && (query.state.data || []).some((job) => job.status === 'running') ? POLL_MS : false,
  });
  return data || [];
}

// The tasks working on (or done with) one record.
export function useJobsFor(target: string): Job[] {
  return useJobs().filter((job) => job.target === target);
}
