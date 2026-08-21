import * as React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CrudKitAPIClient from "../data/api";
import { useMenuViews } from "../hooks/useMenuViews";
import { Icon, Kbd } from "./ui";
import { getIdPrefix, isObjectTypeCode } from "../utils/crudkit";
import { detail as detailRegex } from "../utils/urls";

const SEARCH_DEBOUNCE_MS = 220;

export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate();
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const inputRef = useRef(null);
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [idx, setIdx] = useState(0);
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [directMatch, setDirectMatch] = useState(null);
  const [typeMatch, setTypeMatch] = useState(null);

  const { items: allViews } = useMenuViews({ enabled: open });
  const rootViews = allViews.filter((v) => v.show_in_menu);

  useEffect(() => {
    if (open) {
      setRawQuery("");
      setQuery("");
      setIdx(0);
      setSearchResults([]);
      setDirectMatch(null);
      setTypeMatch(null);
      // Two RAFs to make sure the modal is mounted and styled before focusing.
      requestAnimationFrame(() => requestAnimationFrame(() => inputRef.current?.focus()));
    }
  }, [open]);

  // Debounce the live query into the searchable query.
  useEffect(() => {
    const t = setTimeout(() => setQuery(rawQuery.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [rawQuery]);

  // Run search when debounced query changes. Also detect quick-access patterns:
  // a 3-letter+digits ID (e.g. "CMP1") becomes a direct-object jump, and a
  // bare 3-letter type code (e.g. "LEA") becomes a list-view jump.
  useEffect(() => {
    if (!open || !query) {
      setSearchResults([]);
      setDirectMatch(null);
      setTypeMatch(null);
      return;
    }
    let cancelled = false;
    setSearching(true);
    setDirectMatch(null);
    setTypeMatch(null);

    const upper = query.toUpperCase();

    const run = async () => {
      // 1. ID match like "CMP1234" → fetch and offer direct open.
      if (detailRegex.test(upper)) {
        const id = upper;
        const modelType = id.slice(0, 3);
        try {
          const obj = await client.retrieve(modelType, id);
          if (!cancelled && obj) {
            setDirectMatch({
              id,
              modelType,
              label: obj.label || obj.object_repr || id,
            });
          }
        } catch {
          // No such object — fall back to plain search results.
        }
      }
      // 2. Bare type code like "LEA" → offer list-view jump.
      else if (isObjectTypeCode(upper) && upper.length === 3) {
        try {
          const meta = await client.metadata(upper);
          if (!cancelled && meta) {
            setTypeMatch({
              modelType: upper,
              name: meta.verbose_name_plural || meta.verbose_name || upper,
            });
          }
        } catch {
          // Not a real type — fall through.
        }
      }

      // Always also run free-text search.
      try {
        const r = await client.search(query);
        if (!cancelled) setSearchResults(r?.results || []);
      } catch {
        if (!cancelled) setSearchResults([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    };

    run();
    return () => { cancelled = true; };
  }, [open, query, client]);

  const navItems = useMemo(() => {
    return rootViews.map((view) => ({
      kind: "nav",
      icon: "layout-grid",
      label: `Go to ${view.name || view.model}`,
      sub: view.model,
      href: view.default ? `/${view.model}` : `/${view.model}/VIW/${view.id}`,
    }));
  }, [rootViews]);

  const actionItems = useMemo(() => {
    const items = [
      { kind: "nav", icon: "inbox", label: "Open inbox", href: "/inbox", sub: "Inbox" },
      { kind: "nav", icon: "home", label: "Go to home", href: "/", sub: "Dashboard" },
      { kind: "nav", icon: "columns", label: "Browse all objects", href: "/all-objects", sub: "Objects" },
      { kind: "nav", icon: "user", label: "Open profile", href: "/profile", sub: "Account" },
    ];
    rootViews.forEach((view) => {
      items.push({
        kind: "nav",
        icon: "plus",
        label: `Create ${view.name || view.model}`,
        sub: view.model,
        href: `/${view.model}/create`,
      });
    });
    return items;
  }, [rootViews]);

  const items = useMemo(() => {
    const out = [];
    const ql = query.toLowerCase();

    if (directMatch) {
      out.push({ kind: "group", label: "Quick access" });
      out.push({
        kind: "quick",
        icon: "arrow-right-circle",
        label: `Open ${directMatch.label}`,
        sub: directMatch.id,
        href: `/${directMatch.id}`,
      });
    } else if (typeMatch) {
      out.push({ kind: "group", label: "Quick access" });
      out.push({
        kind: "quick",
        icon: "layout-grid",
        label: `View all ${typeMatch.name.toLowerCase()}`,
        sub: typeMatch.modelType,
        href: `/${typeMatch.modelType}`,
      });
      out.push({
        kind: "quick",
        icon: "plus",
        label: `Create ${typeMatch.name.toLowerCase().replace(/s$/, "")}`,
        sub: typeMatch.modelType,
        href: `/${typeMatch.modelType}/create`,
      });
    }

    if (searchResults.length > 0) {
      const groups = new Map();
      searchResults.forEach((obj) => {
        const prefix = getIdPrefix(obj.id) || "Results";
        if (!groups.has(prefix)) groups.set(prefix, []);
        groups.get(prefix).push(obj);
      });
      groups.forEach((rows, prefix) => {
        out.push({ kind: "group", label: prefix });
        rows.forEach((obj) => {
          out.push({
            kind: "result",
            id: obj.id,
            label: obj.label || obj.object_repr || obj.id,
            sub: obj.id,
            href: `/${obj.id}`,
          });
        });
      });
    }

    const navMatching = navItems.filter((it) =>
      !ql || it.label.toLowerCase().includes(ql)
    );
    if (navMatching.length) {
      out.push({ kind: "group", label: "Navigation" });
      navMatching.forEach((it) => out.push(it));
    }

    const actionMatching = actionItems.filter((it) =>
      !ql || it.label.toLowerCase().includes(ql)
    );
    if (actionMatching.length) {
      out.push({ kind: "group", label: "Actions" });
      actionMatching.forEach((it) => out.push(it));
    }
    return out;
  }, [searchResults, query, navItems, actionItems, directMatch, typeMatch]);

  const selectableIndexes = useMemo(
    () => items.map((it, i) => (it.kind === "group" ? -1 : i)).filter((i) => i >= 0),
    [items]
  );
  const currentSelectableIdx = selectableIndexes[idx] ?? -1;

  const move = (delta) => {
    setIdx((i) => {
      const n = selectableIndexes.length;
      if (n === 0) return 0;
      return (i + delta + n) % n;
    });
  };

  const activate = (item) => {
    if (!item || !item.href) {
      onClose();
      return;
    }
    onClose();
    setTimeout(() => navigate(item.href), 0);
  };

  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const item = items[currentSelectableIdx];
      activate(item);
    }
  };

  if (!open) return null;

  return (
    <div className="ck-cmd-backdrop" onClick={onClose}>
      <div className="ck-cmd" onClick={(e) => e.stopPropagation()} onKeyDown={onKey}>
        <div className="flex items-center gap-2.5 px-3.5 py-3 border-b border-border-1">
          <Icon name="search" size={16} color="var(--fg-3)" />
          <input
            ref={inputRef}
            value={rawQuery}
            onChange={(e) => { setRawQuery(e.target.value); setIdx(0); }}
            placeholder="Search objects, navigate, or run actions…"
            className="flex-1 bg-transparent border-none outline-none text-fg-1 text-lg placeholder:text-fg-3 font-sans"
          />
          {searching && (
            <span className="text-2xs text-fg-3">Searching…</span>
          )}
          <Kbd>ESC</Kbd>
        </div>

        <div className="px-1.5 py-1.5" style={{ maxHeight: 360, overflow: "auto" }}>
          {items.length === 0 && (
            <div className="px-6 py-6 text-center text-fg-3 text-sm">
              {query ? "No matches" : "Type to search…"}
            </div>
          )}
          {items.map((item, i) => {
            if (item.kind === "group") {
              return (
                <div key={`g-${i}`} className="eyebrow px-2.5 pt-2 pb-1">
                  {item.label}
                </div>
              );
            }
            const isOn = i === currentSelectableIdx;
            const enterIdx = selectableIndexes.indexOf(i);
            return (
              <div
                key={item.id || `${item.label}-${i}`}
                className={`ck-cmd-item ${isOn ? "is-on" : ""}`}
                onMouseEnter={() => setIdx(enterIdx)}
                onClick={() => activate(item)}
              >
                <Icon name={item.icon || (item.kind === "result" ? "external-link" : "arrow-right")} size={14} color="var(--fg-2)" />
                <span className="flex-1 truncate">{item.label}</span>
                <span className="text-2xs text-fg-3 font-mono">{item.sub}</span>
                {isOn && <Kbd>↵</Kbd>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
