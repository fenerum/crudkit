// Match the rest of the form's dropdowns (ChoiceField uses react-select).
export const SELECT_STYLES = {
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
