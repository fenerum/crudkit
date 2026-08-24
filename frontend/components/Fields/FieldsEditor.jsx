import { useEffect, useMemo } from "react";
import { useWatch } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import CrudKitAPIClient from "../../data/api";
import BaseField from "./BaseField";
import { Icon } from "../ui";

const apiClient = new CrudKitAPIClient();

function SelectedRow({ id, name, meta, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-2 py-1.5 rounded border border-border-1 bg-bg-2 mb-1"
    >
      <button
        type="button"
        className="ck-icon-btn ck-icon-btn-sm cursor-grab"
        aria-label="Drag to reorder"
        {...attributes}
        {...listeners}
      >
        <Icon name="grip-vertical" size={14} color="currentColor" />
      </button>
      <span className="flex-1 min-w-0 truncate text-sm text-fg-1">
        {meta?.verbose_name || name}
      </span>
      <span className="text-2xs text-fg-3 font-mono truncate">{name}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ck-icon-btn ck-icon-btn-sm"
        aria-label={`Remove ${name}`}
        title="Remove from view"
      >
        <Icon name="x" size={14} color="currentColor" />
      </button>
    </div>
  );
}

function AvailableRow({ name, meta, onAdd }) {
  return (
    <button
      type="button"
      onClick={onAdd}
      className="flex w-full items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-bg-2"
    >
      <span className="ck-icon-btn ck-icon-btn-sm flex-shrink-0">
        <Icon name="plus" size={12} color="currentColor" />
      </span>
      <span className="flex-1 min-w-0 truncate text-sm text-fg-2">
        {meta?.verbose_name || name}
      </span>
      <span className="text-2xs text-fg-3 font-mono truncate">{name}</span>
    </button>
  );
}

function NestedFallback({ value, onChange }) {
  // Layouts also support a 2-column nested format. We don't try to manage
  // that visually here — fall back to a JSON textarea so the user can still
  // edit it.
  const text = useMemo(() => JSON.stringify(value, null, 2), [value]);
  return (
    <div>
      <p className="text-xs text-fg-3 mb-1">
        This layout uses the two-column format ([[…], […]]). Edit it as JSON below.
      </p>
      <textarea
        defaultValue={text}
        onBlur={(e) => {
          try {
            onChange(JSON.parse(e.target.value));
          } catch {
            /* keep the previous value if invalid */
          }
        }}
        rows={8}
        className="ck-input font-mono"
        style={{ width: "100%", minHeight: 160, lineHeight: 1.45 }}
      />
    </div>
  );
}

/**
 * Editor body that drives a list of selected fields for a known model. Used
 * both by FieldsEditor (top-level form field for Layout/View) and by
 * InlinesEditor (one per inline). When `modelType` is empty, prompts the user
 * to pick one.
 */
export function FieldList({
  modelType,
  value,
  onChange,
  // When true, prune entries that don't exist on the model whenever metadata
  // arrives. FieldsEditor wants this; InlinesEditor's nested lists do too,
  // but we expose the prop so callers can opt out if needed.
  pruneOnModelChange = true,
  emptyHint = "Pick a model first to choose its fields.",
}) {
  const { data: modelMetadata, isPending } = useQuery({
    queryKey: ["metadata", modelType],
    queryFn: () => apiClient.metadata(modelType),
    enabled: !!modelType,
  });

  const allFieldEntries = useMemo(
    () => Object.entries(modelMetadata?.fields || {}),
    [modelMetadata],
  );
  const allFieldNames = useMemo(() => allFieldEntries.map(([name]) => name), [allFieldEntries]);
  const fieldMetaByName = useMemo(() => modelMetadata?.fields || {}, [modelMetadata]);

  useEffect(() => {
    if (!pruneOnModelChange) return;
    if (!modelMetadata || !Array.isArray(value)) return;
    const validNames = new Set(allFieldNames);
    const filtered = value.filter((f) => validNames.has(f));
    if (filtered.length !== value.length) {
      onChange(filtered);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelMetadata]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  if (Array.isArray(value) && value.length > 0 && Array.isArray(value[0])) {
    return <NestedFallback value={value} onChange={onChange} />;
  }

  if (!modelType) {
    return (
      <div className="text-xs text-fg-3 px-2 py-3 border border-dashed border-border-1 rounded">
        {emptyHint}
      </div>
    );
  }

  if (isPending) {
    return <div className="text-xs text-fg-3 animate-pulse px-2 py-3">Loading model fields…</div>;
  }

  const selectedFields = Array.isArray(value) ? value : [];
  const availableFields = allFieldNames.filter((f) => !selectedFields.includes(f));

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = selectedFields.indexOf(active.id);
    const newIndex = selectedFields.indexOf(over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    onChange(arrayMove(selectedFields, oldIndex, newIndex));
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-fg-3">
          {selectedFields.length} of {allFieldNames.length} selected
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onChange([...allFieldNames])}
            className="ck-btn ck-btn-secondary ck-btn-sm"
          >
            Show all
          </button>
          <button
            type="button"
            onClick={() => onChange([])}
            className="ck-btn ck-btn-secondary ck-btn-sm"
          >
            Hide all
          </button>
        </div>
      </div>

      {selectedFields.length > 0 && (
        <div>
          <div className="eyebrow mb-1.5">Visible (drag to reorder)</div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={selectedFields} strategy={verticalListSortingStrategy}>
              {selectedFields.map((name) => (
                <SelectedRow
                  key={name}
                  id={name}
                  name={name}
                  meta={fieldMetaByName[name]}
                  onRemove={() => onChange(selectedFields.filter((f) => f !== name))}
                />
              ))}
            </SortableContext>
          </DndContext>
        </div>
      )}

      {availableFields.length > 0 && (
        <div>
          <div className="eyebrow mb-1.5">Available</div>
          <div className="flex flex-col">
            {availableFields.map((name) => (
              <AvailableRow
                key={name}
                name={name}
                meta={fieldMetaByName[name]}
                onAdd={() => onChange([...selectedFields, name])}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Editor({ value, onChange }) {
  const modelType = useWatch({ name: "model" });
  return <FieldList modelType={modelType} value={value} onChange={onChange} />;
}

export default function FieldsEditor({ fieldName, defaultValue, metadata, ...rest }) {
  return (
    <BaseField
      fieldName={fieldName}
      defaultValue={defaultValue}
      metadata={metadata}
      {...rest}
    >
      {({ value, onChange }) => <Editor value={value} onChange={onChange} />}
    </BaseField>
  );
}
