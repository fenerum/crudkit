import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import Kbd from "./Kbd";
import { useHotkeys } from "react-hotkeys-hook";

// items: [{ label, icon?, onSelect, tone?: 'default'|'danger', href?, shortcut? }]
// `shortcut` is the single-key trigger shown as a Kbd hint. If omitted, the
// item is auto-assigned the next available digit (1–9). Pass an empty string
// to opt out of any shortcut.
// Renders a labeled "Actions" button with a keyboard shortcut and a menu
// anchored below-right.
export default function OverflowMenu({
  items,
  label = "Actions",
  shortcut = ".",
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const wrapRef = useRef(null);
  const triggerRef = useRef(null);

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);
  const openMenu = useCallback(() => {
    setActiveIndex(0);
    setOpen(true);
  }, []);
  const toggle = useCallback(() => {
    setOpen((o) => {
      const next = !o;
      if (next) setActiveIndex(0);
      return next;
    });
  }, []);

  useHotkeys(shortcut, (e) => {
    if (!items || items.length === 0) return;
    e?.preventDefault?.();
    toggle();
  }, { preventDefault: true });

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  if (!items || items.length === 0) return null;

  // Resolve a single-key shortcut per item: explicit `shortcut` wins, otherwise
  // auto-assign the next 1–9. An empty string opts out entirely.
  const shortcuts = (() => {
    const map = new Array(items.length).fill(null);
    let n = 1;
    items.forEach((it, i) => {
      if (typeof it.shortcut === "string") {
        if (it.shortcut !== "") map[i] = it.shortcut;
        return;
      }
      if (n <= 9) {
        map[i] = String(n);
        n += 1;
      }
    });
    return map;
  })();

  const onMenuKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % items.length);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + items.length) % items.length);
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      setActiveIndex(0);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      setActiveIndex(items.length - 1);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const it = items[activeIndex];
      setOpen(false);
      triggerRef.current?.focus();
      it?.onSelect?.();
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    // Match the pressed key against each item's resolved shortcut.
    if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const pressed = e.key.toLowerCase();
      const idx = shortcuts.findIndex((s) => s != null && s.toLowerCase() === pressed);
      if (idx !== -1) {
        e.preventDefault();
        const it = items[idx];
        setOpen(false);
        triggerRef.current?.focus();
        it.onSelect?.();
      }
    }
  };

  return (
    <div ref={wrapRef} className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        onClick={toggle}
        onKeyDown={(e) => {
          if (!open && (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            openMenu();
          }
        }}
        aria-haspopup="menu"
        aria-expanded={open}
        className="ck-btn ck-btn-secondary ck-btn-sm"
      >
        {label}
        <Icon name="chevron-down" size={11} color="currentColor" />
        {shortcut && <Kbd>{shortcut}</Kbd>}
      </button>
      {open && (
        <div
          role="menu"
          tabIndex={-1}
          autoFocus
          onKeyDown={onMenuKeyDown}
          ref={(el) => el && el.focus()}
          className="absolute right-0 mt-1 z-50 min-w-[180px] rounded-md border border-border-2 bg-bg-4 shadow-menu p-1 outline-none"
          style={{ top: '100%' }}
        >
          {items.map((it, i) => {
            const isActive = i === activeIndex;
            const toneCls = it.tone === "danger" ? "text-danger" : "text-fg-1";
            const bgCls = isActive ? "bg-bg-5" : "";
            return (
              <button
                key={i}
                role="menuitem"
                type="button"
                tabIndex={-1}
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => {
                  setOpen(false);
                  triggerRef.current?.focus();
                  it.onSelect?.();
                }}
                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-sm text-sm font-sans ${toneCls} ${bgCls}`}
              >
                {it.icon && <Icon name={it.icon} size={13} color="currentColor" />}
                <span className="flex-1 text-left">{it.label}</span>
                {shortcuts[i] != null && <Kbd>{shortcuts[i]}</Kbd>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
