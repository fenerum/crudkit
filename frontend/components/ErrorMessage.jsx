import React from 'react';
import { Icon } from './ui';

export default function ErrorMessage({ message, type = 'error' }) {
  const isWarn = type !== 'error';

  return (
    <div
      className="mt-4 w-full flex items-start gap-2.5 rounded-md border bg-bg-2 px-3.5 py-2.5"
      style={{
        borderColor: isWarn ? 'var(--warn)' : 'var(--danger)',
        background: isWarn ? 'var(--warn-bg, var(--bg-2))' : 'var(--danger-bg, var(--bg-2))',
      }}
    >
      <span
        className="flex-shrink-0 mt-0.5"
        style={{ color: isWarn ? 'var(--warn)' : 'var(--danger)' }}
      >
        <Icon name="alert-circle" size={14} color="currentColor" />
      </span>
      <div
        className="flex-1 text-sm"
        style={{ color: isWarn ? 'var(--warn)' : 'var(--danger)' }}
      >
        {message}
      </div>
    </div>
  );
}
