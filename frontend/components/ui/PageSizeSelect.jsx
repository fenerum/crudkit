import * as React from "react";
import Select from "react-select";

// Backend caps `page_size` at 1000 (see `crudkit_api/pagination.py`), but the
// useful range tops out around 100 — beyond that the list becomes a scroll
// chore. Keep the options small.
const DEFAULT_OPTIONS = [10, 25, 50, 100];
const MAX_PAGE_SIZE = 100;

// Compact styling so the control fits inside a pagination footer alongside
// the page buttons. Same colour tokens as the form's ChoiceField.
const STYLES = {
  container: (base) => ({ ...base, minWidth: 72 }),
  control: (base, state) => ({
    ...base,
    minHeight: 26,
    height: 26,
    backgroundColor: 'var(--bg-2)',
    borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--border-1)',
    boxShadow: state.isFocused ? 'var(--shadow-focus)' : 'none',
    borderRadius: 'var(--r-sm)',
    fontSize: 12,
  }),
  valueContainer: (base) => ({ ...base, padding: '0 6px' }),
  singleValue: (base) => ({ ...base, color: 'var(--fg-1)' }),
  input: (base) => ({ ...base, color: 'var(--fg-1)', margin: 0, padding: 0 }),
  indicatorsContainer: (base) => ({ ...base, height: 24 }),
  indicatorSeparator: () => ({ display: 'none' }),
  dropdownIndicator: (base) => ({ ...base, padding: 2 }),
  menu: (base) => ({
    ...base,
    backgroundColor: 'var(--bg-4)',
    border: '1px solid var(--border-2)',
    boxShadow: 'var(--shadow-menu)',
    zIndex: 9999,
    fontSize: 12,
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
    padding: '4px 10px',
  }),
  menuPortal: (base) => ({ ...base, zIndex: 9999 }),
};

/**
 * Compact page-size picker for pagination footers.
 *
 * `value` is the current page size; if it isn't in `options`, it's prepended
 * so the user always sees what the list is actually paged by.
 */
export default function PageSizeSelect({ value, onChange, options = DEFAULT_OPTIONS }) {
  const merged = React.useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const n of [value, ...options]) {
      if (typeof n !== 'number' || !Number.isFinite(n)) continue;
      if (n > MAX_PAGE_SIZE) continue;
      if (seen.has(n)) continue;
      seen.add(n);
      out.push({ value: n, label: `${n} / page` });
    }
    return out.sort((a, b) => a.value - b.value);
  }, [value, options]);

  const selected = merged.find((opt) => opt.value === value) || null;

  return (
    <Select
      isSearchable={false}
      options={merged}
      value={selected}
      onChange={(opt) => opt && onChange(opt.value)}
      styles={STYLES}
      menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
      menuPosition="fixed"
      aria-label="Page size"
    />
  );
}
