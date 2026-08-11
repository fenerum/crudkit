import * as React from "react";
import { useEffect, useMemo } from "react";
import { useWatch } from "react-hook-form";
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

const apiClient = new CrudKitAPIClient();

// Layout's `fields` can be:
//   ["a", "b", "c"]                 — single column, three rows
//   [["a", "b"], ["c"]]             — two-column row, then a single
// We always edit as `string[][]` (an array of rows) and serialize back to the
// flat shape when every row has exactly one field. That keeps existing flat
// layouts untouched and only emits the nested form when the user actually
// uses multi-column layout.

function toRows(value) {
  if (!Array.isArray(value)) return [];
  if (value.length === 0) return [];
  if (typeof value[0] === "string") return value.map((name) => [name]);
  return value
    .map((row) => (Array.isArray(row) ? row.filter((f) => typeof f === "string") : []))
    .filter((row) => row.length > 0);
}

function fromRows(rows) {
  const cleaned = rows.filter((row) => row.length > 0);
  if (cleaned.length === 0) return [];
  if (cleaned.every((row) => row.length === 1)) return cleaned.map((row) => row[0]);
  return cleaned;
}

function FieldChip({ name, label, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded border border-border-1 bg-bg-3 text-xs text-fg-1">
      <span className="truncate max-w-[160px]" title={name}>
        {label || name}
      </span>
      <button
        type="button"
        onClick={onRemove}
        className="text-fg-3 hover:text-fg-1"
        aria-label={`Remove ${name}`}
      >
        <Icon name="x" size={12} color="currentColor" />
      </button>
    </span>
  );
}

// Match the rest of the form's dropdowns (ChoiceField uses react-select).
const SELECT_STYLES = {
  container: (base) => ({ ...base, minWidth: 200 }),
  control: (base, state) => ({
    ...base,
    minHeight: '30px',
    backgroundColor: 'var(--bg-3)',
    borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-1)',
    boxShadow: state.isFocused ? 'var(--shadow-focus)' : 'none',
    '&:hover': { borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-2)' },
    borderRadius: 'var(--r-sm)',
    fontSize: 12,
  }),
  valueContainer: (base) => ({ ...base, padding: '0 6px' }),
  singleValue: (base) => ({ ...base, color: 'var(--fg-1)' }),
  input: (base) => ({ ...base, color: 'var(--fg-1)', margin: 0, padding: 0 }),
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
    fontSize: 13,
  }),
  indicatorSeparator: () => ({ display: 'none' }),
  dropdownIndicator: (base) => ({ ...base, padding: 4 }),
  menuPortal: (base) => ({ ...base, zIndex: 9999 }),
};

function AddFieldDropdown({ availableFields, fieldMetaByName, onAdd }) {
  if (availableFields.length === 0) return null;
  const options = availableFields.map((name) => ({
    value: name,
    label: fieldMetaByName[name]?.verbose_name || name,
    sub: name,
  }));
  return (
    <Select
      options={options}
      value={null}
      onChange={(opt) => opt && onAdd(opt.value)}
      placeholder="+ Add field"
      isSearchable
      controlShouldRenderValue={false}
      styles={SELECT_STYLES}
      formatOptionLabel={(opt) => (
        <div className="flex items-center justify-between gap-2">
          <span className="truncate">{opt.label}</span>
          <span className="text-2xs text-fg-3 font-mono truncate">{opt.sub}</span>
        </div>
      )}
      menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
      menuPosition="fixed"
    />
  );
}

function SortableRow({
  id,
  rowIndex,
  fields,
  fieldMetaByName,
  availableFields,
  onAddField,
  onRemoveField,
  onRemoveRow,
}) {
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
      className="flex items-start gap-2 px-2 py-2 rounded border border-border-1 bg-bg-2 mb-2"
    >
      <button
        type="button"
        className="ck-icon-btn ck-icon-btn-sm cursor-grab mt-0.5"
        aria-label="Drag to reorder row"
        {...attributes}
        {...listeners}
      >
        <Icon name="grip-vertical" size={14} color="currentColor" />
      </button>
      <div className="flex-1 min-w-0 flex flex-wrap items-center gap-2">
        {fields.length === 0 && (
          <span className="text-xs text-fg-3 italic">Empty row</span>
        )}
        {fields.map((name) => (
          <FieldChip
            key={name}
            name={name}
            label={fieldMetaByName[name]?.verbose_name}
            onRemove={() => onRemoveField(rowIndex, name)}
          />
        ))}
        <AddFieldDropdown
          availableFields={availableFields}
          fieldMetaByName={fieldMetaByName}
          onAdd={(name) => onAddField(rowIndex, name)}
        />
      </div>
      <button
        type="button"
        onClick={() => onRemoveRow(rowIndex)}
        className="ck-icon-btn ck-icon-btn-sm mt-0.5"
        aria-label="Remove row"
        title="Remove row"
      >
        <Icon name="x" size={14} color="currentColor" />
      </button>
    </div>
  );
}

function Editor({ value, onChange }) {
  const modelType = useWatch({ name: "model" });

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

  const rows = useMemo(() => toRows(value), [value]);
  const selectedFlat = useMemo(() => rows.flat(), [rows]);
  const availableFields = useMemo(
    () => allFieldNames.filter((name) => !selectedFlat.includes(name)),
    [allFieldNames, selectedFlat],
  );

  // Drop entries that don't exist on the new model when the user changes
  // `model`. No-op on initial load when the saved value matches the saved
  // model.
  useEffect(() => {
    if (!modelMetadata) return;
    const valid = new Set(allFieldNames);
    const filteredRows = rows
      .map((row) => row.filter((name) => valid.has(name)))
      .filter((row) => row.length > 0);
    const next = fromRows(filteredRows);
    const before = JSON.stringify(value ?? []);
    const after = JSON.stringify(next);
    if (before !== after) onChange(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelMetadata]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const setRows = (nextRows) => onChange(fromRows(nextRows));

  const addRow = () => setRows([...rows, []]);
  const removeRow = (idx) => setRows(rows.filter((_, i) => i !== idx));
  const addFieldToRow = (idx, name) => {
    const next = rows.map((row, i) => (i === idx ? [...row, name] : row));
    setRows(next);
  };
  const removeFieldFromRow = (idx, name) => {
    const next = rows.map((row, i) => (i === idx ? row.filter((f) => f !== name) : row));
    setRows(next);
  };

  const ids = rows.map((_, i) => `row-${i}`);

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ids.indexOf(active.id);
    const newIndex = ids.indexOf(over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    setRows(arrayMove(rows, oldIndex, newIndex));
  };

  if (!modelType) {
    return (
      <div className="text-xs text-fg-3 px-2 py-3 border border-dashed border-border-1 rounded">
        Pick a model first to choose its fields.
      </div>
    );
  }

  if (isPending) {
    return <div className="text-xs text-fg-3 animate-pulse px-2 py-3">Loading model fields…</div>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-fg-3">
          {selectedFlat.length} of {allFieldNames.length} fields used · {rows.length} row{rows.length === 1 ? '' : 's'}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setRows(allFieldNames.map((name) => [name]))}
            className="ck-btn ck-btn-secondary ck-btn-sm"
          >
            Show all
          </button>
          <button
            type="button"
            onClick={() => setRows([])}
            className="ck-btn ck-btn-secondary ck-btn-sm"
          >
            Hide all
          </button>
        </div>
      </div>

      <div>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={ids} strategy={verticalListSortingStrategy}>
            {rows.map((row, idx) => (
              <SortableRow
                key={ids[idx]}
                id={ids[idx]}
                rowIndex={idx}
                fields={row}
                fieldMetaByName={fieldMetaByName}
                availableFields={availableFields}
                onAddField={addFieldToRow}
                onRemoveField={removeFieldFromRow}
                onRemoveRow={removeRow}
              />
            ))}
          </SortableContext>
        </DndContext>
        <button
          type="button"
          onClick={addRow}
          className="flex w-full items-center justify-center gap-2 px-2 py-2 rounded border border-dashed border-border-1 text-sm text-fg-3 hover:text-fg-1 hover:bg-bg-2"
        >
          <Icon name="plus" size={12} color="currentColor" />
          Add row
        </button>
      </div>

      {availableFields.length > 0 && (
        <div>
          <div className="eyebrow mb-1.5">Unused fields</div>
          <div className="flex flex-wrap gap-1.5">
            {availableFields.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setRows([...rows, [name]])}
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-fg-2 border border-border-1 bg-bg-1 hover:bg-bg-2"
                title={`Add ${name} as its own row`}
              >
                <Icon name="plus" size={10} color="currentColor" />
                {fieldMetaByName[name]?.verbose_name || name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LayoutFieldsEditor({ fieldName, defaultValue, metadata, ...rest }) {
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
