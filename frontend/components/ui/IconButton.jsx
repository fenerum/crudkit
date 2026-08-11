import * as React from 'react';
import Icon from './Icon';

export default function IconButton({ icon, size = 'md', className = '', ...rest }) {
  const sizeCls = size === 'sm' ? 'ck-icon-btn-sm' : '';
  const iconSize = size === 'sm' ? 12 : 14;
  return (
    <button type="button" className={`ck-icon-btn ${sizeCls} ${className}`.trim()} {...rest}>
      <Icon name={icon} size={iconSize} />
    </button>
  );
}
