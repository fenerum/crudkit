import { mapIcon } from './iconMap';

export default function Icon({ name, size = 14, color = 'currentColor', style = undefined, ...rest }) {
  const Component = mapIcon(name);
  return (
    <Component
      size={size}
      color={color}
      style={{ flexShrink: 0, ...(style || {}) }}
      {...rest}
    />
  );
}
