import { createContext, useContext } from 'react';

export const CommandPaletteContext = createContext({
  open: false,
  setOpen: () => {},
});

export function useCommandPalette() {
  return useContext(CommandPaletteContext);
}
