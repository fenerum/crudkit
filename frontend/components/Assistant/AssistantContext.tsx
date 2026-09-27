import { createContext, useContext } from 'react';

export const AssistantContext = createContext<{
  enabled: boolean;
  open: boolean;
  setOpen: (open: boolean) => void;
}>({ enabled: false, open: false, setOpen: () => {} });

export function useAssistant() {
  return useContext(AssistantContext);
}
