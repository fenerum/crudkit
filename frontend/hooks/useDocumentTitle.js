import { useEffect } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { appConfig } from '../utils/appConfig';
import { generateBreadcrumbs } from '../utils/breadcrumbs';

export function useDocumentTitle(prefix = appConfig.app_name) {
  const { pathname } = useLocation();
  const params = useParams();

  useEffect(() => {
    const breadcrumbs = generateBreadcrumbs(pathname, params);
    const pageTitle = breadcrumbs.length > 0 ? breadcrumbs[breadcrumbs.length - 1].text : '';
    document.title = pageTitle ? `${pageTitle} - ${prefix}` : prefix;
  }, [pathname, params, prefix]);
}
