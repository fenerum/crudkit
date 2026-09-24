import {
  COMPARATORS,
  FILTER_VARIABLES,
  fieldKind,
  fkCkId,
  isNumeric,
  isTriple,
  isVariable,
  parseFilters,
  supportsOrdering,
  validateFilter,
} from "../../utils/filters";
import { useEffect, useMemo, useRef, useState } from "react";
import AsyncSelect from "react-select/async";
import BaseField from "./BaseField";
import CreatableSelect from "react-select/creatable";
import CrudKitAPIClient from "../../data/api";
import { Icon } from "../ui";
import { SELECT_STYLES } from "./selectStyles";
import Select from "react-select";
import { useMetadata } from "../../utils/formHooks";
import { useQuery } from "@tanstack/react-query";
import { useWatch } from "react-hook-form";

const apiClient = new CrudKitAPIClient();

function selectStyles(invalid, minWidth = 0) {
  return {
    ...SELECT_STYLES,
    container: (base) => ({ ...base, minWidth }),
    control: (base, state) => ({
      ...SELECT_STYLES.control(base, state),
      ...(invalid ? { borderColor: "var(--danger)" } : {}),
    }),
  };
}

const SELECT_PORTAL = {
  menuPortalTarget: typeof document !== "undefined" ? document.body : undefined,
  menuPosition: "fixed",
};

const BOOLEAN_OPTIONS = [
  { value: true, label: "Yes" },
  { value: false, label: "No" },
];

// Keep a stored value the options don't know about visible (flagged) so the
// user can see what's wrong and replace it.
function withCurrent(options, value) {
  if (value === null || value === undefined) return { options, current: null };
  const current = options.find((o) => String(o.value) === String(value));
  if (current) return { options, current };
  const invalid = { value, label: `${JSON.stringify(value)} (invalid)` };
  return { options: [invalid, ...options], current: invalid };
}

function fieldLabel(name, meta) {
  return meta?.verbose_name || name;
}

function FieldSelect({ field, fieldMetaByName, invalid, onChange, placeholder = "Field" }) {
  const options = Object.entries(fieldMetaByName).map(([name, meta]) => ({
    value: name,
    label: fieldLabel(name, meta),
  }));
  const current = field
    ? options.find((o) => o.value === field) || { value: field, label: field }
    : null;
  return (
    <CreatableSelect
      aria-label="Filter field"
      options={options}
      value={current}
      onChange={(opt) => opt && onChange(opt.value)}
      placeholder={placeholder}
      isValidNewOption={(input) => input.includes("__")}
      formatCreateLabel={(input) => `Use path "${input}"`}
      formatOptionLabel={(opt, { context }) =>
        context === "value" ? (
          opt.label
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate">{opt.label}</span>
            <span className="text-2xs text-fg-3 font-mono truncate">{opt.value}</span>
          </div>
        )
      }
      styles={selectStyles(invalid)}
      {...SELECT_PORTAL}
    />
  );
}

function ComparatorSelect({ comparator, kind, invalid, onChange }) {
  const known = (supportsOrdering(kind) ? COMPARATORS : ["=", "!="]).map((c) => ({ value: c, label: c }));
  const { options, current } = withCurrent(known, comparator);
  return (
    <Select
      aria-label="Filter comparator"
      options={options}
      value={current}
      onChange={(opt) => opt && onChange(opt.value)}
      isSearchable={false}
      styles={selectStyles(invalid, 64)}
      {...SELECT_PORTAL}
    />
  );
}

// Number inputs keep their own text so partial input like "1." survives the
// round trip through the stored number.
function NumberInput({ value, invalid, onChange }) {
  const parse = (text) => (isNumeric(text) ? Number(text) : text === "" ? null : text);
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => {
    if (parse(text) !== value) setText(value == null ? "" : String(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <input
      aria-label="Filter value"
      inputMode="decimal"
      value={text}
      placeholder="empty"
      onChange={(e) => {
        setText(e.target.value);
        onChange(parse(e.target.value));
      }}
      className={`ck-input ${invalid ? "is-error" : ""}`}
    />
  );
}

// Relationship paths (`book__title`, `pages__isnull`) have no metadata, so
// read JSON literals (numbers, true/false, null) and keep the rest as text.
function parseLoose(text) {
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed !== "object" || parsed === null) return parsed;
  } catch {
    /* plain text */
  }
  return text;
}

function TextInput({ value, invalid, loose, onChange }) {
  const shown = value == null ? "" : typeof value === "string" ? value : JSON.stringify(value);
  return (
    <input
      aria-label="Filter value"
      value={shown}
      placeholder="empty"
      onChange={(e) => onChange(loose ? parseLoose(e.target.value) : e.target.value)}
      className={`ck-input ${invalid ? "is-error" : ""}`}
    />
  );
}

function ForeignKeyInput({ meta, value, label, invalid, onChange }) {
  const type = meta.related_model_type;
  const loadOptions = async (q) => {
    const response = await apiClient.list(type, { _q: q, _fields: "id,label" });
    const items = response?.isPaginated ? response.results || [] : response || [];
    return items.map((item) => ({ value: item.id, label: item.label || item.id }));
  };
  const current =
    value == null ? null : { value, label: label || (invalid ? `${JSON.stringify(value)} (invalid)` : String(value)) };
  return (
    <AsyncSelect
      aria-label="Filter value"
      loadOptions={loadOptions}
      defaultOptions
      value={current}
      onChange={(opt) => onChange(opt ? opt.value : null)}
      isClearable
      placeholder="empty"
      styles={selectStyles(invalid)}
      {...SELECT_PORTAL}
    />
  );
}

function ValueInput({ kind, meta, value, fkLabel, invalid, onChange }) {
  if (isVariable(value)) {
    const variable = FILTER_VARIABLES.find((v) => v.value === value);
    return (
      <span className="flex w-full items-center gap-1.5 px-2 py-1.5 rounded border border-border-1 bg-bg-3 text-xs text-fg-1">
        <Icon name="braces" size={12} color="currentColor" />
        <span className="flex-1 truncate">{variable.label}</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-fg-3 hover:text-fg-1"
          aria-label={`Remove ${variable.label}`}
        >
          <Icon name="x" size={12} color="currentColor" />
        </button>
      </span>
    );
  }
  const selectProps = { isClearable: true, placeholder: "empty", styles: selectStyles(invalid), ...SELECT_PORTAL };
  switch (kind) {
    case "choice": {
      const choices = meta.choices.map(([v, label]) => ({ value: v, label }));
      const { options, current } = withCurrent(choices, value);
      return (
        <Select
          aria-label="Filter value"
          options={options}
          value={current}
          onChange={(opt) => onChange(opt ? opt.value : null)}
          {...selectProps}
        />
      );
    }
    case "boolean": {
      const { options, current } = withCurrent(BOOLEAN_OPTIONS, value);
      return (
        <Select
          aria-label="Filter value"
          options={options}
          value={current}
          onChange={(opt) => onChange(opt ? opt.value : null)}
          isSearchable={false}
          {...selectProps}
        />
      );
    }
    case "number":
      return <NumberInput value={value} invalid={invalid} onChange={onChange} />;
    case "fk":
      return <ForeignKeyInput meta={meta} value={value} label={fkLabel} invalid={invalid} onChange={onChange} />;
    case "date":
    case "datetime":
      return (
        <input
          aria-label="Filter value"
          type={kind === "date" ? "date" : "datetime-local"}
          value={typeof value === "string" ? value.slice(0, kind === "date" ? 10 : 16) : ""}
          onChange={(e) => onChange(e.target.value || null)}
          className={`ck-input ${invalid ? "is-error" : ""}`}
        />
      );
    default:
      return <TextInput value={value} invalid={invalid} loose={kind === "path"} onChange={onChange} />;
  }
}

function FilterRow({ row, fieldMetaByName, onChange, onRemove }) {
  const [showVariables, setShowVariables] = useState(false);
  const triple = isTriple(row);
  const [field, comparator, value] = triple ? row : [null, "=", null];
  const meta = field ? fieldMetaByName[field] : undefined;
  const kind = fieldKind(meta);

  // Surface FK values pointing at a record that no longer exists.
  const fkId = kind === "fk" ? fkCkId(value, meta.related_model_type) : null;
  const fkQuery = useQuery({
    queryKey: ["detail", meta?.related_model_type, fkId],
    queryFn: () => apiClient.retrieve(meta.related_model_type, fkId),
    enabled: !!fkId,
    retry: false,
  });

  const error =
    validateFilter(row, fieldMetaByName) ||
    (fkQuery.isError ? `No ${fieldLabel(field, meta).toLowerCase()} ${fkId}` : null);
  const fieldInvalid = !triple || !field || (!meta && !field.includes("__"));
  const comparatorInvalid = triple && !COMPARATORS.includes(comparator);
  const valueInvalid = !!error && !fieldInvalid && !comparatorInvalid;

  const update = (index, v) => {
    const next = [field ?? "", comparator, value];
    next[index] = v;
    onChange(next);
  };

  return (
    <div
      data-testid="filter-row"
      data-invalid={error ? "true" : undefined}
      className={`flex flex-col gap-1.5 px-2 py-2 rounded border bg-bg-2 mb-2 ${
        error ? "border-danger" : "border-border-1"
      }`}
    >
      <div className="flex items-center gap-1.5">
        <div className="flex-1 min-w-0">
          <FieldSelect
            field={field}
            fieldMetaByName={fieldMetaByName}
            invalid={fieldInvalid}
            placeholder={triple ? "Field" : "Pick a field"}
            onChange={(name) => {
              const nextKind = fieldKind(fieldMetaByName[name]);
              const keep = supportsOrdering(nextKind) || ["=", "!="].includes(comparator);
              onChange([name, keep && COMPARATORS.includes(comparator) ? comparator : "=", null]);
            }}
          />
        </div>
        <ComparatorSelect
          comparator={comparator}
          kind={kind}
          invalid={comparatorInvalid}
          onChange={(c) => update(1, c)}
        />
        <button
          type="button"
          onClick={onRemove}
          className="ck-icon-btn ck-icon-btn-sm"
          aria-label="Remove filter"
          title="Remove filter"
        >
          <Icon name="x" size={14} color="currentColor" />
        </button>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="flex-1 min-w-0">
          <ValueInput
            kind={kind}
            meta={meta}
            value={value}
            fkLabel={fkQuery.data?.label}
            invalid={valueInvalid}
            onChange={(v) => update(2, v)}
          />
        </div>
        <button
          type="button"
          onClick={() => setShowVariables((s) => !s)}
          className="ck-icon-btn ck-icon-btn-sm"
          aria-label="Insert variable"
          aria-expanded={showVariables}
          title="Insert variable"
        >
          <Icon name="braces" size={14} color="currentColor" />
        </button>
      </div>
      {showVariables && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-2xs text-fg-3">Insert:</span>
          {FILTER_VARIABLES.map((v) => (
            <button
              key={v.value}
              type="button"
              onClick={() => {
                update(2, v.value);
                setShowVariables(false);
              }}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs text-fg-2 border border-border-1 bg-bg-1 hover:bg-bg-3"
              title={v.value}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

function RawFallback({ raw, onChange }) {
  return (
    <div className="flex flex-col gap-2 p-2 rounded border border-danger">
      <p className="text-xs text-danger">
        These filters aren&apos;t a list of [field, comparator, value] entries. Fix the JSON below or start over.
      </p>
      <textarea
        aria-label="Raw filters"
        defaultValue={raw}
        onBlur={(e) => onChange(e.target.value)}
        rows={6}
        className="ck-input is-error font-mono"
        style={{ width: "100%", minHeight: 120, lineHeight: 1.45 }}
      />
      <div>
        <button type="button" onClick={() => onChange([])} className="ck-btn ck-btn-secondary ck-btn-sm">
          Start over
        </button>
      </div>
    </div>
  );
}

function AddFilterSelect({ fieldMetaByName, onAdd }) {
  return (
    <FieldSelect
      field={null}
      fieldMetaByName={fieldMetaByName}
      placeholder="+ Add filter"
      onChange={onAdd}
    />
  );
}

function Editor({ value, onChange, metaRef }) {
  const modelType = useWatch({ name: "model" });
  const { metadata, isMetadataLoading } = useMetadata(modelType);
  const fieldMetaByName = useMemo(() => metadata?.fields || {}, [metadata]);
  metaRef.current = metadata ? fieldMetaByName : null;

  const parsed = parseFilters(value);
  const rows = "rows" in parsed ? parsed.rows : null;

  // Drop filters on fields the newly picked model doesn't have. Only on an
  // actual model switch: on load, unknown fields stay visible (flagged) so the
  // user decides what to do with them.
  const prevModel = useRef(modelType);
  useEffect(() => {
    if (!metadata || prevModel.current === modelType) return;
    const switched = !!prevModel.current;
    prevModel.current = modelType;
    if (!switched || !rows) return;
    const kept = rows.filter((row) => isTriple(row) && fieldMetaByName[row[0].split("__")[0]]);
    if (kept.length !== rows.length) onChange(kept);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metadata, modelType]);

  if (!modelType) {
    return (
      <div className="text-xs text-fg-3 px-2 py-3 border border-dashed border-border-1 rounded">
        Pick a model first to choose its filters.
      </div>
    );
  }

  if (isMetadataLoading) {
    return <div className="text-xs text-fg-3 animate-pulse px-2 py-3">Loading model fields…</div>;
  }

  if (!rows) return <RawFallback raw={parsed.raw} onChange={onChange} />;

  const invalidCount = rows.filter((row) => validateFilter(row, fieldMetaByName)).length;

  return (
    <div className="flex flex-col gap-3" data-testid="filters-editor">
      <div className="flex items-center justify-between">
        <span className="text-xs text-fg-3">
          {rows.length === 0
            ? "No filters · shows every record"
            : `${rows.length} filter${rows.length === 1 ? "" : "s"} · all must match`}
        </span>
        {rows.length > 0 && (
          <button type="button" onClick={() => onChange([])} className="ck-btn ck-btn-secondary ck-btn-sm">
            Clear all
          </button>
        )}
      </div>

      {rows.length > 0 && (
        <div>
          {rows.map((row, idx) => (
            <FilterRow
              key={idx}
              row={row}
              fieldMetaByName={fieldMetaByName}
              onChange={(next) => onChange(rows.map((r, i) => (i === idx ? next : r)))}
              onRemove={() => onChange(rows.filter((_, i) => i !== idx))}
            />
          ))}
        </div>
      )}

      {invalidCount > 0 && (
        <p className="text-xs text-danger">
          {invalidCount === 1 ? "1 filter needs" : `${invalidCount} filters need`} fixing before the view can be saved.
        </p>
      )}

      <AddFilterSelect fieldMetaByName={fieldMetaByName} onAdd={(name) => onChange([...rows, [name, "=", null]])} />
    </div>
  );
}

export default function FiltersEditor({ fieldName, defaultValue, metadata, ...rest }) {
  // Field metadata of the selected model, kept current by the editor so the
  // submit-time validation below can check values against it.
  const metaRef = useRef(null);
  const rules = {
    validate: (value) => {
      const parsed = parseFilters(value);
      if (!("rows" in parsed)) return "Filters must be a list of [field, comparator, value] entries";
      if (!metaRef.current) return true;
      return parsed.rows.some((row) => validateFilter(row, metaRef.current)) ? "Fix the highlighted filters" : true;
    },
  };
  return (
    <BaseField fieldName={fieldName} defaultValue={defaultValue} metadata={metadata} rules={rules} {...rest}>
      {({ value, onChange }) => <Editor value={value} onChange={onChange} metaRef={metaRef} />}
    </BaseField>
  );
}
