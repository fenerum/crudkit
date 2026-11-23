import * as React from "react";
import Select from "react-select";
import { selectStyles } from "../Fields/selectStyles";

// Backend caps `page_size` at 1000 (see `crudkit_api/pagination.py`), but the
// useful range tops out around 100 — beyond that the list becomes a scroll
// chore. Keep the options small.
const DEFAULT_OPTIONS = [10, 25, 50, 100];
const MAX_PAGE_SIZE = 100;

// Compact variant of the shared dropdown so it fits a pagination footer.
const base = selectStyles();
const STYLES = {
  ...base,
  container: (b) => ({ ...b, minWidth: 72 }),
  control: (b, state) => ({ ...base.control(b, state), minHeight: 24, height: 24, fontSize: 12 }),
  valueContainer: (b) => ({ ...b, padding: '0 6px' }),
  indicatorsContainer: (b) => ({ ...b, height: 22 }),
  dropdownIndicator: (b) => ({ ...b, padding: 2 }),
  option: (b, state) => ({ ...base.option(b, state), fontSize: 12, padding: '4px 8px' }),
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
