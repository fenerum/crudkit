// A task's progress: filled to done/total, or sweeping while the total is unknown.
type Props = {
  done: number;
  total: number | null;
  status?: 'running' | 'succeeded' | 'failed';
  label: string;
};

export default function ProgressBar({ done, total, status = 'running', label }: Props) {
  const known = total != null && total > 0;
  const percent = status === 'succeeded' ? 100 : known ? Math.min(100, Math.round((done / total) * 100)) : null;
  const tone = status === 'failed' ? 'bg-danger' : status === 'succeeded' ? 'bg-success' : 'bg-primary-500';
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={known ? total : undefined}
      aria-valuenow={known ? Math.min(done, total) : undefined}
      className="h-1.5 w-full overflow-hidden rounded-full bg-bg-3"
    >
      {percent == null ? (
        <div className={`ck-progress-sweep h-full w-1/3 rounded-full ${tone}`} />
      ) : (
        <div className={`h-full rounded-full transition-[width] duration-300 ${tone}`} style={{ width: `${percent}%` }} />
      )}
    </div>
  );
}
