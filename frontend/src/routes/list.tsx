import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import CrudKitAPIClient from '../../data/api';
import ObjectList from '../../components/ObjectList';
import Gallery from '../../components/Gallery';
import KanbanBoard from '../../components/Kanban';
import Swimlane from '../../components/Swimlane';
import QuadrantView from '../../components/QuadrantView';
import ConversationList from '../../components/ConversationList';
import { Icon, Kbd, OverflowMenu, PageHeader, useScreenContext } from '../../components/ui';
import PageSearch from '../../components/PageSearch';
import { useHotkeys } from 'react-hotkeys-hook';
import { url } from '../../utils/urls';
import { getStoredPageSize, storePageSize } from '../../utils/pageSize';
import { isVisibleToUser } from '../../hooks/useMenuViews';
import { useAuth } from '../../context/AuthContext';
import { useRealtimeConnected } from '../../data/realtime';
import { visibleView } from '../../utils/visibleView';

export default function List() {
  const { segment: type, view: viewId } = useParams() as { segment: string; view?: string };
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const { user } = useAuth();
  const realtimeConnected = useRealtimeConnected();

  const [isRefreshing, setIsRefreshing] = useState(false);
  const pageParam = searchParams.get('page');
  const [currentPage, setCurrentPage] = useState(pageParam ? parseInt(pageParam, 10) : 1);
  const qStr = searchParams.get('q') || '';
  const pageSizeParam = searchParams.get('page_size');
  const pageSize = pageSizeParam ? parseInt(pageSizeParam, 10) : getStoredPageSize('list');

  // Build extra query filters from URL params, excluding the reserved keys.
  const extraQuery = useMemo(() => {
    const result: Record<string, string> = {};
    searchParams.forEach((value, key) => {
      if (key === 'page' || key === 'q' || key === 'page_size') return;
      result[key] = value;
    });
    return result;
  }, [searchParams]);

  const currentUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (pageParam) params.set('page', pageParam);
    Object.entries(extraQuery).forEach(([k, v]) => v && params.set(k, v));
    const qs = params.toString();
    const baseUrl = viewId ? `/${type}/VIW/${viewId}` : `/${type}`;
    return qs ? `${baseUrl}?${qs}` : baseUrl;
  }, [type, viewId, pageParam, extraQuery]);

  useHotkeys('n', () => {
    if (type) navigate(url(type, 'create', { next: currentUrl }));
  });

  const { data: metadata, isPending: isMetadataLoading } = useQuery({
    queryKey: ['metadata', type],
    queryFn: () => client.metadata(type),
  });

  const { data: currentView, isPending: isViewLoading } = useQuery({
    queryKey: ['view', type, viewId, user?.id],
    queryFn: async () => {
      if (viewId) return await client.retrieve('VIW', viewId);
      const viewsList = await client.list('VIW', { model: type });
      const views = (viewsList.isPaginated ? viewsList.results : viewsList)
        ?.filter((v: any) => isVisibleToUser(v, user?.id));
      if (!views || views.length === 0) return null;
      return views.find((v: any) => v.default === true) || views[0];
    },
  });

  const { data: viewsData, isPending: isViewsLoading } = useQuery({
    queryKey: ['views', type],
    queryFn: async () => (await client.list('VIW', { model: type })) || [],
  });
  const views = (viewsData?.isPaginated ? viewsData.results : viewsData)
    ?.filter((v: any) => isVisibleToUser(v, user?.id));

  const {
    isPending: isListLoading,
    error: listError,
    data: objectList,
    refetch,
  } = useQuery({
    queryKey: ['list', type, currentView?.id, currentPage, qStr, pageSize],
    queryFn: async () => {
      let filters: Record<string, any> = { ...extraQuery };
      if (currentPage > 1) filters.page = currentPage;
      if (pageSize) filters.page_size = pageSize;

      if (currentView) {
        const fieldsList = [...new Set(
          currentView.fields.concat([
            'id',
            'label',
            'object_images',
            'updated_at',
            currentView.group_by,
            currentView.pivot_by,
            currentView.aggregate_by,
          ].filter(Boolean)),
        )].join(',');

        filters = { _view: currentView.id, _fields: fieldsList, ...filters };

        // Kanban/swimlane need every card on screen; user-chosen page_size
        // doesn't apply there.
        if (currentView.layout === 'kanban' || currentView.layout === 'swimlane') {
          filters.page_size = 500;
        }
        if (currentView.order_by) filters._order_by = currentView.order_by;
      } else {
        filters = { _fields: 'id,label,object_images,updated_at', ...filters };
      }

      if (qStr) filters._q = qStr;

      return await client.list(type, filters);
    },
    enabled: !isViewLoading,
    ...((currentView?.layout === 'conversation' || currentView?.layout === 'kanban') && {
      refetchInterval: realtimeConnected ? false : 60_000,
      refetchIntervalInBackground: false,
    }),
  });

  const rows = objectList?.isPaginated ? objectList.results : objectList;
  useScreenContext({
    view_id: currentView?.id,
    visible_ids: Array.isArray(rows) ? rows.map((row: any) => row.id) : [],
  });

  useHotkeys('r', () => {
    if (!isListLoading && !isRefreshing) {
      setIsRefreshing(true);
      refetch().finally(() => setIsRefreshing(false));
    }
  });

  const handlePageChange = useCallback((pageUrl: string) => {
    if (typeof pageUrl !== 'string' || !pageUrl) return;
    try {
      // Resolve against the current origin so DRF's relative `next`/`previous`
      // URLs (proxy-stripped scheme, custom paginator) work the same as
      // absolute ones.
      const urlObj = new URL(pageUrl, window.location.origin);
      const newPage = parseInt(urlObj.searchParams.get('page') || '1', 10);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (newPage > 1) next.set('page', String(newPage));
          else next.delete('page');
          return next;
        },
        { replace: true },
      );
      setCurrentPage(newPage);
    } catch (error) {
      console.error('Error navigating to page:', error);
    }
  }, [setSearchParams]);

  const handlePageSizeChange = useCallback((newSize: number) => {
    storePageSize('list', newSize);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('page_size', String(newSize));
        // Reset to page 1; the user's previous page index doesn't make sense
        // at a different page size.
        next.delete('page');
        return next;
      },
      { replace: true },
    );
    setCurrentPage(1);
  }, [setSearchParams]);

  const view = useMemo(() => visibleView(currentView, metadata), [currentView, metadata]);

  const overflowItems = useMemo(() => {
    const items: any[] = [];
    if (view) {
      items.push({
        label: 'Edit view',
        icon: 'edit-3',
        onSelect: () => navigate(url(view.id, 'edit', { next: currentUrl })),
      });
    } else if (metadata?.type) {
      items.push({
        label: 'Create view',
        icon: 'plus',
        onSelect: () => navigate(url('VIW', 'create', { model: metadata.type, next: currentUrl })),
      });
    }
    if (metadata?.can_create) {
      items.push({ label: 'Import…', icon: 'upload', onSelect: () => navigate(url(metadata.type, 'import')) });
    }
    return items;
  }, [view, metadata?.type, metadata?.can_create, currentUrl, navigate]);


  if (isMetadataLoading || isViewsLoading || isViewLoading) {
    return <div className="p-4 text-fg-3 text-sm animate-pulse">Loading metadata…</div>;
  }
  if (!metadata) return <div className="p-4 text-fg-3 text-sm">No metadata found</div>;

  const displayData = objectList?.isPaginated ? objectList.results : objectList;

  const header = (
    <PageHeader
      title={metadata.verbose_name_plural}
      count={objectList ? (objectList.isPaginated ? objectList.count : displayData.length) : null}
      actions={
        <>
          <OverflowMenu items={overflowItems} />
          <Link to={url(type, 'create', { next: currentUrl })} className="ck-btn ck-btn-primary">
            <Icon name="plus" size={14} color="currentColor" />
            New
            <Kbd>N</Kbd>
          </Link>
        </>
      }
      tabs={views && views.length > 0 && (
        <div className="ck-view-tabs">
          {views.map((v: any) => (
            <button
              key={v.id}
              type="button"
              className={`ck-tab ${view?.id === v.id ? 'is-on' : ''}`}
              aria-pressed={view?.id === v.id}
              onClick={() => {
                setCurrentPage(1);
                navigate(url(type, null, {}, v.id));
              }}
            >
              {v.name}
            </button>
          ))}
        </div>
      )}
      toolbar={
        <PageSearch placeholder={`Search ${metadata.verbose_name_plural?.toLowerCase() || 'items'}…`} />
      }
    />
  );

  return (
    <>
      {header}
      {isListLoading ? (
        <div className="rounded-lg border border-border-1 bg-bg-2 p-6">
          <div className="animate-pulse flex flex-col space-y-4">
            <div className="h-3 bg-bg-3 rounded w-1/4" />
            <div className="space-y-2">
              <div className="h-3 bg-bg-3 rounded" />
              <div className="h-3 bg-bg-3 rounded w-5/6" />
              <div className="h-3 bg-bg-3 rounded w-3/4" />
              <div className="h-3 bg-bg-3 rounded w-4/6" />
            </div>
          </div>
        </div>
      ) : listError ? (
        <div className="rounded-lg border border-border-1 bg-bg-2 p-6">
          <div className="text-danger text-sm">
            Couldn&apos;t load data: {(listError as Error).message}
            <div className="mt-3">
              <button
                type="button"
                onClick={() => refetch()}
                className="ck-btn ck-btn-secondary ck-btn-sm"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      ) : !objectList ? (
        <div className="rounded-lg border border-border-1 bg-bg-2 p-6">
          <div className="text-fg-3 text-sm">No data found</div>
        </div>
      ) : view?.layout === 'gallery' ? (
        <Gallery objectList={displayData} view={view} metadata={metadata} q={qStr} />
      ) : view?.layout === 'kanban' ? (
        <KanbanBoard
          objectList={displayData}
          view={view}
          model={type}
          metadata={metadata}
          key={view?.id || 'default-kanban'}
          q={qStr}
        />
      ) : view?.layout === 'swimlane' ? (
        <Swimlane
          objectList={displayData}
          view={view}
          model={type}
          metadata={metadata}
          refetch={refetch}
          q={qStr}
        />
      ) : view?.layout === 'quadrant' ? (
        <QuadrantView
          objectList={displayData}
          view={view}
          metadata={metadata}
        />
      ) : view?.layout === 'conversation' ? (
        <ConversationList
          objectList={displayData}
          view={view}
          model={type}
          metadata={metadata}
          refetch={refetch}
        />
      ) : (
        <ObjectList
          objectList={displayData}
          view={view}
          model={type}
          metadata={metadata}
          pagination={objectList.isPaginated ? objectList : null}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
        />
      )}
    </>
  );
}
