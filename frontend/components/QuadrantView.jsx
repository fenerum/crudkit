import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { hashName } from "./ui/avatarPalette";

// Pull a numeric value out of any field shape (money, FK, plain number).
function extractNumeric(obj, fieldName) {
  const value = obj?.[fieldName];
  if (value === null || value === undefined) return null;
  if (typeof value === 'object' && value.amount !== undefined) {
    return Number(value.amount_default_currency || value.amount);
  }
  if (typeof value === 'object' && value.id !== undefined) {
    return Number(value.id);
  }
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

const PALETTE = [
  '#7B7FFF', // primary
  '#4BA3F5', // stage-blue
  '#3DD68C', // stage-green
  '#9B6BFF', // stage-violet
  '#F5B544', // stage-amber
  '#F0616D', // stage-rose
  '#7D828D', // stage-slate
];

function colorFor(label) {
  return PALETTE[hashName(label || '') % PALETTE.length];
}

function humanize(field) {
  return String(field || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function QuadrantView({ objectList, view, metadata }) {
  const navigate = useNavigate();
  const xField = view?.fields?.[0];
  const yField = view?.fields?.[1];

  const points = useMemo(() => {
    if (!xField || !yField) return [];
    return (objectList || [])
      .map(obj => {
        const x = extractNumeric(obj, xField);
        const y = extractNumeric(obj, yField);
        if (x === null || y === null) return null;
        return { id: obj.id, label: obj.label || obj.id, x, y, raw: obj };
      })
      .filter(Boolean);
  }, [objectList, xField, yField]);

  // Normalize x/y into 0..1 against the data extent so dots fill the board.
  const { norm } = useMemo(() => {
    if (points.length === 0) return { norm: [], xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const xSpan = xMax - xMin || 1;
    const ySpan = yMax - yMin || 1;
    const norm = points.map(p => ({
      ...p,
      nx: (p.x - xMin) / xSpan,
      ny: (p.y - yMin) / ySpan,
      color: colorFor(p.label),
    }));
    return { norm, xMin, xMax, yMin, yMax };
  }, [points]);

  const [hoverId, setHoverId] = useState(null);

  if (!xField || !yField) {
    return (
      <div className="rounded-lg border border-border-1 bg-bg-2 p-6 text-sm text-fg-3">
        The quadrant view needs at least two numeric fields configured (x then y).
      </div>
    );
  }

  if (norm.length === 0) {
    return (
      <div className="rounded-lg border border-border-1 bg-bg-2 p-6 text-sm text-fg-3">
        No items have numeric values for both <code className="font-mono">{xField}</code> and{" "}
        <code className="font-mono">{yField}</code>.
      </div>
    );
  }

  const xLabel = humanize(metadata?.fields?.[xField]?.verbose_name || xField);
  const yLabel = humanize(metadata?.fields?.[yField]?.verbose_name || yField);

  return (
    <div className="ck-quad-wrap">
      <div className="ck-quad-head">
        <div className="ck-quad-sub">
          {norm.length} {norm.length === 1 ? "item" : "items"} · {xLabel} × {yLabel}
        </div>
        <div className="ck-quad-legend">
          <span className="ck-qlg"><span className="ck-qlgd" style={{ background: 'var(--primary-400)' }} /> Highlighted</span>
          <span className="ck-qlg"><span className="ck-qlgd" style={{ background: 'var(--stage-blue)' }} /> Other</span>
        </div>
      </div>

      <div className="ck-quad-board">
        <div className="ck-qax-y-top">High {yLabel.toLowerCase()} →</div>
        <div className="ck-qax-y-bot">← Low {yLabel.toLowerCase()}</div>
        <div className="ck-qax-x-l">← Low {xLabel.toLowerCase()}</div>
        <div className="ck-qax-x-r">High {xLabel.toLowerCase()} →</div>

        <div className="ck-quad-grid">
          <div className="ck-ql ck-ql-tl">Visionaries</div>
          <div className="ck-ql ck-ql-tr">Leaders</div>
          <div className="ck-ql ck-ql-bl">Niche</div>
          <div className="ck-ql ck-ql-br">Challengers</div>

          <div className="ck-qline ck-qline-h" />
          <div className="ck-qline ck-qline-v" />

          {norm.map(p => {
            const r = 14;
            return (
              <div
                key={p.id}
                className="ck-qdot"
                style={{
                  left: `${p.nx * 100}%`,
                  bottom: `${p.ny * 100}%`,
                  width: r * 2,
                  height: r * 2,
                  marginLeft: -r,
                  marginBottom: -r,
                  background: p.color,
                  zIndex: hoverId === p.id ? 5 : 1,
                }}
                onMouseEnter={() => setHoverId(p.id)}
                onMouseLeave={() => setHoverId(null)}
                onClick={() => navigate(`/${p.id}`)}
                title={`${p.label} · ${xLabel}: ${p.x}, ${yLabel}: ${p.y}`}
              >
                <span className="ck-qdot-label">{p.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="ck-quad-table">
        <div className="ck-qt-head">
          <div style={{ flex: 2 }}>Item</div>
          <div style={{ width: 90 }}>{xLabel}</div>
          <div style={{ width: 90 }}>{yLabel}</div>
          <div style={{ width: 120 }}>{xLabel} %</div>
          <div style={{ width: 120 }}>{yLabel} %</div>
        </div>
        {norm.map(p => (
          <div
            key={p.id}
            className={`ck-qt-row ${hoverId === p.id ? 'is-hover' : ''}`}
            onMouseEnter={() => setHoverId(p.id)}
            onMouseLeave={() => setHoverId(null)}
            onClick={() => navigate(`/${p.id}`)}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ flex: 2, display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <span className="ck-qt-dot" style={{ background: p.color }} />
              <span className="ck-qt-name truncate">{p.label}</span>
            </div>
            <div style={{ width: 90, color: 'var(--fg-2)', fontFamily: 'var(--font-mono)' }}>{p.x.toLocaleString()}</div>
            <div style={{ width: 90, color: 'var(--fg-2)', fontFamily: 'var(--font-mono)' }}>{p.y.toLocaleString()}</div>
            <div style={{ width: 120 }}>
              <div className="ck-qt-bar"><div className="ck-qt-bar-fill" style={{ width: `${p.nx * 100}%`, background: p.color }} /></div>
            </div>
            <div style={{ width: 120 }}>
              <div className="ck-qt-bar"><div className="ck-qt-bar-fill" style={{ width: `${p.ny * 100}%`, background: p.color }} /></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
