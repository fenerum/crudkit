import { describe, expect, it } from 'vitest';

import { listQueryKey } from '../../utils/queryKeys';


describe('listQueryKey', () => {
  it('includes URL filters', () => {
    const open = listQueryKey('CUS', undefined, 1, '', null, { status: 'open' });
    const closed = listQueryKey('CUS', undefined, 1, '', null, { status: 'closed' });

    expect(open).not.toEqual(closed);
  });

  it('normalizes filter order', () => {
    const first = listQueryKey('CUS', 'VIW1', 2, 'acme', 25, { owner: '1', status: 'open' });
    const second = listQueryKey('CUS', 'VIW1', 2, 'acme', 25, { status: 'open', owner: '1' });

    expect(first).toEqual(second);
  });
});
