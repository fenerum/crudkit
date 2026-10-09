import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRealtimeConnected } from '../data/realtime';
import { appConfig } from '../utils/appConfig';
import { useBreadcrumbs } from './useBreadcrumbs';
import { viewBadgeQuery } from './useMenuViews';

export function useDocumentTitle(prefix = appConfig.app_name) {
  const { crumbs, view } = useBreadcrumbs();
  const last = crumbs[crumbs.length - 1];
  const onView = !!last?.viewId && !!view;

  const realtimeConnected = useRealtimeConnected();
  const { data: badge } = useQuery({
    ...viewBadgeQuery(view || {}, realtimeConnected),
    enabled: onView && !!view.show_badge_in_menu,
  });

  let pageTitle = last?.text || '';
  if (onView && view.show_badge_in_menu && typeof badge?.count === 'number') {
    pageTitle = `(${badge.count}) ${pageTitle}`;
  }

  useEffect(() => {
    document.title = pageTitle ? `${pageTitle} - ${prefix}` : prefix;
  }, [pageTitle, prefix]);
}
