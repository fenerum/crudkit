import { Suspense, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';
import { ToastContainer } from 'react-toastify';

import { AuthProvider, useAuth } from '../context/AuthContext';
import BaseLayout from '../layouts/BaseLayout';
import ErrorBoundary from './ErrorBoundary';

import LoginScreen from './routes/login';
import { appConfig } from '../utils/appConfig';
import Dashboard from './routes/index';
import Inbox from './routes/inbox';
import AllObjects from './routes/all-objects';
import Profile from './routes/profile';
import SearchPage from './routes/search';
import SegmentIndex from './routes/segment-index';
import Create from './routes/create';
import Edit from './routes/edit';
import DeleteRoute from './routes/delete';
import Merge from './routes/merge';
import NotFound from './routes/not-found';

const queryClient = new QueryClient();

// auth_mode "saml" bounces unauthenticated users into Django's SAML flow
// (mirrors `LOGIN_URL = "/saml2/login/"` from settings.py); "password" uses
// the local username/password form at `/login`. The Vite dev server has no
// rendered config, so dev always falls back to the password form.
const useSamlRedirect = appConfig.auth_mode === 'saml';

function RequireAuth({ children }: { children: any }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (!useSamlRedirect || loading || user) return;
    const next = location.pathname + location.search;
    window.location.assign(`/saml2/login/?next=${encodeURIComponent(next)}`);
  }, [loading, user, location.pathname, location.search]);

  if (loading) return <div className="p-6 text-fg-3 text-sm animate-pulse">Loading user data…</div>;
  if (!user) {
    if (useSamlRedirect) {
      return <div className="p-6 text-fg-3 text-sm animate-pulse">Signing you in…</div>;
    }
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

function ChromeLayout() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<div className="p-6 text-fg-3 text-sm">Loading…</div>}>
        <BaseLayout />
      </Suspense>
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginScreen />} />

            <Route
              element={
                <RequireAuth>
                  <ChromeLayout />
                </RequireAuth>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="inbox" element={<Inbox />} />
              <Route path="all-objects" element={<AllObjects />} />
              <Route path="profile" element={<Profile />} />
              <Route path="search" element={<SearchPage />} />

              <Route path=":segment/create" element={<Create />} />
              <Route path=":segment/edit" element={<Edit />} />
              <Route path=":segment/delete" element={<DeleteRoute />} />
              <Route path=":segment/merge" element={<Merge />} />
              <Route path=":segment/VIW/:view" element={<SegmentIndex />} />
              <Route path=":segment" element={<SegmentIndex />} />

              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
        <ToastContainer position="bottom-right" newestOnTop closeOnClick theme="dark" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
