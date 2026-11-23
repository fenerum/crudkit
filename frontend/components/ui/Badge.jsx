import Dot from './Dot';

// A dotted badge is tinted in its dot's hue (status pill); plain ones stay neutral.
export default function Badge({ children, dot, style }) {
  const tone = dot ? { color: dot, background: `color-mix(in srgb, ${dot} 10%, transparent)` } : null;
  return (
    <span className="ck-badge" style={{ ...tone, ...style }}>
      {dot && <Dot color={dot} size={5} />}
      {children}
    </span>
  );
}
