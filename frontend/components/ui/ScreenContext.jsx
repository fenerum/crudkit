import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

// What the user currently has on screen, for the assistant sidebar.
//
// Most of it comes from the URL (route, record, view, search, filters, page,
// tab). Pages add what only they know — the resolved default view, the ids of
// the rows they render, the selection — with `useScreenContext`. Like
// TopbarSlots, the context is split so publishing pages don't re-render when
// the screen changes.
const ScreenValueContext = createContext({});
const ScreenSetterContext = createContext(() => {});

const TYPE_RE = /^[A-Z]{3}$/;
const CK_ID_RE = /^[A-Z]{3}\d+$/;
const NON_FILTER_PARAMS = new Set(["q", "page", "page_size", "tab"]);

export function screenFromLocation(pathname, search) {
  const params = new URLSearchParams(search);
  const [segment, sub, viewId] = pathname.split("/").filter(Boolean);
  const screen = { path: pathname, route: "other" };
  if (!segment) {
    screen.route = "dashboard";
  } else if (segment === "inbox") {
    screen.route = "inbox";
  } else if (CK_ID_RE.test(segment) && !sub) {
    screen.route = "detail";
    screen.record_id = segment;
    screen.type_id = segment.slice(0, 3);
    if (params.get("tab")) screen.tab = params.get("tab");
  } else if (TYPE_RE.test(segment) && (!sub || (sub === "VIW" && viewId))) {
    screen.route = "list";
    screen.type_id = segment;
    if (viewId) screen.view_id = `VIW${viewId.replace(/^VIW/, "")}`;
    if (params.get("q")) screen.q = params.get("q");
    const page = parseInt(params.get("page") || "1", 10);
    if (page > 1) screen.page = page;
    const filters = {};
    params.forEach((value, key) => {
      if (!NON_FILTER_PARAMS.has(key)) filters[key] = value;
    });
    if (Object.keys(filters).length) screen.filters = filters;
  }
  return screen;
}

export function ScreenProvider({ children }) {
  const { pathname, search } = useLocation();
  const [published, setPublished] = useState({});
  const fromUrl = useMemo(() => screenFromLocation(pathname, search), [pathname, search]);
  const screen = useMemo(() => ({ ...fromUrl, ...published }), [fromUrl, published]);
  return (
    <ScreenSetterContext.Provider value={setPublished}>
      <ScreenValueContext.Provider value={screen}>{children}</ScreenValueContext.Provider>
    </ScreenSetterContext.Provider>
  );
}

export function useScreen() {
  return useContext(ScreenValueContext);
}

// Publish screen keys while mounted; they are removed again on unmount.
// Publishers must use distinct keys.
export function useScreenContext(partial) {
  const setPublished = useContext(ScreenSetterContext);
  const serialized = JSON.stringify(partial);
  const keysRef = useRef([]);

  useEffect(() => {
    const next = JSON.parse(serialized);
    const previousKeys = keysRef.current;
    keysRef.current = Object.keys(next);
    setPublished((prev) => ({ ...without(prev, previousKeys), ...next }));
  }, [serialized, setPublished]);

  useEffect(() => () => setPublished((prev) => without(prev, keysRef.current)), [setPublished]);
}

function without(obj, keys) {
  const out = { ...obj };
  keys.forEach((key) => delete out[key]);
  return out;
}
