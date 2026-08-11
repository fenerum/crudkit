import * as React from 'react';
import { colorForName, initialsFromName } from './avatarPalette';

export default function Avatar({ name, size = 24, status, src }) {
  const bg = colorForName(name);
  const initials = initialsFromName(name);
  const fs = Math.max(9, Math.round(size * 0.38));
  return (
    <span className="ck-avatar-wrap" style={{ width: size, height: size }}>
      {src ? (
        <img
          className="ck-avatar"
          src={src}
          alt={name || ''}
          style={{ width: size, height: size, objectFit: 'cover' }}
        />
      ) : (
        <span
          className="ck-avatar"
          style={{ background: bg, width: size, height: size, fontSize: fs }}
        >
          {initials}
        </span>
      )}
      {status && <span className={`ck-avatar-status ck-status-${status}`} />}
    </span>
  );
}
