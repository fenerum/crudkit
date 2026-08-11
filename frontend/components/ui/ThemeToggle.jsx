import * as React from 'react';
import Icon from './Icon';
import { useTheme } from './ThemeContext';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="ck-theme-toggle" role="tablist" aria-label="Theme">
      <button
        type="button"
        role="tab"
        aria-selected={theme === 'light'}
        className={theme === 'light' ? 'is-on' : ''}
        onClick={() => setTheme('light')}
        title="Light theme"
      >
        <Icon name="sun" size={13} color="currentColor" />
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={theme === 'dark'}
        className={theme === 'dark' ? 'is-on' : ''}
        onClick={() => setTheme('dark')}
        title="Dark theme"
      >
        <Icon name="moon" size={13} color="currentColor" />
      </button>
    </div>
  );
}
