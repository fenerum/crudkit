import Icon from './Icon';

export default function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  iconRight,
  shortcut,
  children,
  className = '',
  type = 'button',
  ...rest
}) {
  const sizeCls = size === 'sm' ? 'ck-btn-sm' : size === 'lg' ? 'ck-btn-lg' : '';
  const iconSize = size === 'sm' ? 12 : size === 'lg' ? 16 : 14;
  return (
    <button
      type={type}
      className={`ck-btn ck-btn-${variant} ${sizeCls} ${className}`.trim()}
      {...rest}
    >
      {icon && <Icon name={icon} size={iconSize} />}
      {children && <span>{children}</span>}
      {shortcut && (
        <span className="ck-kbd" style={{ marginLeft: 2 }}>
          {shortcut}
        </span>
      )}
      {iconRight && <Icon name={iconRight} size={iconSize} />}
    </button>
  );
}
