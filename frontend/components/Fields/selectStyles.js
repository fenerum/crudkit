// react-select styles shared by every dropdown, so they match the plain
// inputs (see inputClass.ts): 28px, input outline, accent focus ring.
export function selectStyles({ hasError = false } = {}) {
  return {
    control: (base, state) => ({
      ...base,
      minHeight: 28,
      backgroundColor: 'var(--bg-1)',
      borderColor: hasError
        ? 'var(--danger)'
        : state.isFocused
          ? 'var(--primary-400)'
          : 'var(--border-3)',
      boxShadow: state.isFocused ? 'var(--shadow-focus)' : 'none',
      '&:hover': { borderColor: state.isFocused ? 'var(--primary-400)' : 'var(--fg-4)' },
      borderRadius: 'var(--r-md)',
      fontSize: 13,
    }),
    valueContainer: (base) => ({ ...base, padding: '0 8px' }),
    singleValue: (base) => ({ ...base, color: 'var(--fg-1)' }),
    input: (base) => ({ ...base, color: 'var(--fg-1)', margin: 0, padding: 0 }),
    placeholder: (base) => ({ ...base, color: 'var(--fg-4)' }),
    indicatorSeparator: () => ({ display: 'none' }),
    dropdownIndicator: (base) => ({ ...base, padding: 4 }),
    clearIndicator: (base) => ({ ...base, padding: 4 }),
    menu: (base) => ({
      ...base,
      backgroundColor: 'var(--bg-4)',
      border: '1px solid var(--border-2)',
      borderRadius: 'var(--r-lg)',
      boxShadow: 'var(--shadow-menu)',
      zIndex: 9999,
    }),
    menuList: (base) => ({ ...base, padding: 4 }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? 'var(--accent-bg)'
        : state.isFocused
          ? 'var(--bg-5)'
          : 'transparent',
      color: state.isSelected ? 'var(--link)' : 'var(--fg-1)',
      borderRadius: 'var(--r-md)',
      cursor: 'pointer',
      fontSize: 13,
      padding: '5px 8px',
    }),
    menuPortal: (base) => ({ ...base, zIndex: 9999 }),
  };
}

const base = selectStyles();

// Inline editors (filters, layout fields) sit in tight rows.
export const SELECT_STYLES = {
  ...base,
  container: (b) => ({ ...b, minWidth: 200 }),
  control: (b, state) => ({ ...base.control(b, state), fontSize: 12 }),
};
