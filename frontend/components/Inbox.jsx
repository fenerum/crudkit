import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import moment from "moment-timezone";
import CrudKitAPIClient from "../data/api";
import { Avatar, Icon, useTopbarSlots } from "./ui";
import { detail as detailRegex } from "../utils/urls";

const VALID_TABS = new Set(["all", "unread", "mentions", "assigned"]);

const TABS = [
  { id: "all", label: "All", icon: "inbox" },
  { id: "unread", label: "Unread", icon: "circle" },
  { id: "mentions", label: "Mentions", icon: "at-sign" },
  { id: "assigned", label: "Assigned", icon: "user" },
];

function deriveIcon(item) {
  const ct = item.related_content_type;
  if (!ct) return "message-square";
  const model = String(ct.model || "").toLowerCase();
  if (model.includes("email")) return "mail";
  if (model.includes("call")) return "phone";
  if (model.includes("aisuggestion")) return "zap";
  if (model.includes("note")) return "message-square";
  return "activity";
}

function previewFromBody(body) {
  if (!body) return "";
  const stripped = String(body).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return stripped.length > 220 ? stripped.slice(0, 220) + "…" : stripped;
}

export default function Inbox() {
  const client = useMemo(() => new CrudKitAPIClient(), []);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab = VALID_TABS.has(tabParam) ? tabParam : "all";

  const setTab = useCallback((next) => {
    if (next === tab) return;
    const search = new URLSearchParams();
    if (next !== "all") search.set("tab", next);
    const qs = search.toString();
    navigate(qs ? `${pathname}?${qs}` : pathname, { replace: true });
  }, [pathname, navigate, tab]);

  const { data, isPending, isError } = useQuery({
    queryKey: ["list", "FEI", { tab }],
    queryFn: async () => {
      if (tab !== "all") return [];
      return client.list("FEI", { ordering: "-created_at", page_size: 50 });
    },
  });

  const items = data?.isPaginated ? data.results : (data || []);

  const counts = {
    all: items.length || null,
    unread: 0,
    mentions: 0,
    assigned: 0,
  };

  useTopbarSlots(() => ({
    title: { label: "Inbox" },
    middle: (
      <div className="flex items-center gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={
              "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-colors duration-fast " +
              (tab === t.id
                ? "bg-bg-3 text-fg-1"
                : "text-fg-2 hover:bg-bg-2 hover:text-fg-1")
            }
          >
            <Icon name={t.icon} size={12} color="currentColor" />
            <span>{t.label}</span>
            {counts[t.id] != null && (
              <span className="text-2xs text-fg-3 font-mono">{counts[t.id]}</span>
            )}
          </button>
        ))}
      </div>
    ),
  }), [tab, counts.all]);

  const onOpen = (item) => {
    const raw = item.parent_object_id;
    if (raw) {
      const asString = String(raw).toUpperCase();
      if (detailRegex.test(asString)) {
        navigate(`/${asString}`);
        return;
      }
      const prefix = item.parent_content_type?.model
        ? item.parent_content_type.model.slice(0, 3).toUpperCase()
        : null;
      if (prefix && /^\d+$/.test(String(raw))) {
        navigate(`/${prefix}${raw}`);
        return;
      }
    }
    if (item.id) navigate(`/${item.id}`);
  };

  return (
    <div className="flex flex-col h-full">
      {isPending ? (
        <div className="px-6 py-12 text-center text-fg-3 text-sm">Loading…</div>
      ) : isError ? (
        <div className="px-6 py-12 text-center text-danger text-sm">
          Couldn&apos;t load inbox — try refreshing the page.
        </div>
      ) : items.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <div className="text-fg-1 text-base font-medium">
            {tab === "all" ? "Inbox zero" : "Nothing here yet"}
          </div>
          <div className="text-fg-3 text-sm mt-1">
            {tab === "all" && "When new activity arrives, you'll see it here."}
            {tab === "unread" && "You're caught up on unread items."}
            {tab === "mentions" && "Nobody has mentioned you yet."}
            {tab === "assigned" && "Nothing is assigned to you right now."}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-border-1 bg-bg-1 overflow-hidden">
          {items.map((item) => {
            const when = item.created_at ? moment(item.created_at) : null;
            const isUnread = when && moment().diff(when, "hours") < 24;
            const actor = item.created_by;
            const actorName = actor?.label || null;
            const actorImage = actor?.object_images?.[0] || actor?.image || null;
            return (
              <div
                key={item.id}
                className={"ck-inbox-row " + (isUnread ? "is-unread" : "")}
                onClick={() => onOpen(item)}
              >
                {actorName ? (
                  <Avatar name={actorName} src={actorImage} size={28} />
                ) : (
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-bg-3 border border-border-1 inline-flex items-center justify-center text-fg-2">
                    <Icon name={deriveIcon(item)} size={14} color="currentColor" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-fg-1 font-semibold truncate">
                      {item.created_by?.label || "System"}
                    </span>
                    {item.parent_content_type?.model && (
                      <span className="text-fg-2 truncate">
                        — {item.parent_content_type.model}
                      </span>
                    )}
                    <span className="ml-auto text-2xs text-fg-3 font-mono flex-shrink-0">
                      {when ? when.fromNow(true) : ""}
                    </span>
                  </div>
                  <div className="text-sm text-fg-2 truncate mt-0.5">
                    {previewFromBody(item.body) || (item.related_content_type
                      ? `${item.related_content_type.model} · ${item.id}`
                      : item.id)}
                  </div>
                </div>
                {isUnread && (
                  <span className="w-1.5 h-1.5 rounded-full bg-primary-400 mt-2.5 flex-shrink-0" />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
