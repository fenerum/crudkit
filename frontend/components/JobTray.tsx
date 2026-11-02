// The signed-in person's running tasks, bottom-left on every page. A task
// that succeeded fades out after a moment; a failed one stays until closed.
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Icon } from './ui';
import ProgressBar from './ProgressBar';
import { Job, dismissJob, useJobs } from '../data/jobs';
import { url } from '../utils/urls';

const SUCCEEDED_STAYS_MS = 5_000;

export function jobProgressText(job: Job): string {
  if (job.status === 'failed') return job.error || 'Failed';
  if (job.status === 'succeeded') return 'Done';
  const count = job.total != null ? `${job.done} / ${job.total}` : job.done > 0 ? `${job.done}` : '';
  return [count, job.message].filter(Boolean).join(' · ') || 'Working…';
}

function JobRow({ job }: { job: Job }) {
  const qc = useQueryClient();
  const finished = job.status !== 'running';

  useEffect(() => {
    if (job.status !== 'succeeded') return;
    const timer = window.setTimeout(() => dismissJob(qc, job.id), SUCCEEDED_STAYS_MS);
    return () => window.clearTimeout(timer);
  }, [job.status, job.id, qc]);

  return (
    <li className="flex flex-col gap-1.5 px-3 py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        <span className="flex-1 min-w-0 truncate text-sm font-medium text-fg-1">
          {job.label}
          {job.target && (
            <>
              <span className="text-fg-3 font-normal"> · </span>
              <Link to={url(job.target)} className="font-normal text-fg-2 hover:text-fg-1">
                {job.target_label || job.target}
              </Link>
            </>
          )}
        </span>
        {job.status === 'succeeded' && <Icon name="check" size={13} color="var(--success)" />}
        {finished && (
          <button
            type="button"
            className="ck-icon-btn ck-icon-btn-sm"
            onClick={() => dismissJob(qc, job.id)}
            aria-label={`Close ${job.label}`}
          >
            <Icon name="x" size={12} color="currentColor" />
          </button>
        )}
      </div>
      <ProgressBar done={job.done} total={job.total} status={job.status} label={job.label} />
      <span className={'text-xs truncate ' + (job.status === 'failed' ? 'text-danger' : 'text-fg-3')}>
        {jobProgressText(job)}
      </span>
    </li>
  );
}

export default function JobTray() {
  const jobs = useJobs();
  if (jobs.length === 0) return null;
  return (
    <section
      aria-label="Tasks"
      className="fixed bottom-4 left-4 lg:left-[calc(var(--sidebar-w)+16px)] z-40 w-80 max-w-[calc(100vw-32px)] rounded-lg border border-border-1 bg-bg-2 shadow-2xl"
    >
      <ul className="flex flex-col divide-y divide-border-1 max-h-72 overflow-y-auto">
        {jobs.map((job) => (
          <JobRow key={job.id} job={job} />
        ))}
      </ul>
    </section>
  );
}
