import { createContext, useContext } from 'react';

export const PageSearchContext = createContext({
  registerInput: () => () => {},
  focus: () => false,
});

export function usePageSearch() {
  return useContext(PageSearchContext);
}
