import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Select from "react-select";
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
import { FieldList } from "./FieldsEditor";

const apiClient = new CrudKitAPIClient();

function InlineCard({ id, mdl, fields, modelLabel, onFieldsChange, onRemove }) {
  const [open, setOpen] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="rounded border border-border-1 bg-bg-2 mb-2"
    >
      <div className="flex items-center gap-2 px-2 py-1.5">
        <button
          type="button"
          className="ck-icon-btn ck-icon-btn-sm cursor-grab"
          aria-label="Drag to reorder"
          {...attributes}
          {...listeners}
        >
          <Icon name="grip-vertical" size={14} color="currentColor" />
        </button>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="ck-icon-btn ck-icon-btn-sm"
          aria-label={open ? "Collapse" : "Expand"}
        >
          <Icon name={open ? "chevron-down" : "chevron-right"} size={14} color="currentColor" />
        </button>
        <span className="flex-1 min-w-0 truncate text-sm text-fg-1">{modelLabel || mdl}</span>
        <span className="text-2xs text-fg-3 font-mono truncate">
          {mdl} · {(fields || []).length} fields
        </span>
        <button
          type="button"
          onClick={onRemove}
          className="ck-icon-btn ck-icon-btn-sm"
          aria-label={`Remove inline ${mdl}`}
          title="Remove inline"
        >
          <Icon name="x" size={14} color="currentColor" />
        </button>
      </div>
      {open && (
        <div className="px-3 pb-3 pt-1 border-t border-border-1">
          <FieldList
            modelType={mdl}
            value={fields || []}
            onChange={onFieldsChange}
          />
        </div>
      )}
    </div>
  );
}

// Match the ChoiceField look so this dropdown feels like the rest of the
// form. Search-as-you-type comes for free with react-select.
const SELECT_STYLES = {
  control: (base, state) => ({
    ...base,
    minHeight: '34px',
    backgroundColor: 'var(--bg-2)',
    borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-1)',
    boxShadow: state.isFocused ? 'var(--shadow-focus)' : 'none',
    '&:hover': { borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-2)' },
    borderRadius: 'var(--r-sm)',
  }),
  singleValue: (base) => ({ ...base, color: 'var(--fg-1)' }),
  input: (base) => ({ ...base, color: 'var(--fg-1)' }),
  placeholder: (base) => ({ ...base, color: 'var(--fg-3)' }),
  menu: (base) => ({
    ...base,
    backgroundColor: 'var(--bg-4)',
    border: '1px solid var(--border-2)',
    boxShadow: 'var(--shadow-menu)',
    zIndex: 9999,
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected
      ? 'var(--bg-5)'
      : state.isFocused
        ? 'var(--bg-3)'
        : 'transparent',
    color: 'var(--fg-1)',
    cursor: 'pointer',
  }),
  indicatorSeparator: (base) => ({ ...base, backgroundColor: 'var(--border-1)' }),
  menuPortal: (base) => ({ ...base, zIndex: 9999 }),
};

function ModelPicker({ choices, onSelect, disabled }) {
  const [selected, setSelected] = useState(null);
  if (!choices.length) return null;
  const options = choices.map(([code, label]) => ({
    value: code,
    label: `${label} (${code})`,
  }));
  return (
    <div className="flex items-center gap-2 mt-2">
      <div className="flex-1">
        <Select
          options={options}
          value={selected}
          onChange={(opt) => setSelected(opt)}
          isClearable
          isSearchable
          isDisabled={disabled}
          placeholder="Add an inline…"
          styles={SELECT_STYLES}
          menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
          menuPosition="fixed"
        />
      </div>
      <button
        type="button"
        className="ck-btn ck-btn-secondary ck-btn-sm"
        onClick={() => {
          if (!selected) return;
          onSelect(selected.value);
          setSelected(null);
        }}
        disabled={!selected || disabled}
      >
        <Icon name="plus" size={12} color="currentColor" />
        Add
      </button>
    </div>
  );
}

function Editor({ value, onChange }) {
  // Model choices come from the parent model's metadata — the same `choices`
  // we put on `ModelField` server-side. The Layout's `model` field has them.
  const { data: parentMetadata } = useQuery({
    queryKey: ["metadata", "LAY"],
    queryFn: () => apiClient.metadata("LAY"),
  });
  const allModelChoices = useMemo(
    () => parentMetadata?.fields?.model?.choices || [],
    [parentMetadata],
  );
  const labelByCode = useMemo(() => {
    const out = {};
    for (const [code, label] of allModelChoices) out[code] = label;
    return out;
  }, [allModelChoices]);

  const inlines = Array.isArray(value) ? value : [];

  // Each row needs a stable id for dnd-kit. Use index — we never let duplicate
  // models in, so it's stable across the lifetime of a row.
  const items = inlines.map((entry, idx) => ({
    id: `inline-${idx}`,
    mdl: Array.isArray(entry) ? entry[0] : "",
    fields: Array.isArray(entry) ? entry[1] || [] : [],
  }));
  const ids = items.map((i) => i.id);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ids.indexOf(active.id);
    const newIndex = ids.indexOf(over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    onChange(arrayMove(inlines, oldIndex, newIndex));
  };

  const updateFields = (idx, newFields) => {
    const next = inlines.map((entry, i) => (i === idx ? [items[i].mdl, newFields] : entry));
    onChange(next);
  };

  const removeAt = (idx) => onChange(inlines.filter((_, i) => i !== idx));

  const usedModels = new Set(items.map((i) => i.mdl));
  const remainingChoices = allModelChoices.filter(([code]) => !usedModels.has(code));

  return (
    <div>
      {items.length === 0 && (
        <div className="text-xs text-fg-3 px-2 py-3 border border-dashed border-border-1 rounded mb-2">
          No inlines yet. Pick a related model below to add one.
        </div>
      )}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {items.map((it, idx) => (
            <InlineCard
              key={it.id}
              id={it.id}
              mdl={it.mdl}
              fields={it.fields}
              modelLabel={labelByCode[it.mdl]}
              onFieldsChange={(newFields) => updateFields(idx, newFields)}
              onRemove={() => removeAt(idx)}
            />
          ))}
        </SortableContext>
      </DndContext>

      <ModelPicker
        choices={remainingChoices}
        onSelect={(mdl) => onChange([...inlines, [mdl, []]])}
      />
    </div>
  );
}

export default function InlinesEditor({ fieldName, defaultValue, metadata, ...rest }) {
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
