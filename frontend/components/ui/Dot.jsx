
export default function Dot({ color = 'var(--fg-3)', size = 8, style }) {
  return (
    <span
      className="ck-dot"
      style={{ background: color, width: size, height: size, ...style }}
    />
  );
}
