import * as React from "react";
import ReadOnlyField from "./ReadOnlyField.jsx";
import { groupBy } from "../utils/groupby";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import CrudKitAPIClient from "../data/api";
import { toast } from "react-toastify";
import {
    DndContext,
    DragOverlay,
    KeyboardSensor,
    PointerSensor,
    closestCorners,
    useDroppable,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import {
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { url } from "../utils/urls";
import { PriorityBars } from "./ui";
import {
    AMOUNT_FIELDS, PRIORITY_FIELDS,
    findFieldByNames, priorityLevel,
} from "../utils/cardFields";

function sum(arr) {
   return arr.reduce(function (a, b) {
      return a + b;
   }, 0);
}

// Compact "swim-card" matching the design system. Same shape as the kanban
// DealCard (id top + title + footer) but with the smaller .ck-swim-card
// chrome (6px radius, 8/10 padding, gap 4) defined in global.css.
function SwimCard({ id, object, view, metadata }) {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
    if (!object) return null;
    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    const titleField = view.fields[0];
    const amountField = view.aggregate_by || findFieldByNames(object, AMOUNT_FIELDS);
    const amountMeta = amountField ? metadata.fields[amountField] : null;
    const priorityField = findFieldByNames(object, PRIORITY_FIELDS);
    const prioLevel = priorityLevel(priorityField ? object[priorityField] : null);

    return (
        <Link to={url(object.id)} ref={setNodeRef} style={style} {...attributes} {...listeners} className="ck-swim-card">
            <div className="ck-dc-head">
                <span className="ck-sc-id">{object.id}</span>
                {prioLevel != null && <PriorityBars level={prioLevel} />}
            </div>
            <div className="ck-sc-title truncate">
                {titleField ? (
                    <ReadOnlyField value={object[titleField]} metadata={metadata.fields[titleField]} link={false} />
                ) : (
                    object.label || object.id
                )}
            </div>
            <div className="ck-sc-foot">
                {amountField && amountMeta ? (
                    <span className="ck-sc-amt">
                        <ReadOnlyField value={object[amountField]} metadata={amountMeta} link={false} />
                    </span>
                ) : (
                    <span />
                )}
                {object.object_images && object.object_images.length > 0 && (
                    <div className="flex items-center">
                        {object.object_images.slice(0, 3).map((src, i) => (
                            <img
                                key={i}
                                src={src}
                                alt=""
                                className="rounded-full"
                                style={{
                                    width: 16,
                                    height: 16,
                                    objectFit: 'cover',
                                    border: '1px solid var(--bg-2)',
                                    marginLeft: i === 0 ? 0 : -5,
                                }}
                            />
                        ))}
                    </div>
                )}
            </div>
        </Link>
    );
}

function DroppableCell({ id, items, children }) {
    const { isOver, setNodeRef } = useDroppable({ id });
    return (
        <SortableContext items={items} id={id} strategy={verticalListSortingStrategy}>
            <div
                ref={setNodeRef}
                className="flex flex-col gap-1.5"
                style={isOver ? { outline: '1px dashed var(--primary-400)', borderRadius: 6 } : undefined}
            >
                {children}
                {items.length === 0 && <div className="ck-swim-empty" />}
            </div>
        </SortableContext>
    );
}

export default function Swimlane({ objectList, view, model, metadata, refetch, q = '' }) {
    const client = new CrudKitAPIClient();

    // Check if we hit the limit
    const isDataLimited = objectList.length >= 500;

    const filterText = q;
    const [expandedRows, setExpandedRows] = useState({});
    const [sortOrder] = useState('asc');
    const [sortBy] = useState('');

    // Drag and drop state
    const [activeId, setActiveId] = useState(null);
    const [draggedItemData, setDraggedItemData] = useState(null);
    const dragSourceColumnRef = useRef(null);
    const dragSourcePivotRef = useRef(null);
    const [objectMap, setObjectMap] = useState({});
    const [dndItems, setDndItems] = useState({});
    const isDraggingRef = useRef(false);
    const isTouchDevice = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: { distance: isTouchDevice ? Infinity : 5 },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    // Default currency from system settings
    const DEFAULT_CURRENCY = 'DKK';
    
    // Format currency based on currency code
    const formatMoney = (amount, currencyCode) => {
        const formatter = new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: currencyCode,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
        return formatter.format(amount);
    };
    
    // Filter objects based on search text
    const filteredObjects = objectList.filter(obj => {
        if (!filterText) return true;
        
        // Check if any field contains the filter text
        return view.fields.some(field => {
            const value = obj[field];
            if (value === null || value === undefined) return false;
            
            // Check if it's a foreign key object
            if (typeof value === 'object' && value.label) {
                return value.label.toLowerCase().includes(filterText.toLowerCase());
            }
            
            // Regular field value
            return String(value).toLowerCase().includes(filterText.toLowerCase());
        });
    });
    
    // Sort objects
    const sortedObjects = [...filteredObjects].sort((a, b) => {
        if (!sortBy) {
            // Default sort by pivot field
            const valA = a[view.pivot_by];
            const valB = b[view.pivot_by];
            
            if (sortOrder === 'asc') {
                return valA > valB ? 1 : -1;
            } else {
                return valA < valB ? 1 : -1;
            }
        } else {
            // Sort by chosen field
            const valA = a[sortBy];
            const valB = b[sortBy];
            
            // Handle different data types
            if (typeof valA === 'number' && typeof valB === 'number') {
                return sortOrder === 'asc' ? valA - valB : valB - valA;
            } else {
                // Convert to string for comparison
                const strA = String(valA || '');
                const strB = String(valB || '');
                return sortOrder === 'asc' ? 
                    strA.localeCompare(strB) : 
                    strB.localeCompare(strA);
            }
        }
    });
    
    // Group objects for swimlane display
    const swimLaneList = Object.entries(
        groupBy(sortedObjects, (object) => object[view.pivot_by])
    ).map(([key, value]) => (
        [key, Object.entries(groupBy(value, (object) => {
            // Handle both foreign key and regular fields
            const groupValue = object[view.group_by];
            return typeof groupValue === 'object' ? groupValue?.id : groupValue;
        }))]
    ));
    
    // Toggle row expansion
    const toggleRowExpansion = (pivotKey) => {
        setExpandedRows(prev => ({
            ...prev,
            [pivotKey]: !prev[pivotKey]
        }));
    };
    
    // Field metadata
    const groupByField = metadata.fields[view.group_by];
    const pivotByField = metadata.fields[view.pivot_by];
    const initialColumns = groupByField.choices ? groupByField.choices : [];
    const [columns, setColumns] = useState(initialColumns);
    
    // Helper function to extract amount value from money field
    const getAmountValue = (object, fieldName) => {
        const field = object[fieldName];
        
        // Handle money field format (object with currency and amount)
        if (field && typeof field === 'object' && field.amount !== undefined) {
            // Return the amount in default currency for calculations
            return Number(field.amount_default_currency || field.amount);
        }
        
        // Handle regular number field
        return Number(field || 0);
    };
    
    // Helper function to get currency from money field
    const getCurrency = (object, fieldName) => {
        const field = object[fieldName];
        if (field && typeof field === 'object' && field.currency) {
            return field.currency;
        }
        return DEFAULT_CURRENCY;
    };
    
    // Calculate column totals for the footer
    const calculateColumnTotals = useCallback(() => {
        const totals = {};
        const currencyTotals = {};
        
        columns.forEach(([id]) => {
            // Get all objects in this column
            const columnObjects = swimLaneList.flatMap(([_, stageObjectList]) => 
                stageObjectList
                    .filter(([stageId]) => stageId === id)
                    .flatMap(([_, objectList]) => objectList)
            );
            
            // Calculate total in default currency
            const defaultCurrencyValues = columnObjects.map(object => 
                getAmountValue(object, view.aggregate_by)
            );
            totals[id] = sum(defaultCurrencyValues);
            
            // Group by currency and calculate totals for each currency
            const byCurrency = {};
            columnObjects.forEach(object => {
                const currency = getCurrency(object, view.aggregate_by);
                const amount = Number(object[view.aggregate_by]?.amount || 0);
                
                if (!byCurrency[currency]) {
                    byCurrency[currency] = 0;
                }
                byCurrency[currency] += amount;
            });
            
            currencyTotals[id] = byCurrency;
        });
        
        return { totals, currencyTotals };
    }, [columns, swimLaneList, view.aggregate_by, DEFAULT_CURRENCY]);
    
    // Load columns data for foreign key fields
    const loadColumns = async () => {
        const response = await client.list(metadata.fields[view.group_by].related_model_type);
        // Handle both paginated and non-paginated responses
        const data = response?.isPaginated ? response.results : response;
        return Array.isArray(data) ? data.map((result) => [result.id, result.label]) : [];
    };
    
    useEffect(() => {
        (async () => {
            if (groupByField.type === "ForeignKey" && columns.length === 0) {
                const data = await loadColumns();
                setColumns(data);
            }
        })();
    }, [columns, groupByField.type]);

    // Sync objectMap and dndItems when objectList or columns change
    useEffect(() => {
        if (isDraggingRef.current) return;

        const newMap = {};
        objectList?.forEach(obj => { newMap[obj.id] = obj; });
        setObjectMap(newMap);

        const itemsMap = {};

        // Initialize ALL cells (including empty ones) so findContainer works for empty drop targets
        const pivotValues = [...new Set((objectList || []).map(obj => String(obj[view.pivot_by] ?? '')))];
        pivotValues.forEach(pv => {
            columns.forEach(([colId]) => {
                itemsMap[`${pv}::${colId}`] = [];
            });
        });

        // Populate cells with item IDs
        (objectList || []).forEach(obj => {
            const pivotValue = String(obj[view.pivot_by] ?? '');
            const groupValue = obj[view.group_by];
            const colId = String(typeof groupValue === 'object' ? groupValue?.id ?? '' : groupValue ?? '');
            const key = `${pivotValue}::${colId}`;
            if (!itemsMap[key]) itemsMap[key] = [];
            itemsMap[key].push(obj.id);
        });
        setDndItems(itemsMap);
        setActiveId(null);
        setDraggedItemData(null);
    }, [objectList, columns, view.pivot_by, view.group_by]);

    const getColumnId = (containerId) => {
        const idx = String(containerId).indexOf('::');
        return idx >= 0 ? String(containerId).slice(idx + 2) : String(containerId);
    };

    const getPivotValue = (containerId) => {
        const idx = String(containerId).indexOf('::');
        return idx >= 0 ? String(containerId).slice(0, idx) : '';
    };

    const findContainer = (id) => {
        if (id in dndItems) return id;
        return Object.keys(dndItems).find(key => dndItems[key].includes(id));
    };

    const getFilteredItemIds = useCallback((itemIds) => {
        if (!filterText) return itemIds;
        return itemIds.filter(id => {
            const obj = objectMap[id];
            if (!obj) return false;
            return view.fields.some(field => {
                const value = obj[field];
                if (value === null || value === undefined) return false;
                if (typeof value === 'object' && value.label) {
                    return value.label.toLowerCase().includes(filterText.toLowerCase());
                }
                return String(value).toLowerCase().includes(filterText.toLowerCase());
            });
        });
    }, [filterText, objectMap, view.fields]);

    function handleDragStart(event) {
        const { active } = event;
        if (!objectMap[active.id]) return;
        isDraggingRef.current = true;
        setActiveId(active.id);
        setDraggedItemData(objectMap[active.id]);
        const sourceContainer = findContainer(active.id) || '';
        dragSourceColumnRef.current = getColumnId(sourceContainer);
        dragSourcePivotRef.current = getPivotValue(sourceContainer);
    }

    function handleDragOver(event) {
        const { active, over } = event;
        if (!over) return;

        const activeContainer = findContainer(active.id);
        const overContainer = findContainer(over.id);

        if (!activeContainer || !overContainer || activeContainer === overContainer) return;

        setDndItems(prev => {
            const activeItems = prev[activeContainer] || [];
            const overItems = prev[overContainer] || [];
            const overIndex = overItems.indexOf(over.id);

            let newIndex;
            if (over.id in prev) {
                newIndex = overItems.length;
            } else {
                newIndex = overIndex >= 0 ? overIndex + 1 : overItems.length;
            }

            return {
                ...prev,
                [activeContainer]: activeItems.filter(item => item !== active.id),
                [overContainer]: [
                    ...overItems.slice(0, newIndex),
                    active.id,
                    ...overItems.slice(newIndex),
                ],
            };
        });
    }

    function handleDragEnd(event) {
        const { active, over } = event;
        isDraggingRef.current = false;

        if (!over) {
            setActiveId(null);
            setDraggedItemData(null);
            dragSourceColumnRef.current = null;
            dragSourcePivotRef.current = null;
            return;
        }

        const overContainer = findContainer(over.id);
        if (!overContainer) {
            setActiveId(null);
            setDraggedItemData(null);
            dragSourceColumnRef.current = null;
            dragSourcePivotRef.current = null;
            return;
        }

        const targetColumnId = getColumnId(overContainer);
        const targetPivotValue = getPivotValue(overContainer);
        const sourceColumn = dragSourceColumnRef.current;
        const sourcePivot = dragSourcePivotRef.current;

        const columnChanged = sourceColumn !== null && sourceColumn !== targetColumnId;
        const pivotChanged = sourcePivot !== null && sourcePivot !== targetPivotValue;

        if (columnChanged || pivotChanged) {
            const updates = {};
            if (columnChanged) {
                updates[view.group_by] = targetColumnId;
            }
            if (pivotChanged) {
                updates[view.pivot_by] = targetPivotValue;
            }

            client.partialUpdate(model, active.id, updates)
            .then(() => {
                toast.success('Updated');
                refetch();
            })
            .catch(error => {
                toast.error('Failed to update');
                console.error('Error updating item:', error);
                refetch();
            });
        }

        setActiveId(null);
        setDraggedItemData(null);
        dragSourceColumnRef.current = null;
        dragSourcePivotRef.current = null;
    }

    // Calculate column totals
    const { totals: columnTotals, currencyTotals } = calculateColumnTotals();
    const grandTotal = Object.values(columnTotals).reduce((a, b) => a + b, 0);
    
    // Calculate row totals and currency breakdowns
    const rowTotals = {};
    const rowCurrencyTotals = {};
    
    swimLaneList.forEach(([pivotBy, stageObjectList]) => {
        // All objects in this row
        const rowObjects = stageObjectList.flatMap(([_, objectList]) => objectList);
        
        // Calculate total in default currency
        rowTotals[pivotBy] = sum(rowObjects.map(object => 
            getAmountValue(object, view.aggregate_by)
        ));
        
        // Group by currency and calculate totals for each currency
        const byCurrency = {};
        rowObjects.forEach(object => {
            const currency = getCurrency(object, view.aggregate_by);
            const amount = Number(object[view.aggregate_by]?.amount || 0);
            
            if (!byCurrency[currency]) {
                byCurrency[currency] = 0;
            }
            byCurrency[currency] += amount;
        });
        
        rowCurrencyTotals[pivotBy] = byCurrency;
    });

    // Per-cell totals (group × stage intersection)
    const cellTotals = {};
    const cellCurrencyTotals = {};
    const cellCounts = {};

    swimLaneList.forEach(([pivotBy, stageObjectList]) => {
        stageObjectList.forEach(([colId, objs]) => {
            const key = `${pivotBy}::${colId}`;
            cellCounts[key] = objs.length;
            cellTotals[key] = sum(objs.map(o => getAmountValue(o, view.aggregate_by)));
            const byCurrency = {};
            objs.forEach(o => {
                const cur = getCurrency(o, view.aggregate_by);
                byCurrency[cur] = (byCurrency[cur] || 0) + Number(o[view.aggregate_by]?.amount || 0);
            });
            cellCurrencyTotals[key] = byCurrency;
        });
    });

    // Build the column-template string used by both header and row grids:
    // 200px row-head + N columns + 140px total column.
    const colCount = columns.length;
    const gridTemplate = `200px repeat(${colCount}, minmax(180px, 1fr)) 140px`;

    return (
        <div className="ck-fullbleed flex flex-col gap-3" style={{ height: '100%' }}>
            {isDataLimited && (
                <div className="mx-6 mt-3 flex items-start gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3 py-2.5">
                    <p className="text-xs text-fg-2 leading-snug">
                        Showing the first 500 items. Add a filter to narrow results.
                    </p>
                </div>
            )}

            <div className="ck-swim" style={{ flex: 1, minHeight: 0 }}>
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCorners}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDragEnd={handleDragEnd}
                >
                    {/* Sticky header */}
                    <div className="ck-swim-head" style={{ gridTemplateColumns: gridTemplate }}>
                        <div className="ck-swim-corner">
                            {pivotByField?.verbose_name || 'Group'}
                        </div>
                        {columns.map(([id, label]) => (
                            <div key={id}>
                                <span className="truncate">{label}</span>
                            </div>
                        ))}
                        <div>Total</div>
                    </div>

                    {/* Body rows */}
                    {swimLaneList.map(([pivotBy, stageObjectList], rowIndex) => {
                        const isExpanded = expandedRows[pivotBy] !== false;
                        const rowItemCount = stageObjectList.reduce(
                            (acc, [, objs]) => acc + objs.length,
                            0
                        );
                        return (
                            <React.Fragment key={pivotBy}>
                                <div
                                    className={`ck-swim-row${rowIndex % 2 === 1 ? ' ck-swim-row--alt' : ''}`}
                                    style={{ gridTemplateColumns: gridTemplate }}
                                >
                                    {/* Row header cell — always rendered */}
                                    <div className="ck-swim-row-head">
                                        <div
                                            className="ck-srh-label ck-fg-1 cursor-pointer inline-flex items-center gap-1.5"
                                            onClick={() => toggleRowExpansion(pivotBy)}
                                        >
                                            <svg
                                                width={11}
                                                height={11}
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth={1.5}
                                                style={{
                                                    transition: 'transform 120ms',
                                                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                                                }}
                                            >
                                                <path d="M9 5l7 7-7 7" />
                                            </svg>
                                            <ReadOnlyField value={pivotBy} metadata={pivotByField} link={false} />
                                        </div>
                                        <div className="ck-srh-meta">
                                            {rowItemCount} {rowItemCount === 1 ? 'item' : 'items'}
                                            {' · '}
                                            {formatMoney(rowTotals[pivotBy] || 0, DEFAULT_CURRENCY)}
                                        </div>
                                    </div>

                                    {/* Stage cells */}
                                    {columns.map(([colId]) => {
                                        const containerId = `${pivotBy}::${colId}`;
                                        const itemIds = getFilteredItemIds(dndItems[containerId] || []);
                                        const cellTotal = cellTotals[containerId] || 0;
                                        const cellCount = cellCounts[containerId] || 0;
                                        const cellByCurrency = cellCurrencyTotals[containerId] || {};
                                        return (
                                            <div key={colId}>
                                                {isExpanded ? (
                                                    <>
                                                        {cellCount > 0 && (
                                                            <div className="text-xs text-fg-3 px-1 pb-1">
                                                                {cellCount} · {formatMoney(cellTotal, DEFAULT_CURRENCY)}
                                                                {Object.entries(cellByCurrency)
                                                                    .filter(([cur]) => cur !== DEFAULT_CURRENCY)
                                                                    .map(([cur, amt]) => (
                                                                        <span key={cur} className="ml-1 font-mono">
                                                                            · {formatMoney(amt, cur)}
                                                                        </span>
                                                                    ))}
                                                            </div>
                                                        )}
                                                        <DroppableCell id={containerId} items={itemIds}>
                                                            {itemIds.map(itemId => (
                                                                <SwimCard
                                                                    key={`${colId}-${itemId}`}
                                                                    id={itemId}
                                                                    object={objectMap[itemId]}
                                                                    view={view}
                                                                    metadata={metadata}
                                                                />
                                                            ))}
                                                        </DroppableCell>
                                                    </>
                                                ) : (
                                                    <span className="text-fg-4 text-xs">·</span>
                                                )}
                                            </div>
                                        );
                                    })}

                                    <div>
                                        <div className="text-sm text-fg-1 font-medium">
                                            {formatMoney(rowTotals[pivotBy] || 0, DEFAULT_CURRENCY)}
                                        </div>
                                        {Object.entries(rowCurrencyTotals[pivotBy] || {})
                                            .filter(([curr]) => curr !== DEFAULT_CURRENCY)
                                            .map(([curr, amt]) => (
                                                <div key={curr} className="text-xs text-fg-3 font-mono">
                                                    {formatMoney(amt, curr)}
                                                </div>
                                            ))}
                                    </div>
                                </div>
                            </React.Fragment>
                        );
                    })}

                    {/* Footer totals row */}
                    <div className="ck-swim-row" style={{ gridTemplateColumns: gridTemplate }}>
                        <div className="ck-swim-row-head">
                            <div className="ck-srh-label">Grand total</div>
                            <div className="ck-srh-meta">{DEFAULT_CURRENCY}</div>
                        </div>
                        {columns.map(([colId]) => (
                            <div key={colId}>
                                <div className="text-sm text-fg-1 font-medium">
                                    {formatMoney(columnTotals[colId] || 0, DEFAULT_CURRENCY)}
                                </div>
                                {Object.entries(currencyTotals[colId] || {})
                                    .filter(([curr]) => curr !== DEFAULT_CURRENCY)
                                    .map(([curr, amt]) => (
                                        <div key={curr} className="text-xs text-fg-3 font-mono">
                                            {formatMoney(amt, curr)}
                                        </div>
                                    ))}
                            </div>
                        ))}
                        <div>
                            <div className="text-sm text-fg-1 font-medium">
                                {formatMoney(grandTotal, DEFAULT_CURRENCY)}
                            </div>
                        </div>
                    </div>

                    <DragOverlay>
                        {activeId && draggedItemData && (
                            <div className="ck-swim-card" style={{ width: 200, opacity: 0.85 }}>
                                <div className="ck-sc-id">{draggedItemData.id}</div>
                                <div className="ck-sc-title truncate">
                                    {draggedItemData.label || draggedItemData.id}
                                </div>
                            </div>
                        )}
                    </DragOverlay>
                </DndContext>
            </div>
        </div>
    );
}