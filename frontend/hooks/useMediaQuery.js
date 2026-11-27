import { useSyncExternalStore } from 'react';

// Breakpoints shared with the .ck-shell rules in global.css.
export const ASSISTANT_OVERLAY_QUERY = '(max-width: 1200px)';
export const NAV_OVERLAY_QUERY = '(max-width: 900px)';

export function useMediaQuery(query) {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    () => window.matchMedia(query).matches,
  );
}
