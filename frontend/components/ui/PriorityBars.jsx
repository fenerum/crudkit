import * as React from 'react';

export default function PriorityBars({ level = 0, max = 4 }) {
  const bars = [];
  for (let i = 1; i <= max; i++) {
    bars.push(
      <span key={i} className={`ck-prio-bar ${i <= level ? 'is-on' : ''}`} />
    );
  }
  return <span className="ck-prio">{bars}</span>;
}
