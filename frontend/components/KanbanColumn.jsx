import {useDroppable} from "@dnd-kit/core";
import {SortableContext, verticalListSortingStrategy} from "@dnd-kit/sortable";
import KanbanItem from "./KanbanItem";
import React, { useState } from "react";
import { Dot, Icon } from "./ui";
import { colorForStage } from "./ui/StageBadge";

export default function KanbanColumn({
  id,
  label,
  index = 0,
  items,
  objectList,
  objectMap,
  view,
  metadata,
  showColumnCount = true
}) {
  const { isOver, setNodeRef } = useDroppable({ id });
  const [isCollapsed, setIsCollapsed] = useState(false);

  const columnObjects = items.map(itemId =>
    objectMap ? objectMap[itemId] : objectList.find(obj => obj.id === itemId)
  ).filter(Boolean);

  const calculateAggregate = () => {
    if (!view.aggregate_by || !view.aggregate_type) return null;
    const field = view.aggregate_by;
    const aggregateType = view.aggregate_type.toLowerCase();
    const values = columnObjects.map(obj => obj[field]).filter(val => typeof val === 'number');
    if (values.length === 0) return null;
    switch (aggregateType) {
      case 'sum': return values.reduce((s, v) => s + v, 0);
      case 'avg': return values.reduce((s, v) => s + v, 0) / values.length;
      case 'min': return Math.min(...values);
      case 'max': return Math.max(...values);
      case 'count': return values.length;
      default: return null;
    }
  };

  const aggregate = calculateAggregate();
  const dotColor = colorForStage(label || id);

  return (
    <SortableContext items={items} id={id} strategy={verticalListSortingStrategy}>
      <div ref={setNodeRef} className="ck-pipe-col">
        <div className="ck-pipe-head">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Dot color={dotColor} size={8} />
            <span className="ck-pipe-name truncate">{label || id}</span>
            {showColumnCount && (
              <span className="ck-pipe-count">{items.length}</span>
            )}
            <button
              type="button"
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="ck-icon-btn ck-icon-btn-sm ml-auto"
              aria-label={isCollapsed ? 'Expand column' : 'Collapse column'}
            >
              <Icon name={isCollapsed ? 'chevron-down' : 'chevron-up'} size={12} color="currentColor" />
            </button>
          </div>
          <button type="button" className="ck-icon-btn ck-icon-btn-sm" aria-label="Add item">
            <Icon name="plus" size={12} color="currentColor" />
          </button>
        </div>

        {aggregate !== null && (
          <div className="ck-pipe-sub">
            {view.aggregate_type}: {aggregate.toLocaleString()}
          </div>
        )}

        {!isCollapsed && (
          <div
            className="flex flex-col gap-1.5 min-h-[40px] rounded-md p-px transition-colors duration-fast"
            style={isOver ? { background: 'rgba(123,127,255,0.08)', outline: '1px dashed var(--primary-400)' } : undefined}
          >
            {items.length === 0 ? (
              <div className="border border-dashed border-border-1 rounded-md py-6 text-center text-fg-3 text-xs">
                No items
              </div>
            ) : (
              items.map(objId => (
                <KanbanItem
                  key={objId}
                  id={objId}
                  object={objectMap ? objectMap[objId] : objectList.find(obj => obj.id === objId)}
                  fieldList={view.fields}
                  metadata={metadata}
                />
              ))
            )}
          </div>
        )}
      </div>
    </SortableContext>
  );
}
