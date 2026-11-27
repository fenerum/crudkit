import { mapIcon } from './iconMap';

export default function Icon({ name, size = 14, color = 'currentColor', strokeWidth = 1.5, style = undefined, ...rest }) {
  const Component = mapIcon(name);
  return (
    <Component
      size={size}
      color={color}
      strokeWidth={strokeWidth}
      style={{ flexShrink: 0, ...(style || {}) }}
      {...rest}
    />
  );
}
