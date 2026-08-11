import { Link, useLocation } from 'react-router-dom';

export default function NotFound() {
  const { pathname } = useLocation();
  return (
    <div className="flex flex-col items-start gap-3 py-12">
      <span className="eyebrow">404</span>
      <h1 className="text-3xl font-semibold tracking-tight text-fg-1">Page not found</h1>
      <p className="text-sm text-fg-3 max-w-md">
        {pathname ? (
          <>
            No route matches <code className="ck-mono text-fg-2">{pathname}</code>. The link
            may be malformed or the record no longer exists.
          </>
        ) : (
          'The link may be malformed or the record no longer exists.'
        )}
      </p>
      <Link to="/" className="ck-btn ck-btn-secondary ck-btn-sm">
        Go home
      </Link>
    </div>
  );
}
