import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { appConfig } from '../../utils/appConfig';

const STORAGE_KEY = `${appConfig.storage_prefix}-theme`;

function readInitialTheme() {
  if (typeof window === 'undefined' || !window.localStorage) return 'dark';
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage unavailable (private mode) — fall through.
  }
  return 'dark';
}

// Pre-paint: set the data-theme attribute as soon as this module loads, so
// React renders against the correct CSS variables on the very first paint and
// users don't see a dark→light flash.
if (typeof document !== 'undefined') {
  try {
    document.documentElement.dataset.theme = readInitialTheme();
  } catch {
    /* noop */
  }
}

export const ThemeContext = createContext({
  theme: 'dark',
  setTheme: () => {},
  toggleTheme: () => {},
});

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readInitialTheme);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = theme;
    }
    if (typeof window !== 'undefined' && window.localStorage) {
      try { window.localStorage.setItem(STORAGE_KEY, theme); } catch { /* noop */ }
    }
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (next === 'light' || next === 'dark') setThemeState(next);
  }, []);
  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
