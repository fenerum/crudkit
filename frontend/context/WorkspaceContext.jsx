import { createContext, useCallback, useContext, useState } from 'react';

import { appConfig } from '../utils/appConfig';

const STORAGE_KEY = `${appConfig.storage_prefix}-workspace`;

function readInitialWorkspaceId() {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY) || null;
  } catch {
    // localStorage unavailable (private mode) — workspace just won't persist.
    return null;
  }
}

export const WorkspaceContext = createContext({
  activeWorkspaceId: null,
  setActiveWorkspaceId: () => {},
});

export function WorkspaceProvider({ children }) {
  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState(readInitialWorkspaceId);

  const setActiveWorkspaceId = useCallback((id) => {
    setActiveWorkspaceIdState(id || null);
    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        if (id) window.localStorage.setItem(STORAGE_KEY, id);
        else window.localStorage.removeItem(STORAGE_KEY);
      } catch { /* noop */ }
    }
  }, []);

  return (
    <WorkspaceContext.Provider value={{ activeWorkspaceId, setActiveWorkspaceId }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  return useContext(WorkspaceContext);
}
