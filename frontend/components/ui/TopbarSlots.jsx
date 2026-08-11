import * as React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

// Slot shape:
//   title?:        { eyebrow?: string, label: string, subtitle?: string }
//   middle?:       ReactNode
//   viewSwitch?:   ReactNode
//   pageSearch?:   ReactNode
//   right?:        ReactNode
//   primary?:      ReactNode
//
// We split the context: the *value* updates whenever slots change, but the
// *setter* is stable. Pages that only register slots (`useTopbarSlots`) read
// the setter, so a slot change does not re-render every page that registered
// one — it only re-renders the topbar that actually displays the slots. This
// avoids the render loop when a builder's deps are not perfectly stable.
const SlotsValueContext = createContext({});
const SlotsSetterContext = createContext(() => {});

export function TopbarSlotsProvider({ children }) {
  const [slots, setSlotsState] = useState({});
  const setSlots = useCallback((next) => {
    setSlotsState(next || {});
  }, []);
  return (
    <SlotsSetterContext.Provider value={setSlots}>
      <SlotsValueContext.Provider value={slots}>{children}</SlotsValueContext.Provider>
    </SlotsSetterContext.Provider>
  );
}

export function useTopbarSlotsValue() {
  return useContext(SlotsValueContext);
}

// Per-route hook: register slot content while mounted, clear on unmount.
// `deps` controls when the slots are rebuilt — pass the values the builder
// closes over. Defaults to running once per mount.
export function useTopbarSlots(slotsBuilder, deps) {
  const setSlots = useContext(SlotsSetterContext);
  // Capture the latest builder in a ref so the effect only re-fires when the
  // caller's deps change, not on every render.
  const builderRef = useRef(slotsBuilder);
  builderRef.current = slotsBuilder;

  useEffect(() => {
    setSlots(builderRef.current());
    return () => setSlots({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps || []);
}
