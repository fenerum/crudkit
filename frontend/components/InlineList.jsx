import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReadOnlyField from './ReadOnlyField';
import { PageSizeSelect } from './ui';
import { url } from '@/utils/urls';
import CrudKitAPIClient from '@/data/api';

const DEFAULT_INLINE_PAGE_SIZE = 10;

/**
 * Component for displaying related inline objects in a detail view.
 */
export default function InlineList({ fields, model, metadata, createParams, parent_object_id, related_field_name }) {
  const [selectedRows, setSelectedRows] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_INLINE_PAGE_SIZE);
  const client = new CrudKitAPIClient();

  const listQuery = useQuery({
    queryKey: ['inline-list', model, parent_object_id, currentPage, pageSize],
    queryFn: async () => {
      if (!related_field_name) return [];

      const params = {
        [related_field_name]: parent_object_id,
        page: currentPage,
        page_size: pageSize,
      };

      return await client.list(model, params);
    },
  });

  const handlePageSizeChange = useCallback((newSize) => {
    setPageSize(newSize);
    setCurrentPage(1);
  }, []);

  const handlePageChange = useCallback(async (pageUrl) => {
    try {
      if (typeof pageUrl === 'string' && (pageUrl.startsWith('http://') || pageUrl.startsWith('https://'))) {
        const urlObj = new URL(pageUrl);
        const pageParam = urlObj.searchParams.get('page');
        const newPage = pageParam ? parseInt(pageParam) : 1;
        setCurrentPage(newPage);
      } else if (typeof pageUrl === 'number') {
        setCurrentPage(pageUrl);
      }
    } catch (error) {
      console.error("Error navigating to page:", error);
    }
  }, []);

  const paginationData = !listQuery.isPending && listQuery.data?.isPaginated ? listQuery.data : null;

  const objectList = !listQuery.isPending
    ? (listQuery.data?.isPaginated ? listQuery.data.results : listQuery.data) || []
    : [];

  const isLoading = listQuery.isPending;
  const hasError = listQuery.isError;

  return (
    <div className="mb-6 w-full">
      <div
        className="bg-bg-1"
        style={{ marginLeft: -24, marginRight: -24, width: 'calc(100% + 48px)' }}
      >
        {selectedRows.length > 1 && (
          <div className="flex items-center gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3 py-2 mb-2">
            <span className="text-sm text-fg-2">{selectedRows.length} selected</span>
            <span className="flex-1" />
            <Link
              to={(() => {
                const params = new URLSearchParams();
                selectedRows.forEach(id => params.append('object_id', id));
                return `${url(model, 'merge')}?${params.toString()}`;
              })()}
              className="ck-btn ck-btn-secondary ck-btn-sm"
            >
              Merge
            </Link>
          </div>
        )}
        <div className="ck-list-head">
          <div className="ck-lh-c" style={{ flex: '0 0 28px' }}>
            <span className="sr-only">Select</span>
          </div>
          <div className="ck-lh-c" style={{ flex: '0 0 80px' }}>ID</div>
          {fields.map((field, i) => (
            <div
              key={field}
              className="ck-lh-c"
              style={{ flex: i === 0 ? '2 1 0' : '1 1 0' }}
            >
              {metadata.fields[field]?.verbose_name || field}
            </div>
          ))}
          <div className="ck-lh-c" style={{ flex: '0 0 28px' }}>
            <span className="sr-only">Actions</span>
          </div>
        </div>
        <div>
          {isLoading ? (
            <div className="px-3.5 py-6 text-center text-fg-3 text-sm animate-pulse">
              Loading {metadata.verbose_name_plural.toLowerCase()}…
            </div>
          ) : hasError ? (
            <div className="px-3.5 py-6 text-center text-danger text-sm">
              Couldn't load data — try refreshing.
            </div>
          ) : objectList?.length > 0 ? (
            objectList.map((object) => {
              const isSelected = selectedRows.includes(object.id);
              return (
                <div
                  key={object.id}
                  className={`ck-lrow ${isSelected ? 'is-selected' : ''}`}
                >
                  <div
                    className="ck-lh-c"
                    style={{ flex: '0 0 28px' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      className="ck-checkbox"
                      checked={isSelected}
                      onChange={() => {
                        if (isSelected) {
                          setSelectedRows(selectedRows.filter(r => r !== object.id));
                        } else {
                          setSelectedRows([...selectedRows, object.id]);
                        }
                      }}
                      aria-label={`Select ${object.id}`}
                    />
                  </div>
                  <Link
                    to={url(object.id)}
                    className="ck-lh-c font-mono text-fg-3"
                    style={{ flex: '0 0 80px', fontSize: 11 }}
                  >
                    {object.id}
                  </Link>
                  {fields.map((field, i) => (
                    <div
                      key={field}
                      className="ck-lh-c"
                      style={{ flex: i === 0 ? '2 1 0' : '1 1 0' }}
                    >
                      <ReadOnlyField field={field} value={object[field]} metadata={metadata.fields[field]} />
                    </div>
                  ))}
                  <div className="ck-lh-c justify-end" style={{ flex: '0 0 28px' }}>
                    <Link
                      to={url(object.id, 'delete')}
                      className="ck-icon-btn ck-icon-btn-sm"
                      style={{ color: 'var(--danger)' }}
                      aria-label="Delete"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6" />
                        <path d="M10 11v6" />
                        <path d="M14 11v6" />
                        <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
                      </svg>
                    </Link>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="px-3.5 py-6 text-center text-fg-3 text-sm">
              No {metadata.verbose_name_plural.toLowerCase()} yet.
            </div>
          )}
        </div>
        {paginationData && (
          <div className="flex items-center justify-between px-3.5 py-2 border-t border-border-1">
            <span className="text-xs text-fg-3">
              Showing{' '}
              <span className="font-mono text-fg-2">
                {((paginationData.current_page - 1) * paginationData.page_size) + 1}
              </span>
              –
              <span className="font-mono text-fg-2">
                {Math.min(paginationData.current_page * paginationData.page_size, paginationData.count)}
              </span>
              {' '}of{' '}
              <span className="font-mono text-fg-2">{paginationData.count}</span>
            </span>
            <nav className="flex items-center gap-2" aria-label="Pagination">
              <PageSizeSelect
                value={paginationData.page_size}
                onChange={handlePageSizeChange}
              />
              <button
                type="button"
                onClick={() => handlePageChange(paginationData.previous)}
                disabled={!paginationData.previous}
                className="ck-icon-btn ck-icon-btn-sm"
                aria-label="Previous"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: 'scaleX(-1)' }}>
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
              {[...Array(paginationData.total_pages).keys()].map(page => {
                const pageNumber = page + 1;
                const isCurrent = pageNumber === paginationData.current_page;
                const show =
                  pageNumber === 1 ||
                  pageNumber === paginationData.total_pages ||
                  (pageNumber >= paginationData.current_page - 1 && pageNumber <= paginationData.current_page + 1);
                if (!show) {
                  if (pageNumber === 2 || pageNumber === paginationData.total_pages - 1) {
                    return <span key={`e-${pageNumber}`} className="px-1.5 text-xs text-fg-3">…</span>;
                  }
                  return null;
                }
                return (
                  <button
                    key={pageNumber}
                    type="button"
                    onClick={() => handlePageChange(pageNumber)}
                    className={"ck-btn ck-btn-sm " + (isCurrent ? "ck-btn-primary" : "ck-btn-ghost")}
                    aria-current={isCurrent ? 'page' : undefined}
                  >
                    {pageNumber}
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => handlePageChange(paginationData.next)}
                disabled={!paginationData.next}
                className="ck-icon-btn ck-icon-btn-sm"
                aria-label="Next"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            </nav>
          </div>
        )}
      </div>
    </div>
  );
}
