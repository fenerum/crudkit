import * as React from "react";
import {useEffect, useState, useMemo, useCallback, useRef} from "react";
import CrudKitAPIClient, {fetchObjects} from "@/data/api";
import {useQuery} from "@tanstack/react-query";
import {Link, Outlet, useLocation, useNavigate} from "react-router-dom";
import {useAuth} from "../context/AuthContext";
import defaultLogoUrl from "../images/logo.svg";
import faviconUrl from "../images/favicon.svg";
import {appConfig} from "../utils/appConfig";
import TimeTracker from "../components/TimeTracker";
import Breadcrumbs from "../components/Breadcrumbs";
import CommandPalette from "../components/CommandPalette";
import {useDocumentTitle} from "../hooks/useDocumentTitle";
import {useHotkeys} from "react-hotkeys-hook";
import {Avatar, Icon, Kbd, Dot, TopbarSlotsProvider, useTopbarSlotsValue, ThemeProvider, ThemeToggle} from "../components/ui";
import {CommandPaletteContext} from "../components/ui/CommandPaletteContext";
import {PageSearchContext} from "../components/ui/PageSearchContext";

const NavItem = React.memo(function NavItem({href, icon, label, count, color, active, onClick}) {
  const cls =
    "flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm " +
    (active
      ? "bg-bg-3 text-fg-1"
      : "text-fg-2 hover:bg-bg-2 hover:text-fg-1");
  const inner = (
    <>
      {color ? (
        <Dot color={color} size={8} />
      ) : icon ? (
        <Icon name={icon} size={14} color="currentColor" />
      ) : null}
      <span className="flex-1 truncate">{label}</span>
      {count != null && count > 0 && (
        <span className="text-2xs text-fg-3 font-mono">{count}</span>
      )}
    </>
  );
  if (href) {
    return (
      <Link to={href} className={cls} onClick={onClick}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" className={cls + " w-full text-left"} onClick={onClick}>
      {inner}
    </button>
  );
});

function NavSection({title, action, children}) {
  return (
    <div className="flex flex-col mb-1.5">
      {title && (
        <div className="flex items-center justify-between px-2 pt-2.5 pb-1 eyebrow">
          <span>{title}</span>
          {action}
        </div>
      )}
      <div className="flex flex-col gap-px">{children}</div>
    </div>
  );
}

function Topbar({ menuActive, setMenuActive, handleNavClick }) {
  const slots = useTopbarSlotsValue();
  return (
    <header className="ck-topbar sticky top-0 z-40 flex items-center gap-3 px-3.5">
      <button
        type="button"
        className="ck-icon-btn ck-icon-btn-sm lg:hidden"
        onClick={() => setMenuActive(!menuActive)}
        aria-label={menuActive ? 'Close sidebar' : 'Open sidebar'}
      >
        <Icon name="panel-left" size={14} color="currentColor" />
      </button>

      {/* Left cluster: home + crumbs + optional title */}
      <nav className="flex items-center gap-1.5 min-w-0 flex-shrink-0" aria-label="Breadcrumb">
        <Link
          to="/"
          className="text-fg-3 hover:text-fg-1 transition-colors duration-fast inline-flex items-center"
          onClick={handleNavClick}
        >
          <Icon name="home" size={13} color="currentColor" />
        </Link>
        <ol role="list" className="flex items-center gap-1.5 min-w-0">
          <Breadcrumbs />
        </ol>
      </nav>

      {slots.title && slots.title.label && (
        <span className="text-sm font-normal text-fg-2 truncate min-w-0">
          {slots.title.label}
        </span>
      )}

      {/* Middle slot — view switcher, tab strip, etc. */}
      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-hidden">
        {slots.middle}
      </div>

      {/* Right cluster: viewSwitch | pageSearch | rightSlot | primary */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {slots.viewSwitch}

        {slots.pageSearch}

        {slots.right}

        <div className="hidden md:flex items-center">
          <TimeTracker />
        </div>

        {slots.primary}
      </div>
    </header>
  );
}

export default function BaseLayout() {
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const navigate = useNavigate();
  const {pathname} = useLocation();
  const {user, logout} = useAuth();
  useDocumentTitle();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [menuActive, setMenuActive] = useState(false);

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

  const {isPending, data: viewsData} = useQuery({
    queryKey: ['list', 'VIW', { show_in_menu: true }],
    queryFn: () => client.list("VIW", {"show_in_menu": true})
  });

  const rootViews = viewsData?.isPaginated ? viewsData.results : viewsData;

  const [badgeCounts, setBadgeCounts] = useState({});

  const viewsWithBadges = useMemo(() => {
    if (!rootViews) return [];
    return rootViews.filter(v => v.show_badge_in_menu);
  }, [rootViews]);

  useEffect(() => {
    const fetchBadgeCounts = async () => {
      if (!viewsWithBadges.length) return;
      const counts = {};
      await Promise.all(viewsWithBadges.map(async (view) => {
        try {
          const response = await fetchObjects(view.model, {
            page_size: 1,
            _fields: 'id',
            _view: view.id,
            ...view.filters
          });
          if (response && response.count !== undefined) {
            counts[view.id] = response.count;
          }
        } catch (err) {
          console.error(`Error fetching count for view ${view.id}:`, err);
        }
      }));
      setBadgeCounts(counts);
    };
    fetchBadgeCounts();
    const id = setInterval(fetchBadgeCounts, 60000);
    return () => clearInterval(id);
  }, [viewsWithBadges]);

  const handleNavClick = useCallback(() => {
    if (window.innerWidth < 1024) {
      setMenuActive(false);
    }
  }, []);

  // Group views by ownership: public views show under "Workspace"; private
  // views the current user created show under "My Views" with colored dots.
  const userId = user?.id;
  const isMineAndPrivate = useCallback((v) => {
    if (v.public) return false;
    const owner = typeof v.created_by === 'object' ? v.created_by?.id : v.created_by;
    return owner != null && userId != null && String(owner) === String(userId);
  }, [userId]);
  const myViews = useMemo(() => (rootViews || []).filter(isMineAndPrivate), [rootViews, isMineAndPrivate]);
  const workspaceViews = useMemo(() => (rootViews || []).filter(v => !isMineAndPrivate(v)), [rootViews, isMineAndPrivate]);

  const userName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : (user?.username || 'User');

  const sidebarClasses =
    "flex flex-col bg-bg-0 border-r border-border-1 overflow-y-auto " +
    "lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:flex-col " +
    (menuActive ? "fixed inset-0 z-50 flex" : "hidden lg:flex");

  return (
    <ThemeProvider>
    <CommandPaletteContext.Provider value={{open: paletteOpen, setOpen: setPaletteOpen}}>
      <PageSearchContext.Provider value={pageSearchValue}>
      <TopbarSlotsProvider>
      <div className="flex flex-col h-screen overflow-hidden bg-bg-1 text-fg-1">
        {/* Sidebar */}
        <div
          className={sidebarClasses}
          style={{width: 'var(--sidebar-w)', padding: '10px 8px'}}
        >
          {/* Workspace header */}
          <Link
            to="/"
            onClick={handleNavClick}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-bg-2"
          >
            <span className="flex items-center justify-center" style={{width: 24, height: 24, borderRadius: 6, overflow: 'hidden', flex: '0 0 24px', background: 'var(--primary-400)'}}>
              <img
                src={appConfig.logo_url || defaultLogoUrl}
                alt={appConfig.app_name}
                style={{width: 18, height: 18, objectFit: 'contain'}}
              />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-sm font-semibold text-fg-1 truncate">{appConfig.org_name}</span>
              <span className="block text-2xs text-fg-3">{userName}</span>
            </span>
            <Icon name="chevrons-up-down" size={14} color="var(--fg-3)" />
          </Link>

          {/* Search trigger */}
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2 px-2.5 py-1.5 mt-1 mb-2 rounded-md bg-bg-2 hover:bg-bg-3 border border-border-1 text-fg-3 text-xs"
          >
            <Icon name="search" size={13} color="var(--fg-3)" />
            <span className="flex-1 text-left">Search</span>
            <Kbd>⌘K</Kbd>
          </button>

          {/* Inbox + Home */}
          <NavSection>
            <NavItem
              href="/inbox"
              icon="inbox"
              label="Inbox"
              active={pathname === '/inbox'}
              onClick={handleNavClick}
            />
            <NavItem
              href="/"
              icon="home"
              label="Home"
              active={pathname === '/'}
              onClick={handleNavClick}
            />
          </NavSection>

          {/* Workspace */}
          {workspaceViews.length > 0 && (
            <NavSection title="Workspace">
              {workspaceViews.map((view) => {
                const href = view.default ? `/${view.model}` : `/${view.model}/VIW/${view.id}`;
                const active = pathname === href || pathname.startsWith(`/${view.model}`);
                return (
                  <NavItem
                    key={view.id}
                    href={href}
                    icon="layout-grid"
                    label={view.name || 'Untitled'}
                    count={view.show_badge_in_menu ? badgeCounts[view.id] : null}
                    active={active}
                    onClick={handleNavClick}
                  />
                );
              })}
              <NavItem
                href="/all-objects"
                icon="columns"
                label="All objects"
                active={pathname === '/all-objects'}
                onClick={handleNavClick}
              />
            </NavSection>
          )}

          {/* My Views — private views the current user created */}
          <NavSection
            title="My Views"
            action={
              <Link
                to="/VIW/create"
                onClick={handleNavClick}
                aria-label="New view"
                className="inline-flex items-center justify-center w-4 h-4 rounded text-fg-3 hover:text-fg-1 hover:bg-bg-2"
              >
                <Icon name="plus" size={12} color="currentColor" />
              </Link>
            }
          >
            {myViews.map((view, i) => {
              const href = view.default ? `/${view.model}` : `/${view.model}/VIW/${view.id}`;
              const palette = ['var(--stage-blue)', 'var(--stage-amber)', 'var(--stage-violet)', 'var(--stage-green)', 'var(--stage-rose)', 'var(--stage-slate)'];
              return (
                <NavItem
                  key={view.id}
                  href={href}
                  color={palette[i % palette.length]}
                  label={view.name || 'Untitled'}
                  count={view.show_badge_in_menu ? badgeCounts[view.id] : null}
                  active={pathname === href}
                  onClick={handleNavClick}
                />
              );
            })}
          </NavSection>

          {/* Footer */}
          <div className="mt-auto flex items-center gap-2.5 p-2 border-t border-border-1">
            <Avatar
              name={userName}
              size={24}
              status="online"
              src={user?.object_images?.[0] || user?.image || user?.avatar || null}
            />
            <Link
              to="/profile"
              className="flex-1 min-w-0"
              onClick={handleNavClick}
            >
              <span className="block text-sm font-medium text-fg-1 truncate">{userName}</span>
              <span className="block text-2xs text-fg-3 truncate">
                {user?.email || (user?.username ? `@${user.username}` : 'Member')}
              </span>
            </Link>
            <ThemeToggle />
          </div>
        </div>

        {/* Main content area — sidebar is `lg:fixed` so only reserve its
            240px gutter at lg+ viewports, otherwise the content takes the
            full width and the hamburger reveals the sidebar as an overlay. */}
        <div
          className="flex flex-col flex-1 overflow-hidden lg:pl-[var(--sidebar-w)]"
        >
          <Topbar
            menuActive={menuActive}
            setMenuActive={setMenuActive}
            handleNavClick={handleNavClick}
          />

          {/* Scrollable content area */}
          <div className={"flex-1 overflow-auto overflow-x-hidden " + (isPending ? "opacity-25 transition-opacity" : "")}>
            <main id="main">
              <div className="px-6 py-5">
                <div className="innerContent">
                  <Outlet />
                </div>
              </div>
            </main>
          </div>
        </div>

        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      </div>
      </TopbarSlotsProvider>
      </PageSearchContext.Provider>
    </CommandPaletteContext.Provider>
    </ThemeProvider>
  );
}
