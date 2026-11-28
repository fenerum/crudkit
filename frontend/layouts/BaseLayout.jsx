import * as React from "react";
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {useQueries} from "@tanstack/react-query";
import {RealtimeProvider, useRealtimeConnected} from "@/data/realtime";
import {Link, Outlet, useLocation, useNavigate} from "react-router-dom";
import {useAuth} from "../context/AuthContext";
import {WorkspaceProvider, useWorkspace} from "../context/WorkspaceContext";
import {isMine, isVisibleToUser, useMenuViews, useWorkspaces, viewBadgeQuery} from "../hooks/useMenuViews";
import {resolveWorkspaceViews} from "../utils/workspaces";
import AppLogo from "../components/AppLogo";
import faviconUrl from "../images/favicon.svg";
import {appConfig} from "../utils/appConfig";
import TimeTracker from "../components/TimeTracker";
import Breadcrumbs from "../components/Breadcrumbs";
import CommandPalette from "../components/CommandPalette";
import JobTray from "../components/JobTray";
import {useDocumentTitle} from "../hooks/useDocumentTitle";
import {usePendingProposals} from "../hooks/usePendingProposals";
import {useHotkeys} from "react-hotkeys-hook";
import {ASSISTANT_OVERLAY_QUERY, NAV_OVERLAY_QUERY, useMediaQuery} from "../hooks/useMediaQuery";
import {Avatar, hasIcon, Icon, initialsFromName, Kbd, ScreenProvider, ThemeToggle, TopbarSlotsProvider, useTopbarSlotsValue} from "../components/ui";
import {CommandPaletteContext} from "../components/ui/CommandPaletteContext";
import {PageSearchContext} from "../components/ui/PageSearchContext";
import AssistantSidebar from "../components/Assistant/AssistantSidebar";
import {AssistantContext, useAssistant} from "../components/Assistant/AssistantContext";

const ASSISTANT_OPEN_KEY = "crudkit.assistant.open";
const NAV_COLLAPSED_KEY = "crudkit.nav.collapsed";
const LAYOUT_ICONS = {
  list: 'table-2',
  kanban: 'kanban',
  gallery: 'layout-grid',
  swimlane: 'rows',
  conversation: 'messages-square',
  quadrant: 'scatter-chart',
};

// A view's own icon, else its layout's.
function viewIcon(view) {
  return hasIcon(view.icon) ? view.icon : LAYOUT_ICONS[view.layout] || 'table-2';
}

function viewHref(view) {
  return view.default ? `/${view.model}` : `/${view.model}/VIW/${view.id}`;
}

// A link when given `href`, else a button.
function LinkOrButton({href, className, children, ...rest}) {
  if (href) {
    return <Link to={href} className={className} {...rest}>{children}</Link>;
  }
  return <button type="button" className={className} {...rest}>{children}</button>;
}

const NavItem = React.memo(function NavItem({href, icon, label, count, active, onClick}) {
  return (
    <LinkOrButton href={href} onClick={onClick} className={"ck-navleaf" + (active ? " is-active" : "")}>
      <span className="ck-navleaf-ico">
        <Icon name={icon} size={15} color="currentColor" />
      </span>
      <span className="ck-navleaf-label">{label}</span>
      {count != null && count > 0 && <span className="ck-navleaf-count">{count}</span>}
    </LinkOrButton>
  );
});

function NavSection({title, action, children}) {
  return (
    <div className="flex flex-col">
      {title && (
        <div className="ck-navpanel-section eyebrow">
          <span className="truncate">{title}</span>
          {action}
        </div>
      )}
      <div className="flex flex-col gap-px">{children}</div>
    </div>
  );
}

// The rail label under the icon is aria-hidden, so the accessible name comes
// from aria-label.
// Without an icon the item shows the label's initials.
function RailItem({href, icon, label, active, badge, onClick, ariaLabel}) {
  return (
    <LinkOrButton
      href={href}
      onClick={onClick}
      className={"ck-rail-item" + (active ? " is-active" : "")}
      aria-label={ariaLabel || label}
      aria-current={href && active ? "page" : undefined}
      aria-pressed={!href ? !!active : undefined}
      title={ariaLabel || label}
    >
      <span className="ck-rail-ico">
        {icon
          ? <Icon name={icon} size={18} color="currentColor" />
          : <span className="ck-rail-initials" aria-hidden="true">{initialsFromName(label)}</span>}
        <span className="ck-rail-label" aria-hidden="true">{label}</span>
        {badge > 0 && <span className="ck-rail-badge">{badge}</span>}
      </span>
    </LinkOrButton>
  );
}

function Topbar({ navOverlay, navCollapsed, onOpenNav }) {
  const slots = useTopbarSlotsValue();
  const assistant = useAssistant();
  const sidebarLabel = navOverlay ? "Open sidebar" : "Show sidebar";
  return (
    <header className="ck-topbar relative z-40 flex items-center gap-1.5 sm:gap-2 px-3 sm:px-4 flex-shrink-0">
      {(navOverlay || navCollapsed) && (
        <button
          type="button"
          className="ck-icon-btn ck-icon-btn-sm"
          onClick={onOpenNav}
          aria-label={sidebarLabel}
          title={sidebarLabel}
        >
          <Icon name="panel-left" size={14} color="currentColor" />
        </button>
      )}

      <nav className="ck-crumbs" aria-label="Breadcrumb">
        <Link to="/" className="text-fg-3 hover:text-fg-1 transition-colors duration-fast inline-flex items-center" aria-label="Home">
          <Icon name="home" size={14} color="currentColor" />
        </Link>
        <ol role="list" className="flex items-center gap-2 min-w-0">
          <Breadcrumbs />
        </ol>
      </nav>

      {slots.title && slots.title.label && (
        <span className="ck-topbar-title">{slots.title.label}</span>
      )}

      {/* Middle slot: the page's tabs, continuing the breadcrumbs */}
      <div className="ck-topbar-middle">
        {slots.middle && (
          <>
            <Icon name="chevron-right" size={12} color="var(--fg-4)" className="self-center flex-shrink-0" />
            {slots.middle}
          </>
        )}
      </div>

      {slots.pageSearch && <div className="ck-topbar-search">{slots.pageSearch}</div>}

      <div className="ck-topbar-actions">
        {slots.viewSwitch}
        {slots.right}
        <div className="hidden md:flex items-center">
          <TimeTracker />
        </div>
        {slots.primary}
        {assistant.enabled && (
          <button
            type="button"
            className={"ck-btn ck-btn-secondary" + (assistant.open ? " text-link" : "")}
            onClick={() => assistant.setOpen(!assistant.open)}
            aria-label="Toggle assistant"
            aria-pressed={assistant.open}
            title="Assistant (⌘J)"
          >
            <Icon name="sparkles" size={14} color="currentColor" />
            <span className="hidden sm:inline">Assistant</span>
            <span className="hidden sm:inline-flex"><Kbd>⌘J</Kbd></span>
          </button>
        )}
      </div>
    </header>
  );
}

export default function BaseLayout() {
  return (
    <WorkspaceProvider>
      <RealtimeProvider>
        <BaseLayoutInner />
      </RealtimeProvider>
    </WorkspaceProvider>
  );
}

function BaseLayoutInner() {
  const {pathname} = useLocation();
  const navigate = useNavigate();
  const {user} = useAuth();
  useDocumentTitle();

  const [paletteOpen, setPaletteOpen] = useState(false);

  const assistantEnabled = !!user?.assistant?.enabled;
  const [assistantOpen, setAssistantOpenState] = useState(() => localStorage.getItem(ASSISTANT_OPEN_KEY) === "1");
  const setAssistantOpen = useCallback((open) => {
    localStorage.setItem(ASSISTANT_OPEN_KEY, open ? "1" : "0");
    setAssistantOpenState(open);
  }, []);
  const assistantValue = useMemo(
    () => ({enabled: assistantEnabled, open: assistantEnabled && assistantOpen, setOpen: setAssistantOpen}),
    [assistantEnabled, assistantOpen, setAssistantOpen]
  );

  // Track the currently-mounted page-search input (if any) so "/" can focus it
  // instead of opening the palette.
  const pageSearchInputRef = useRef(null);
  const pageSearchValue = useMemo(() => ({
    registerInput: (ref) => {
      pageSearchInputRef.current = ref;
      return () => {
        if (pageSearchInputRef.current === ref) pageSearchInputRef.current = null;
      };
    },
    focus: () => {
      const el = pageSearchInputRef.current?.current;
      if (el && typeof el.focus === 'function') {
        el.focus();
        if (typeof el.select === 'function') el.select();
        return true;
      }
      return false;
    },
  }), []);

  // ⌘K / Ctrl+K opens the command palette.
  useHotkeys('mod+k', (e) => {
    e?.preventDefault?.();
    setPaletteOpen(true);
  });

  // ⌘J / Ctrl+J toggles the assistant sidebar, also from inside its textarea.
  useHotkeys('mod+j', (e) => {
    e?.preventDefault?.();
    if (assistantEnabled) setAssistantOpen(!assistantOpen);
  }, {enableOnFormTags: true}, [assistantEnabled, assistantOpen, setAssistantOpen]);

  // "/" focuses the page-search input on list-style views; falls back to the
  // command palette so the muscle memory keeps working elsewhere.
  useHotkeys('/', (e) => {
    if (paletteOpen) return;
    const tag = (e?.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || (e?.target && e.target.isContentEditable)) return;
    e?.preventDefault?.();
    if (!pageSearchValue.focus()) setPaletteOpen(true);
  });

  useEffect(() => {
    let link = document.querySelector("link[rel~='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.getElementsByTagName('head')[0].appendChild(link);
    }
    link.href = faviconUrl;
  }, []);

  const {isPending, items: menuViews} = useMenuViews();
  const {isPending: workspacesPending, items: allWorkspaces} = useWorkspaces();
  const {activeWorkspaceId, setActiveWorkspaceId} = useWorkspace();

  // Group views by ownership: public views show under "Workspace"; private
  // views the current user created show under "My Views".
  const userId = user?.id;
  const myViews = useMemo(() => menuViews.filter(v => !v.public && isMine(v, userId)), [menuViews, userId]);
  const workspaceViews = useMemo(() => menuViews.filter(v => v.public), [menuViews]);

  const visibleWorkspaces = useMemo(
    () => allWorkspaces.filter(w => isVisibleToUser(w, userId)),
    [allWorkspaces, userId]
  );
  const activeWorkspace = useMemo(
    () => visibleWorkspaces.find(w => String(w.id) === String(activeWorkspaceId)) || null,
    [visibleWorkspaces, activeWorkspaceId]
  );
  const workspaceTabs = useMemo(
    () => resolveWorkspaceViews(activeWorkspace, workspaceViews),
    [activeWorkspace, workspaceViews]
  );

  // Clear a stale stored workspace id (deleted, or not visible to this user).
  useEffect(() => {
    if (activeWorkspaceId && !workspacesPending && !activeWorkspace) {
      setActiveWorkspaceId(null);
    }
  }, [activeWorkspaceId, workspacesPending, activeWorkspace, setActiveWorkspaceId]);

  // Only count views currently displayed in the sidebar.
  const viewsWithBadges = useMemo(() => {
    const displayed = activeWorkspace ? [...workspaceTabs, ...myViews] : [...workspaceViews, ...myViews];
    const badged = new Map();
    displayed.forEach((v) => {
      if (v.show_badge_in_menu && !badged.has(v.id)) badged.set(v.id, v);
    });
    return [...badged.values()];
  }, [activeWorkspace, workspaceTabs, myViews, workspaceViews]);

  const realtimeConnected = useRealtimeConnected();
  const badgeQueries = useQueries({
    queries: viewsWithBadges.map((view) => viewBadgeQuery(view, realtimeConnected)),
  });
  const badgeCounts = Object.fromEntries(viewsWithBadges.map((view, i) => [view.id, badgeQueries[i]?.data?.count]));
  const pendingProposals = usePendingProposals();

  const navOverlay = useMediaQuery(NAV_OVERLAY_QUERY);
  const assistantOverlay = useMediaQuery(ASSISTANT_OVERLAY_QUERY);
  const [navCollapsed, setNavCollapsedState] = useState(() => localStorage.getItem(NAV_COLLAPSED_KEY) === "1");
  const setNavCollapsed = useCallback((collapsed) => {
    localStorage.setItem(NAV_COLLAPSED_KEY, collapsed ? "1" : "0");
    setNavCollapsedState(collapsed);
  }, []);
  // Below the nav breakpoint the panel is an overlay, closed by default.
  const [navOpen, setNavOpen] = useState(false);
  const showNav = useCallback(() => (navOverlay ? setNavOpen(true) : setNavCollapsed(false)), [navOverlay, setNavCollapsed]);
  const hideNav = useCallback(() => (navOverlay ? setNavOpen(false) : setNavCollapsed(true)), [navOverlay, setNavCollapsed]);

  const handleNavClick = useCallback(() => setNavOpen(false), []);
  const selectWorkspace = useCallback((id) => {
    setActiveWorkspaceId(id);
    showNav();
  }, [setActiveWorkspaceId, showNav]);
  // A workspace opens on its first view, so the page matches the menu beside it.
  const openWorkspace = useCallback((workspace) => {
    selectWorkspace(workspace.id);
    const first = resolveWorkspaceViews(workspace, workspaceViews)[0];
    if (first) navigate(viewHref(first));
  }, [selectWorkspace, workspaceViews, navigate]);

  const closeOverlays = useCallback(() => {
    setNavOpen(false);
    if (assistantOverlay) setAssistantOpen(false);
  }, [assistantOverlay, setAssistantOpen]);
  const scrim = (navOverlay && navOpen) || (assistantOverlay && assistantValue.open);

  const userName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : (user?.username || 'User');

  const shellClass = "ck-shell"
    + (assistantValue.open ? " with-assistant" : "")
    + (navCollapsed && !navOverlay ? " is-nav-collapsed" : "")
    + (navOverlay && navOpen ? " is-nav-open" : "");

  return (
    <CommandPaletteContext.Provider value={{open: paletteOpen, setOpen: setPaletteOpen}}>
      <AssistantContext.Provider value={assistantValue}>
      <PageSearchContext.Provider value={pageSearchValue}>
      <ScreenProvider>
      <TopbarSlotsProvider>
      <div className={shellClass}>
        <nav className="ck-rail" aria-label="Workspaces">
          <Link
            to="/"
            className="ck-rail-logo"
            aria-label={appConfig.app_name}
            title={appConfig.crudkit_version ? `crudkit v${appConfig.crudkit_version}` : undefined}
            onClick={handleNavClick}
          >
            <AppLogo />
            {appConfig.crudkit_version && <span className="ck-rail-version">v{appConfig.crudkit_version}</span>}
          </Link>
          {/* One item per workspace; Home is the default one, its menu every shared view. */}
          <div className="ck-rail-group">
            <RailItem href="/" icon="home" label="Home" active={!activeWorkspace} onClick={() => selectWorkspace(null)} />
            {visibleWorkspaces.map((workspace) => (
              <RailItem
                key={workspace.id}
                icon={hasIcon(workspace.icon) ? workspace.icon : null}
                label={workspace.name || 'Untitled'}
                active={activeWorkspace?.id === workspace.id}
                onClick={() => openWorkspace(workspace)}
              />
            ))}
          </div>
          <div className="ck-rail-group ck-rail-foot">
            <RailItem icon="search" label="Search" onClick={() => setPaletteOpen(true)} />
            <RailItem
              href="/inbox"
              icon="inbox"
              label="Inbox"
              badge={pendingProposals.data?.count}
              active={pathname === '/inbox'}
              onClick={handleNavClick}
            />
          </div>
        </nav>

        <nav aria-label="Sidebar" className="ck-navpanel">
          <div className="ck-navpanel-header">
            <span className="ck-navpanel-title">{activeWorkspace ? activeWorkspace.name : appConfig.org_name}</span>
            {!activeWorkspace && (
              <Link
                to="/WSP/create"
                className="ck-navpanel-btn"
                aria-label="New workspace"
                title="New workspace"
                onClick={handleNavClick}
              >
                <Icon name="plus" size={14} color="currentColor" />
              </Link>
            )}
            {activeWorkspace && (
              <Link
                to={`/${activeWorkspace.id}/edit`}
                className="ck-navpanel-btn"
                aria-label="Edit workspace"
                title="Edit workspace"
                onClick={handleNavClick}
              >
                <Icon name="edit-3" size={13} color="currentColor" />
              </Link>
            )}
            <button type="button" className="ck-navpanel-btn" onClick={hideNav} aria-label="Collapse sidebar" title="Collapse sidebar">
              <Icon name="panel-left" size={14} color="currentColor" />
            </button>
          </div>

          <button type="button" onClick={() => setPaletteOpen(true)} className="ck-navpanel-search">
            <Icon name="search" size={13} color="currentColor" />
            <span className="flex-1 truncate">Find anything…</span>
            <Kbd>⌘K</Kbd>
          </button>

          <div className="ck-navpanel-scroll">
            {/* The workspace's menu: its views, or for Home every shared view */}
            <NavSection title="Views">
              {(activeWorkspace ? workspaceTabs : workspaceViews).map((view) => {
                const href = viewHref(view);
                const active = pathname === href
                  || (view.default && pathname.startsWith(`/${view.model}`) && !pathname.includes('/VIW/'));
                return (
                  <NavItem
                    key={view.id}
                    href={href}
                    icon={viewIcon(view)}
                    label={view.name || 'Untitled'}
                    count={view.show_badge_in_menu ? badgeCounts[view.id] : null}
                    active={active}
                    onClick={handleNavClick}
                  />
                );
              })}
              <NavItem
                href="/all-objects"
                icon="layers"
                label="All objects"
                active={pathname === '/all-objects'}
                onClick={handleNavClick}
              />
            </NavSection>

            {/* My Views — private views the current user created */}
            <NavSection
              title="My views"
              action={
                <Link
                  to="/VIW/create"
                  onClick={handleNavClick}
                  aria-label="New view"
                  className="inline-flex items-center justify-center w-4 h-4 rounded text-fg-3 hover:text-fg-1 hover:bg-bg-3"
                >
                  <Icon name="plus" size={12} color="currentColor" />
                </Link>
              }
            >
              {myViews.length === 0 && (
                <p className="ck-navpanel-empty">Views you save for yourself show up here.</p>
              )}
              {myViews.map((view) => {
                const href = viewHref(view);
                return (
                  <NavItem
                    key={view.id}
                    href={href}
                    icon={viewIcon(view)}
                    label={view.name || 'Untitled'}
                    count={view.show_badge_in_menu ? badgeCounts[view.id] : null}
                    active={pathname === href}
                    onClick={handleNavClick}
                  />
                );
              })}
            </NavSection>

          </div>
        </nav>

        <div className="ck-shell-footer">
          <Link to="/profile" className="ck-shell-footer-me" onClick={handleNavClick}>
            <Avatar
              name={userName}
              size={28}
              status="online"
              src={user?.object_images?.[0] || user?.image || user?.avatar || null}
            />
            <span className="ck-shell-footer-who">
              <span className="block text-md font-semibold text-fg-1 truncate">{userName}</span>
              <span className="block text-xs text-fg-3 truncate">
                {user?.email || (user?.username ? `@${user.username}` : 'Member')}
              </span>
            </span>
          </Link>
          <ThemeToggle />
        </div>

        <div className="ck-main">
          <Topbar navOverlay={navOverlay} navCollapsed={navCollapsed && !navOverlay} onOpenNav={showNav} />
          <div className={"ck-main-scroll" + (isPending ? " opacity-25 transition-opacity" : "")}>
            <main id="main" className="ck-content">
              <Outlet />
            </main>
          </div>
        </div>

        {assistantValue.open && (
          <div className="ck-assistant">
            <AssistantSidebar onClose={() => setAssistantOpen(false)} />
          </div>
        )}

        {scrim && <div className="ck-scrim" onClick={closeOverlays} aria-hidden="true" />}

        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
        <JobTray />
      </div>
      </TopbarSlotsProvider>
      </ScreenProvider>
      </PageSearchContext.Provider>
      </AssistantContext.Provider>
    </CommandPaletteContext.Provider>
  );
}
