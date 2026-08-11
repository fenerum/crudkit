// Keep in sync with the <Route> declarations in src/App.tsx and the segment
// regexes in src/routes/segment-index.tsx. Used by action-redirect handling to
// decide between React Router navigation and a full page load (for backend
// URLs like /orderform/, /admin/, etc.).
const SEGMENT = '[A-Z]{3}\\d*';
const FRONTEND_ROUTE_RES: RegExp[] = [
  /^\/$/,
  /^\/login\/?$/,
  /^\/inbox\/?$/,
  /^\/all-objects\/?$/,
  /^\/profile\/?$/,
  /^\/search\/?$/,
  new RegExp(`^\\/${SEGMENT}\\/?$`),
  new RegExp(`^\\/${SEGMENT}\\/(create|edit|delete|merge)\\/?$`),
  new RegExp(`^\\/${SEGMENT}\\/VIW\\/[^/]+\\/?$`),
];

export function isFrontendPath(path: string): boolean {
  const pathname = path.split(/[?#]/, 1)[0];
  return FRONTEND_ROUTE_RES.some((re) => re.test(pathname));
}
