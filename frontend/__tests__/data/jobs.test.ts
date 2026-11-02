import { describe, expect, test } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { JOBS_KEY, Job, mergeJobs, receiveJob } from '../../data/jobs';
import { jobProgressText } from '../../components/JobTray';

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: 'JOB1',
    label: 'Recount',
    status: 'running',
    done: 1,
    total: 3,
    message: '',
    error: '',
    target: 'RDG1',
    started_at: '2026-11-02T10:00:00Z',
    finished_at: null,
    ...overrides,
  };
}

describe('mergeJobs', () => {
  test('updates a known task in place and keeps the newest first', () => {
    const older = job({ id: 'JOB1', started_at: '2026-11-02T09:00:00Z' });
    const newer = job({ id: 'JOB2', started_at: '2026-11-02T10:00:00Z' });
    const merged = mergeJobs([older, newer], [{ ...older, done: 2 }]);
    expect(merged.map((j) => [j.id, j.done])).toEqual([
      ['JOB2', 1],
      ['JOB1', 2],
    ]);
  });
});

describe('receiveJob', () => {
  test('refetches the record only when its task finishes', () => {
    const qc = new QueryClient();
    qc.setQueryData(['detail', 'RDG', 'RDG1'], {});
    const stale = () => qc.getQueryState(['detail', 'RDG', 'RDG1'])?.isInvalidated;

    receiveJob(qc, job());
    receiveJob(qc, job({ done: 2 }));
    expect(stale()).toBe(false);

    receiveJob(qc, job({ status: 'succeeded', done: 3, finished_at: '2026-11-02T10:00:05Z' }));
    expect(stale()).toBe(true);
    expect(qc.getQueryData<Job[]>(JOBS_KEY)).toHaveLength(1);
  });
});

describe('jobProgressText', () => {
  test.each([
    [job({ message: 'Step 1' }), '1 / 3 · Step 1'],
    [job({ total: null, done: 0 }), 'Working…'],
    [job({ status: 'failed', error: 'Ledger locked' }), 'Ledger locked'],
    [job({ status: 'succeeded' }), 'Done'],
  ])('%#', (input, text) => expect(jobProgressText(input)).toBe(text));
});
