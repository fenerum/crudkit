import * as React from 'react';
import Dot from './Dot';

export default function Badge({ children, dot, style }) {
  return (
    <span className="ck-badge" style={style}>
      {dot && <Dot color={dot} size={6} />}
      {children}
    </span>
  );
}
