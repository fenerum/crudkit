import * as React from "react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ReadOnlyField from "./ReadOnlyField.jsx";
import { url } from "../utils/urls";
import { Avatar, Icon, colorForStage } from "./ui";
import { hashName } from "./ui/avatarPalette";

// Returns the per-card thumb hue & glyph deterministically from the object's
// label/id so the gallery feels designed without metadata-driven colors.
function thumbStyle(label) {
  const palette = [
    'var(--stage-blue)', 'var(--stage-violet)', 'var(--stage-amber)',
    'var(--stage-green)', 'var(--stage-rose)', 'var(--stage-slate)',
    'var(--primary-400)',
  ];
  const idx = hashName(label || '') % palette.length;
  return palette[idx];
}

function glyphFor(label) {
  const s = String(label || '').trim();
  if (!s) return '·';
  return s[0].toUpperCase();
}

function Card({ object, view, fields, metadata }) {
  const fieldList = view ? Object.values(view.fields) : (fields || []);
  const titleField = fieldList[0];
  const subField = fieldList[1];
  const thumbHue = thumbStyle(object.label || object.id);

  // The "category" eyebrow tries the second field, falling back to model name.
  const category = subField && metadata.fields[subField]
    ? metadata.fields[subField].verbose_name
    : metadata.verbose_name;

  return (
    <Link to={url(object.id)} className="ck-gal-card">
      {object.object_images && object.object_images.length > 0 ? (
        <div className="ck-gal-thumb" style={{ background: 'var(--bg-3)' }}>
          <img
            src={object.object_images[0]}
            alt={object.label || object.id}
          />
          <span
            className="ck-gal-thumb-tint"
            style={{
              background:
                `linear-gradient(135deg, color-mix(in oklab, ${thumbHue} 22%, transparent) 0%, color-mix(in oklab, ${thumbHue} 6%, transparent) 100%)`,
            }}
          />
        </div>
      ) : (
        <div
          className="ck-gal-thumb"
          style={{
            background:
              `linear-gradient(135deg, color-mix(in oklab, ${thumbHue} 22%, transparent) 0%, color-mix(in oklab, ${thumbHue} 6%, transparent) 100%)`,
          }}
        >
          <span className="ck-gal-glyph" style={{ color: thumbHue }}>
            {glyphFor(object.label || object.id)}
          </span>
        </div>
      )}
      <div className="ck-gal-meta">
        <div className="ck-gal-cat">{category}</div>
        <div className="ck-gal-name">
          {titleField ? (
            <ReadOnlyField value={object[titleField]} metadata={metadata.fields[titleField]} link={false} />
          ) : (
            object.label || object.id
          )}
        </div>
        <div className="ck-gal-foot">
          {object.created_by?.label && (
            <>
              <Avatar name={object.created_by.label} size={16} />
              <span className="ck-gal-author">{object.created_by.label}</span>
              <span className="ck-gal-sep">·</span>
            </>
          )}
          {object.updated_at && (
            <span className="ck-gal-time">
              {new Date(object.updated_at).toLocaleDateString()}
            </span>
          )}
          <span className="ck-gal-spacer" />
          <span className="ck-gal-reads font-mono text-xs text-fg-3">{object.id}</span>
        </div>
      </div>
    </Link>
  );
}

export default function Gallery({ objectList, view, fields, model, metadata, q = '' }) {
  // Build category filter buttons from the choices of the second field if
  // available — keeps the design's "All / Onboarding / Security" bar useful
  // without bespoke metadata.
  const categoryField = useMemo(() => {
    const candidates = view ? Object.values(view.fields).slice(1, 4) : [];
    return candidates.find((f) => {
      const meta = metadata.fields[f];
      return meta && Array.isArray(meta.choices) && meta.choices.length > 0;
    }) || null;
  }, [view, metadata]);

  const categories = useMemo(() => {
    if (!categoryField) return [];
    return metadata.fields[categoryField].choices.map(([value, label]) => ({ value, label }));
  }, [categoryField, metadata]);

  const [active, setActive] = useState('All');
  const visible = useMemo(() => {
    let next = objectList;
    if (categoryField && active !== 'All') {
      next = next.filter(obj => {
        const v = obj[categoryField];
        const compare = typeof v === 'object' && v?.id != null ? v.id : v;
        return String(compare) === String(active);
      });
    }
    const ql = q.trim().toLowerCase();
    if (ql) {
      const fieldList = view ? Object.values(view.fields) : (fields || []);
      next = next.filter(obj => {
        if (String(obj.id || '').toLowerCase().includes(ql)) return true;
        if (String(obj.label || '').toLowerCase().includes(ql)) return true;
        return fieldList.some(field => {
          const value = obj[field];
          if (value == null) return false;
          if (typeof value === 'object' && value.label) return value.label.toLowerCase().includes(ql);
          return String(value).toLowerCase().includes(ql);
        });
      });
    }
    return next;
  }, [objectList, categoryField, active, q, view, fields]);

  return (
    <div className="ck-gal-wrap">
      {categories.length > 0 && (
        <div className="ck-gal-head">
          <div>
            <div className="ck-gal-sub">{objectList.length} {objectList.length === 1 ? 'item' : 'items'}</div>
          </div>
          <div className="ck-gal-filters">
            <button
              type="button"
              className={`ck-gf ${active === 'All' ? 'is-on' : ''}`}
              onClick={() => setActive('All')}
            >
              All
            </button>
            {categories.map(c => (
              <button
                key={c.value}
                type="button"
                className={`ck-gf ${String(active) === String(c.value) ? 'is-on' : ''}`}
                onClick={() => setActive(c.value)}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {visible.length === 0 ? (
        <div className="rounded-lg border border-border-1 bg-bg-2 p-10 text-center text-fg-3 text-sm">
          Nothing here yet.
        </div>
      ) : (
        <div className="ck-gallery">
          {visible.map(obj => (
            <Card
              key={obj.id}
              object={obj}
              view={view}
              fields={fields}
              metadata={metadata}
            />
          ))}
        </div>
      )}
    </div>
  );
}
