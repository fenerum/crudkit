import {useCallback, useEffect, useMemo, useState} from 'react';
import {
    DndContext,
    DragOverlay,
    KeyboardSensor,
    PointerSensor,
    closestCorners,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import {
    arrayMove,
    sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import KanbanColumn from "./KanbanColumn";
import {groupBy} from "../utils/groupby";
import CrudKitAPIClient from "../data/api";
import { toast } from "react-toastify";
import ErrorMessage from "./ErrorMessage.jsx";
import { Icon } from "./ui";

export default function KanbanBoard({objectList, view, model, metadata, q = ''}) {
    const client = useMemo(() => new CrudKitAPIClient(), []);

    const groupByField = view?.group_by ? metadata.fields[view.group_by] : null;
    const initialColumns = groupByField?.choices ? groupByField.choices : [];
    const [columns, setColumns] = useState(initialColumns);
    const [objectMap, setObjectMap] = useState({});
    const filterText = q;
    const [draggedItemData, setDraggedItemData] = useState(null);
    const [activeId, setActiveId] = useState();
    const isTouchDevice = typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: isTouchDevice ? Infinity : 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const getGrouper = useCallback(
      (object) => groupByField?.type === "ForeignKey" ? object[view.group_by]?.id : object[view.group_by],
      [groupByField, view.group_by]
    );

    const [items, setItems] = useState(() => {
        if (!groupByField || !objectList) return {};
        const validObjectIds = new Set(objectList.map(obj => obj.id));
        const initial = Object.fromEntries(columns.map(([key]) => [key, []]));
        const grouped = groupBy(objectList, (object) => getGrouper(object), (object) => object.id);
        Object.entries(grouped).forEach(([columnId, itemIds]) => {
            if (initial[columnId]) initial[columnId] = itemIds.filter(id => validObjectIds.has(id));
        });
        return initial;
    });

    useEffect(() => {
        const next = {};
        objectList?.forEach(obj => { next[obj.id] = obj; });
        setObjectMap(next);
    }, [objectList]);

    useEffect(() => {
        if (!groupByField || !objectList || !Array.isArray(objectList)) return;
        const validObjectIds = new Set(objectList.map(obj => obj.id));
        const next = Object.fromEntries(columns.map(([key]) => [key, []]));
        const grouped = groupBy(objectList, (object) => getGrouper(object), (object) => object.id);
        Object.entries(grouped).forEach(([columnId, itemIds]) => {
            if (next[columnId]) next[columnId] = itemIds.filter(id => validObjectIds.has(id));
        });
        setItems(next);
        setActiveId(null);
        setDraggedItemData(null);
    }, [objectList, columns, getGrouper, groupByField]);

    const loadColumns = useCallback(async () => {
        const response = await client.list(metadata.fields[view.group_by].related_model_type);
        const data = response?.isPaginated ? response.results : response;
        return Array.isArray(data) ? data.map((result) => [result.id, result.label]) : [];
    }, [client, metadata.fields, view.group_by]);

    const getFilteredItems = useCallback(() => {
        if (!filterText) return items;
        const filtered = {};
        const ql = filterText.toLowerCase();
        Object.keys(items).forEach(columnId => {
            filtered[columnId] = items[columnId].filter(itemId => {
                const obj = objectMap[itemId];
                if (!obj) return false;
                return view.fields.some(field => {
                    const value = obj[field];
                    if (value === null || value === undefined) return false;
                    if (typeof value === 'object' && value.label) return value.label.toLowerCase().includes(ql);
                    return String(value).toLowerCase().includes(ql);
                });
            });
        });
        return filtered;
    }, [items, filterText, objectMap, view.fields]);

    useEffect(() => {
        if (!groupByField) return;
        (async () => {
            if (groupByField.type === "ForeignKey" && columns.length === 0) {
                const data = await loadColumns();
                setColumns(data);
                setItems(
                    Object.assign(
                        Object.fromEntries(data.map(([key]) => [key, []])),
                        groupBy(objectList || [], (object) => object[view.group_by]?.id, (object) => object.id),
                    )
                );
            }
        })();
    }, [columns.length, groupByField, loadColumns, objectList, view.group_by]);

    const isDataLimited = objectList?.length >= 500;

    if (!view.group_by) {
        return <ErrorMessage message="Error: Kanban view requires a group_by field to be configured." />;
    }
    if (!groupByField) {
        return <ErrorMessage message={`Error: The group_by field '${view.group_by}' does not exist in the model metadata.`} />;
    }
    if (!Array.isArray(objectList)) {
        console.error('objectList is not an array:', objectList);
        return <ErrorMessage message="Error: Invalid data format received." />;
    }

    return (
        <div className="flex flex-col gap-2">
            {isDataLimited && (
                <div className="flex items-start gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3 py-2.5">
                    <span className="text-warn flex-shrink-0 mt-0.5">
                        <Icon name="alert-triangle" size={14} color="currentColor" />
                    </span>
                    <p className="text-xs text-fg-2 leading-snug">
                        Showing the first 500 items. There may be more data not displayed — add a filter to narrow results.
                    </p>
                </div>
            )}

            {/* Board */}
            <div className="overflow-x-auto pb-2 -mx-1.5 px-1.5">
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCorners}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDragEnd={handleDragEnd}
                >
                    <div className="flex gap-2.5 items-start">
                        {columns.map(([id, label], index) => (
                            <KanbanColumn
                                key={id}
                                id={id}
                                label={label}
                                index={index}
                                items={getFilteredItems()[id] || []}
                                objectList={objectList}
                                objectMap={objectMap}
                                showColumnCount={true}
                                view={view}
                                metadata={metadata}
                            />
                        ))}
                    </div>

                    <DragOverlay>
                        {activeId && draggedItemData && (
                            <div className="ck-deal-card" style={{width: 280, opacity: 0.85}}>
                                <p className="text-sm font-medium text-fg-1 truncate">
                                    {draggedItemData?.label || draggedItemData?.id || 'Item'}
                                </p>
                            </div>
                        )}
                    </DragOverlay>
                </DndContext>
            </div>
        </div>
    );

    function findContainer(id) {
        if (id in items) return id;
        return Object.keys(items).find((key) => items[key].includes(id));
    }

    function handleDragStart(event) {
        const { active } = event;
        const { id } = active;
        if (!objectMap[id]) return;
        setActiveId(id);
        setDraggedItemData(objectMap[id]);
    }

    function handleDragOver(event) {
        const { active, over } = event;
        if (!over) return;
        const { id } = active;
        const { id: overId } = over;
        const activeContainer = findContainer(id);
        const overContainer = findContainer(overId);
        if (!activeContainer || !overContainer || activeContainer === overContainer) return;

        setItems((prev) => {
            const activeItems = prev[activeContainer];
            const overItems = prev[overContainer];
            const activeIndex = activeItems.indexOf(id);
            const overIndex = overItems.indexOf(overId);
            let newIndex;
            if (overId in prev) {
                newIndex = overItems.length + 1;
            } else {
                const isBelowLastItem = over && overIndex === overItems.length - 1;
                const modifier = isBelowLastItem ? 1 : 0;
                newIndex = overIndex >= 0 ? overIndex + modifier : overItems.length + 1;
            }
            return {
                ...prev,
                [activeContainer]: prev[activeContainer].filter((item) => item !== active.id),
                [overContainer]: [
                    ...prev[overContainer].slice(0, newIndex),
                    items[activeContainer][activeIndex],
                    ...prev[overContainer].slice(newIndex, prev[overContainer].length)
                ]
            };
        });
    }

    function handleDragEnd(event) {
        const { active, over } = event;
        if (!over) {
            setActiveId(null);
            setDraggedItemData(null);
            return;
        }
        const { id } = active;
        const { id: overId } = over;
        if (!objectMap[id]) {
            setActiveId(null);
            setDraggedItemData(null);
            return;
        }
        const activeContainer = findContainer(id);
        const overContainer = findContainer(overId);
        if (!activeContainer || !overContainer) {
            setActiveId(null);
            setDraggedItemData(null);
            return;
        }
        const activeItems = items[activeContainer];
        const activeIndex = activeItems.indexOf(id);
        const overItems = items[overContainer];
        const overIndex = overItems.indexOf(overId);

        client.partialUpdate(model, id, {
            [view.group_by]: overContainer,
        })
        .then(() => {
            toast.success('Status updated');
            if (objectMap[id]) {
                const updatedObj = {...objectMap[id]};
                if (groupByField.type === "ForeignKey") {
                    const columnLabel = columns.find(col => col[0] === overContainer)?.[1];
                    updatedObj[view.group_by] = { id: overContainer, label: columnLabel || overContainer };
                } else {
                    updatedObj[view.group_by] = overContainer;
                }
                setObjectMap(prev => ({ ...prev, [id]: updatedObj }));
            }
            if (activeContainer === overContainer && activeIndex !== overIndex) {
                setItems((prev) => ({
                    ...prev,
                    [overContainer]: arrayMove(prev[overContainer], activeIndex, overIndex)
                }));
            }
        })
        .catch(error => {
            toast.error('Failed to update status');
            console.error('Error updating item status:', error);
            setItems(prev => ({
                ...prev,
                [activeContainer]: [...prev[activeContainer], id],
                [overContainer]: prev[overContainer].filter(item => item !== id)
            }));
        });

        setActiveId(null);
        setDraggedItemData(null);
    }
}
