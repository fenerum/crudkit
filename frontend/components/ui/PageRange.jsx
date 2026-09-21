export default function PageRange({ page, pageSize, count }) {
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, count);
  return (
    <span className="text-xs text-fg-3">
      Showing{' '}
      {count > 0 && (
        <>
          <span className="font-mono text-fg-2">{first}</span>–
        </>
      )}
      <span className="font-mono text-fg-2">{last}</span>
      {' '}of{' '}
      <span className="font-mono text-fg-2">{count}</span>
    </span>
  );
}
