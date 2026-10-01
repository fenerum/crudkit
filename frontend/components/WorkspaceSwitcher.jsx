import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { appConfig } from "../utils/appConfig";
import AppLogo from "./AppLogo";
import { Icon } from "./ui";

// Sidebar-header workspace picker. Replaces the plain home link when the
// deployment has at least one workspace; selecting one swaps the sidebar's
// shared section for that workspace's pinned views.
export default function WorkspaceSwitcher({ workspaces, activeWorkspace, onSelect, userName }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const select = (workspaceId) => {
    setOpen(false);
    onSelect(workspaceId);
  };
  const go = (path) => {
    setOpen(false);
    navigate(path);
  };

  const itemCls =
    "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-sm text-sm font-sans text-fg-1 hover:bg-bg-5";

  const menuItem = ({ key, icon, label, checked, onClick }) => (
    <button key={key} role="menuitem" type="button" onClick={onClick} className={itemCls}>
      <Icon name={icon} size={13} color="currentColor" />
      <span className="flex-1 text-left truncate">{label}</span>
      {checked && <Icon name="check" size={13} color="currentColor" />}
    </button>
  );

  return (
    <div ref={wrapRef} className="relative" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-bg-2 text-left"
      >
        <AppLogo />
        <span className="flex-1 min-w-0">
          <span className="block text-sm font-semibold text-fg-1 truncate">
            {activeWorkspace ? activeWorkspace.name : appConfig.org_name}
          </span>
          <span className="block text-2xs text-fg-3">{userName}</span>
        </span>
        <Icon name="chevrons-up-down" size={14} color="var(--fg-3)" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 right-0 z-50 mt-1 rounded-md border border-border-2 bg-bg-4 shadow-menu p-1"
          style={{ top: '100%' }}
        >
          {menuItem({
            key: 'all',
            icon: 'columns',
            label: 'All',
            checked: !activeWorkspace,
            onClick: () => select(null),
          })}
          {workspaces.map((workspace) =>
            menuItem({
              key: workspace.id,
              icon: workspace.icon || 'layout-grid',
              label: workspace.name || 'Untitled',
              checked: activeWorkspace?.id === workspace.id,
              onClick: () => select(workspace.id),
            })
          )}
          <div className="my-1 border-t border-border-1" />
          {menuItem({
            key: 'new',
            icon: 'plus',
            label: 'New workspace',
            onClick: () => go('/WSP/create'),
          })}
          {activeWorkspace &&
            menuItem({
              key: 'edit',
              icon: 'edit-3',
              label: 'Edit workspace',
              onClick: () => go(`/${activeWorkspace.id}/edit`),
            })}
        </div>
      )}
    </div>
  );
}
