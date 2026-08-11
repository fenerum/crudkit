import * as React from "react";
import { useState } from "react";
import { Link } from "react-router-dom";
import ReadOnlyField from "./ReadOnlyField.jsx";
import { url } from "../utils/urls";
import { Icon, PageSizeSelect } from "./ui";

export default function ObjectList({
    objectList,
    view,
    fields,
    model,
    metadata,
    pagination,
    onPageChange,
    onPageSizeChange,
}) {
    const [selectedRows, setSelectedRows] = useState([]);

    const isPaginated = pagination && pagination.isPaginated;
    const items = isPaginated ? pagination.results : objectList;

    const handlePageChange = (target) => {
        if (onPageChange && target) onPageChange(target);
    };

    const fieldKeys = view ? Object.values(view.fields) : (fields || null);

    const toggleRow = (id) => {
        setSelectedRows(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
    };

    return (
        <form
            id="bulk"
            className="ck-fullbleed flex flex-col"
            style={{ minHeight: 'calc(100vh - var(--topbar-h))' }}
        >
            {selectedRows.length > 1 && (
                <div className="flex items-center gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3 py-2">
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

            <div className="bg-bg-1 flex-1">
                <div className="ck-list-head">
                    <div className="ck-lh-c" style={{ flex: '0 0 28px' }}>
                        <span className="sr-only">Select</span>
                    </div>
                    <div className="ck-lh-c" style={{ flex: '0 0 80px' }}>ID</div>
                    {fieldKeys ? fieldKeys.map((field, i) => (
                        <div
                            key={i}
                            className="ck-lh-c"
                            style={{ flex: i === 0 ? '2 1 0' : '1 1 0' }}
                        >
                            {metadata.fields[field]?.verbose_name || field}
                        </div>
                    )) : (
                        <div className="ck-lh-c" style={{ flex: '2 1 0' }}>Label</div>
                    )}
                    <div className="ck-lh-c" style={{ flex: '0 0 28px' }}>
                        <span className="sr-only">Actions</span>
                    </div>
                </div>

                <div className="bg-bg-1">
                    {items.map((object) => {
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
                                        onChange={() => toggleRow(object.id)}
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
                                {fieldKeys ? fieldKeys.map((field, i) => (
                                    <div
                                        key={i}
                                        className="ck-lh-c"
                                        style={{ flex: i === 0 ? '2 1 0' : '1 1 0' }}
                                    >
                                        <ReadOnlyField field={field} value={object[field]} metadata={metadata.fields[field]} />
                                    </div>
                                )) : (
                                    <div className="ck-lh-c" style={{ flex: '2 1 0' }}>{object.label}</div>
                                )}
                                <div className="ck-lh-c justify-end" style={{ flex: '0 0 28px' }}>
                                    <Link
                                        to={url(object.id, 'delete')}
                                        className="ck-icon-btn ck-icon-btn-sm"
                                        style={{ color: 'var(--danger)' }}
                                        aria-label="Delete"
                                    >
                                        <Icon name="trash-2" size={12} color="currentColor" />
                                    </Link>
                                </div>
                            </div>
                        );
                    })}
                    {items.length === 0 && (
                        <div className="px-6 py-12 text-center text-fg-3 text-sm">
                            Nothing here yet
                        </div>
                    )}
                </div>
            </div>

            {/* Pagination */}
            {isPaginated && (
                <div
                    className="sticky bottom-0 z-10 flex items-center justify-between border-t border-border-1 bg-bg-1 px-3.5 py-2"
                >
                    <span className="text-xs text-fg-3">
                        Showing{' '}
                        <span className="font-mono text-fg-2">
                            {((pagination.current_page - 1) * pagination.page_size) + 1}
                        </span>
                        –
                        <span className="font-mono text-fg-2">
                            {Math.min(pagination.current_page * pagination.page_size, pagination.count)}
                        </span>
                        {' '}of{' '}
                        <span className="font-mono text-fg-2">{pagination.count}</span>
                    </span>

                    <nav className="flex items-center gap-2" aria-label="Pagination">
                        {onPageSizeChange && (
                            <PageSizeSelect
                                value={pagination.page_size}
                                onChange={onPageSizeChange}
                            />
                        )}
                        <button
                            type="button"
                            onClick={() => handlePageChange(pagination.previous)}
                            disabled={!pagination.previous}
                            className="ck-icon-btn ck-icon-btn-sm"
                            aria-label="Previous"
                        >
                            <Icon name="chevron-right" size={12} color="currentColor" style={{ transform: 'scaleX(-1)' }} />
                        </button>
                        {[...Array(pagination.total_pages).keys()].map(page => {
                            const pageNumber = page + 1;
                            const isCurrent = pageNumber === pagination.current_page;
                            const show =
                                pageNumber === 1 ||
                                pageNumber === pagination.total_pages ||
                                (pageNumber >= pagination.current_page - 1 && pageNumber <= pagination.current_page + 1);
                            if (!show) {
                                if (pageNumber === 2 || pageNumber === pagination.total_pages - 1) {
                                    return <span key={`e-${pageNumber}`} className="px-1.5 text-xs text-fg-3">…</span>;
                                }
                                return null;
                            }
                            return (
                                <button
                                    key={pageNumber}
                                    type="button"
                                    onClick={() => {
                                        const u = new URL(window.location.href);
                                        u.searchParams.set('page', String(pageNumber));
                                        handlePageChange(u.toString());
                                    }}
                                    className={"ck-btn ck-btn-sm " + (isCurrent ? "ck-btn-primary" : "ck-btn-ghost")}
                                    aria-current={isCurrent ? "page" : undefined}
                                >
                                    {pageNumber}
                                </button>
                            );
                        })}
                        <button
                            type="button"
                            onClick={() => handlePageChange(pagination.next)}
                            disabled={!pagination.next}
                            className="ck-icon-btn ck-icon-btn-sm"
                            aria-label="Next"
                        >
                            <Icon name="chevron-right" size={12} color="currentColor" />
                        </button>
                    </nav>
                </div>
            )}
        </form>
    );
}
