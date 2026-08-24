import * as React from "react";
import ReadOnlyField from "./ReadOnlyField.jsx";
import {appConfig} from "../utils/appConfig";
import {url} from "../utils/urls";
import {useEffect, useState} from "react";
import CrudKitAPIClient, {performAction} from "../data/api";
import useWebSocket, {ReadyState} from "react-use-websocket";
import moment from "moment-timezone";
import {Link, useNavigate} from "react-router-dom";
import {useHotkeys} from "react-hotkeys-hook";
import {toast} from "react-toastify";
import {useMutation} from "@tanstack/react-query";
import {useAuth} from "../context/AuthContext";
import {Avatar, Icon, IconButton} from "./ui";
import SafeMarkdown from "../shared/SafeMarkdown";
import MarkdownComposer from "../shared/MarkdownComposer";

function MessageTranslation({message, preferredLanguage}) {
  if (!message.detected_language || !message.translation) return null;
  if (message.detected_language === preferredLanguage) return null;
  return (
    <div className="mt-1.5 pt-1.5 border-t border-border-2 text-xs text-fg-3 italic">
      {message.translation}
    </div>
  );
}

function Messages({parentId}) {
  const {user} = useAuth();
  const client = new CrudKitAPIClient();
  const preferredLanguage = user?.preferred_language || "en";

  const socketURL = client.baseUrl + "/ws/agent/" + parentId + "/";
  const {sendMessage, lastJsonMessage, readyState} = useWebSocket(socketURL, {
    shouldReconnect: () => true,
  });
  const bodyRef = React.useRef(null);
  const prevScrollHeightRef = React.useRef(null);
  const didInitialScrollRef = React.useRef(false);
  const wasNearBottomRef = React.useRef(true);
  const [typingFrom, setTypingFrom] = useState(null);
  const typingTimerRef = React.useRef(null);
  useEffect(() => {
    if (lastJsonMessage !== null) {
      const el = bodyRef.current;
      wasNearBottomRef.current = el
        ? el.scrollHeight - el.scrollTop - el.clientHeight < 80
        : true;
      // Check if there's an error message (conversation closed)
      if (lastJsonMessage.error && lastJsonMessage.error === "Conversation is closed") {
        console.warn("Conversation is closed:", lastJsonMessage.message);
        // Display the system message about the conversation being closed
        if (lastJsonMessage.message && lastJsonMessage.message.system_message) {
          setMessages((prev) => [...prev, {
            id: "system-message",
            text: lastJsonMessage.message.text,
            created_at: lastJsonMessage.message.created_at,
            system_message: true
          }]);
        }
      } else if (lastJsonMessage.type === "typing") {
        const who = lastJsonMessage.user || { label: "Customer" };
        setTypingFrom(who);
        if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
        typingTimerRef.current = setTimeout(() => setTypingFrom(null), 3000);
      } else if (lastJsonMessage.type === "feedback_updated") {
        const {message_id, feedback_score, feedback_reason, feedback_comment} = lastJsonMessage;
        setMessages((prev) => prev.map((m) =>
          m.id === message_id
            ? {...m, feedback_score, feedback_reason: feedback_reason || "", feedback_comment: feedback_comment || ""}
            : m
        ));
      } else if (lastJsonMessage.type === "feedback_prompt") {
        // Visitor ended the chat. Refresh survey responses so the summary shows up.
        refetchSurveyResponses();
      } else if (lastJsonMessage.message) {
        setTypingFrom(null);
        setMessages((prev) => prev.concat(lastJsonMessage.message));
      }
    }
  }, [lastJsonMessage]);

  useEffect(() => () => {
    if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
  }, []);
  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];

  const [messages, setMessages] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [surveyResponses, setSurveyResponses] = useState([]);

  const refetchSurveyResponses = async () => {
    const result = await client.list("SUR", {conversation: parentId});
    const rows = result?.isPaginated ? (result.results || []) : (result || []);
    setSurveyResponses(rows);
  };

  const fetchMessages = async (page = 1) => {
    if (page === 1) {
      setIsLoading(true);
    }
    const result = await client.list("MSG", {
      conversation: parentId,
      _order_by: "-created_at",
      page: page
    });
    // Check if the response is paginated
    if (result && result.isPaginated) {
      // Reverse to show oldest first in the UI (we fetched newest first to get latest 50)
      const newMessages = (result.results || []).reverse();

      if (page === 1) {
        setMessages(newMessages);
      } else {
        // Prepend older messages when loading more
        setMessages((prev) => [...newMessages, ...prev]);
      }

      setHasMore(!!result.next);
      setCurrentPage(page);
    } else {
      setMessages((result || []).reverse());
      setHasMore(false);
    }
    if (page === 1) {
      setIsLoading(false);
    }
  }

  const loadMoreMessages = async () => {
    setIsLoadingMore(true);
    const el = bodyRef.current;
    prevScrollHeightRef.current = el ? el.scrollHeight : 0;
    await fetchMessages(currentPage + 1);
    setIsLoadingMore(false);
  }

  useEffect(() => {
    didInitialScrollRef.current = false;
    prevScrollHeightRef.current = null;
    wasNearBottomRef.current = true;
    (async () => {
      // Reset state when switching conversations
      setMessages([]);
      setCurrentPage(1);
      setHasMore(false);
      setSurveyResponses([]);
      await Promise.all([fetchMessages(1), refetchSurveyResponses()]);
    })();
  }, [parentId]);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el || messages.length === 0) return;
    if (!didInitialScrollRef.current) {
      el.scrollTop = el.scrollHeight;
      didInitialScrollRef.current = true;
      return;
    }
    if (prevScrollHeightRef.current !== null) {
      el.scrollTop = el.scrollHeight - prevScrollHeightRef.current;
      prevScrollHeightRef.current = null;
      return;
    }
    if (wasNearBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, typingFrom]);

  const sender = (message) => message.user?.id ? message.user : message.person?.id ? message.person : {
    "label": "Anonymous"
  };

  // Detect touch/mobile-web. On coarse pointers Enter inserts a newline (the
  // soft keyboard's Return) and the user sends via the explicit Send button.
  const isTouch = typeof window !== "undefined"
    && window.matchMedia
    && window.matchMedia("(pointer: coarse)").matches;

  const [draft, setDraft] = useState("");
  const lastTypingSentRef = React.useRef(0);

  const sendCurrent = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    sendMessage(JSON.stringify({ text }));
  };

  const handleDraftChange = (next) => {
    setDraft(next);
    if (next && Date.now() - lastTypingSentRef.current > 2000) {
      lastTypingSentRef.current = Date.now();
      sendMessage(JSON.stringify({ type: "typing" }));
    }
  };

  const conversationClosed = messages.some(m => m.system_message);

  return (
    <>
      <div className="ck-ct-body" ref={bodyRef}>
        {surveyResponses.length > 0 && (
          <div className="mx-2 mt-2 mb-1 rounded-md border border-border-2 bg-bg-2 px-3 py-2 text-xs text-fg-2">
            <span className="font-medium text-fg-1">End-of-chat survey:</span>
            {surveyResponses.map((r) => {
              if (r.type === "FTR") {
                return (
                  <span key={r.id} className="ml-2">
                    Resolved: <strong>{r.score === 1 ? "Yes" : "No"}</strong>
                  </span>
                );
              }
              if (r.type === "CSAT") {
                return (
                  <span key={r.id} className="ml-2">
                    CSAT: <strong>{r.score}/5</strong>
                  </span>
                );
              }
              return null;
            })}
            {surveyResponses.find((r) => r.comments) && (
              <div className="mt-1 italic text-fg-3">
                &quot;{surveyResponses.find((r) => r.comments).comments}&quot;
              </div>
            )}
          </div>
        )}
        {hasMore && (
          <div className="flex justify-center my-2">
            <button
              type="button"
              onClick={loadMoreMessages}
              disabled={isLoadingMore}
              className="ck-btn ck-btn-ghost ck-btn-sm"
            >
              {isLoadingMore ? "Loading…" : "Load older messages"}
            </button>
          </div>
        )}
        {messages.length === 0 && !isLoading && (
          <div className="flex items-center justify-center h-32">
            <p className="text-sm text-fg-3">No messages</p>
          </div>
        )}
        {messages.length === 0 && isLoading && (
          <div className="flex items-center justify-center h-32">
            <p className="text-sm text-fg-3 animate-pulse">Loading…</p>
          </div>
        )}
        {messages.map((message) => {
          if (message.system_message) {
            return (
              <div key={message.id} className="ck-bubble-system">
                {message.text}
              </div>
            );
          }
          const isOut = !!message.user?.id;
          const senderInfo = sender(message);
          const senderName = senderInfo.label || "Unknown";
          const senderImg =
            senderInfo.object_images?.[0]
            || (message.object_images && message.object_images[0])
            || null;
          return (
            <div key={message.id} className={`ck-bubble-row ${isOut ? 'is-out' : ''}`}>
              <Avatar name={senderName} size={24} src={senderImg} />
              <div className="ck-bubble-stack">
                <div className={`ck-bubble ${isOut ? 'ck-bubble-out' : 'ck-bubble-in'}`}>
                  <SafeMarkdown source={message.text} />
                  {!isOut && (
                    <MessageTranslation message={message} preferredLanguage={preferredLanguage} />
                  )}
                </div>
                <div className="ck-bubble-meta">
                  {senderName} · {moment(message.created_at).fromNow()}
                  {message.feedback_score === 1 && (
                    <span
                      className="ml-1 text-emerald-600"
                      title={message.feedback_comment || message.feedback_reason || "Marked helpful"}
                    >
                      · 👍
                    </span>
                  )}
                  {message.feedback_score === -1 && (
                    <span
                      className="ml-1 text-red-600"
                      title={message.feedback_comment || message.feedback_reason || "Marked unhelpful"}
                    >
                      · 👎 {message.feedback_reason ? `(${message.feedback_reason})` : ""}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {typingFrom && (
          <div className="ck-bubble-row">
            <Avatar name={typingFrom.label || "Typing"} size={24} />
            <div className="ck-bubble-stack">
              <div className="ck-bubble ck-bubble-in ck-bubble-typing" aria-label={`${typingFrom.label || "Someone"} is typing`}>
                <span className="ck-typing-dot" />
                <span className="ck-typing-dot" />
                <span className="ck-typing-dot" />
              </div>
              <div className="ck-bubble-meta">{typingFrom.label || "Customer"} is typing…</div>
            </div>
          </div>
        )}
      </div>
      <form className="ck-ct-composer" onSubmit={(e) => { e.preventDefault(); sendCurrent(); }}>
        <MarkdownComposer
          value={draft}
          onChange={handleDraftChange}
          onSubmit={sendCurrent}
          placeholder={conversationClosed ? "This conversation is closed" : "Reply…"}
          rows={3}
          disabled={conversationClosed}
          submitOnEnter={!isTouch}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-fg-3">
            {conversationClosed
              ? "Closed. Start a new conversation to reply."
              : isTouch
                ? "Tap Send to reply"
                : "↵ to send · ⇧↵ for newline"}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-2xs text-fg-3 font-mono">{connectionStatus}</span>
            {isTouch && (
              <button
                type="submit"
                disabled={conversationClosed}
                className="ck-btn ck-btn-primary ck-btn-sm"
              >
                <Icon name="send" size={12} color="currentColor" />
                Send
              </button>
            )}
          </div>
        </div>
      </form>
    </>
  );
}


const LIST_TABS = [
  { id: "open", label: "Open" },
  { id: "mine", label: "Mine" },
  { id: "closed", label: "Closed" },
];

function tabFilter(tab, items, userId) {
  if (!items) return [];
  switch (tab) {
    case "mine":
      return items.filter(o => {
        const owner = typeof o.assignee === "object" ? o.assignee?.id : o.assignee;
        return owner != null && userId != null && String(owner) === String(userId);
      });
    case "closed":
      return items.filter(o => {
        const status = typeof o.status === "object" ? o.status?.label : o.status;
        return typeof status === "string" && /(closed|resolved|done)/i.test(status);
      });
    case "open":
    default:
      return items.filter(o => {
        const status = typeof o.status === "object" ? o.status?.label : o.status;
        return !(typeof status === "string" && /(closed|resolved|done)/i.test(status));
      });
  }
}

export default function ConversationList({objectList, view, model, metadata, refetch}) {
  const {user} = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("open");
  // Only set selectedRows if objectList has items
  const [selectedRows, setSelectedRows] = useState(objectList && objectList.length > 0 ? [objectList[0].id]:[]);
  // Force Messages component refresh when this changes
  const [refreshKey, setRefreshKey] = useState(0);

  const visibleList = React.useMemo(
    () => tabFilter(tab, objectList || [], user?.id),
    [tab, objectList, user?.id]
  );
  const tabCounts = React.useMemo(() => ({
    open: tabFilter("open", objectList || [], user?.id).length,
    mine: tabFilter("mine", objectList || [], user?.id).length,
    closed: tabFilter("closed", objectList || [], user?.id).length,
  }), [objectList, user?.id]);
  
  
  // Update selectedRows when objectList changes
  useEffect(() => {
    // If the currently selected conversation is no longer in the list, select the first one
    if (selectedRows.length > 0 && objectList && objectList.length > 0) {
      const selectedStillExists = objectList.some(obj => obj.id === selectedRows[0]);
      if (!selectedStillExists) {
        // Select the first conversation in the new list
        setSelectedRows([objectList[0].id]);
      }
    } else if (objectList && objectList.length > 0 && selectedRows.length === 0) {
      // If nothing is selected but there are conversations, select the first one
      setSelectedRows([objectList[0].id]);
    } else if (!objectList || objectList.length === 0) {
      // If there are no conversations, clear the selection
      setSelectedRows([]);
    }
  }, [objectList]); // eslint-disable-line react-hooks/exhaustive-deps
  
  // Function to refresh the currently selected conversation
  const refreshSelectedConversation = async () => {
    // Refresh the entire list from the parent
    if (refetch) {
      await refetch();
    }
    // Force Messages component to refresh
    setRefreshKey(prevKey => prevKey + 1);
  };
  
  // Action mutation
  const actionMutation = useMutation({
    mutationFn: ({modelType, id, action}) => performAction(modelType, id, action),
    onSuccess: async (response) => {
      console.log("Action success response:", response);
      
      // Handle success - show messages and handle redirects
      if (response.messages && response.messages.length > 0) {
        // Show each message as a toast
        response.messages.forEach(message => {
          toast.info(message);
        });
      } else {
        // Generic success message
        toast.success("Action completed successfully");
      }
      
      // Handle redirects
      if (response.redirect) {
        console.log("Redirecting to:", response.redirect);
      }
      
      // Refresh the conversation to show updated data
      await refreshSelectedConversation();
      
      // Force Messages component to refresh
      setRefreshKey(prevKey => prevKey + 1);
    },
    onError: (error) => {
      toast.error("Action failed: " + (error.message || "Unknown error"));
      console.error("Action error:", error);
    }
  });
  
  // Get the selected object if any
  const selectedObject = (selectedRows && selectedRows.length > 0 && objectList && objectList.length > 0)
    ? objectList.find(obj => obj.id === selectedRows[0]) || null
    : null;

  const editHref = selectedRows[0]
    ? url(selectedRows[0], 'edit', {next: window.location.pathname + window.location.search})
    : null;

  useHotkeys('e', () => {
    if (editHref) navigate(editHref);
  }, {enabled: !!editHref}, [editHref]);

  const runAction = (action) => {
    if (!window.confirm(`Are you sure you want to ${action.verbose_name.toLowerCase()}?`)) return;
    actionMutation.mutate({modelType: model, id: selectedRows[0], action: action.action});
  };

  const titleField = view.fields[0];
  const subtitleField = view.fields[1];

  // Helper: build a plain-text label from any field value (FK / Date / etc.)
  // for use in places where we can't render a full ReadOnlyField (e.g. the
  // Avatar `name` prop).
  const plain = (value) => {
    if (value == null) return "";
    if (typeof value === "object") {
      if (value.label) return String(value.label);
      if (value.amount !== undefined) return String(value.amount);
      return JSON.stringify(value);
    }
    return String(value);
  };

  const headerLabel = selectedObject?.label || selectedObject?.id || "No conversation selected";

  return (
    <div className="ck-conv ck-fullbleed">
      {/* Left pane: conversation list */}
      <aside className="ck-conv-list">
        <div className="ck-conv-list-head">
          <div className="ck-clh-tabs" role="tablist">
            {LIST_TABS.map(t => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={`ck-clt ${tab === t.id ? 'is-on' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
                {tabCounts[t.id] > 0 && <span className="ck-clt-c">{tabCounts[t.id]}</span>}
              </button>
            ))}
          </div>
          <IconButton icon="filter" size="sm" aria-label="Filter" />
        </div>
        <div className="ck-conv-rows">
          {visibleList && visibleList.length > 0 ? (
            visibleList.map((object) => {
              const selected = selectedRows[0] === object.id;
              const avatarName = plain(titleField ? object[titleField] : object.label) || object.id;
              return (
                <div
                  key={object.id}
                  className={`ck-conv-row ${selected ? 'is-on' : ''}`}
                  onClick={() => setSelectedRows([object.id])}
                >
                  <Avatar name={avatarName} size={32} src={object.object_images?.[0]} />
                  <div className="ck-cr-body">
                    <div className="ck-cr-head">
                      <span className="ck-cr-who ck-fg-1">
                        {titleField ? (
                          <ReadOnlyField
                            value={object[titleField]}
                            metadata={metadata.fields[titleField]}
                            link={false}
                          />
                        ) : (
                          object.label || object.id
                        )}
                      </span>
                      {object.updated_at && (
                        <span className="ck-cr-when">
                          {moment(object.updated_at).fromNow(true)}
                        </span>
                      )}
                    </div>
                    {subtitleField && metadata.fields[subtitleField] && (
                      <div className="ck-cr-company ck-fg-3">
                        <ReadOnlyField
                          value={object[subtitleField]}
                          metadata={metadata.fields[subtitleField]}
                          link={false}
                        />
                      </div>
                    )}
                    {view.fields[2] && (
                      <div className="ck-cr-preview ck-fg-2">
                        <ReadOnlyField
                          value={object[view.fields[2]]}
                          metadata={metadata.fields[view.fields[2]]}
                          link={false}
                        />
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="flex items-center justify-center h-32 px-4">
              <p className="text-sm text-fg-3">No conversations available</p>
            </div>
          )}
        </div>
      </aside>

      {/* Center pane: message thread */}
      <section className="ck-conv-thread">
        <div className="ck-ct-head">
          <div className="flex items-center gap-2.5 min-w-0 flex-1">
            <Avatar name={String(headerLabel)} size={28} status="online" />
            <div className="flex flex-col min-w-0 flex-1">
              <Link to={selectedRows[0] ? url(selectedRows[0]) : '#'} className="ck-cth-who hover:text-primary-300">
                {String(headerLabel)}
              </Link>
              {selectedObject && subtitleField && metadata.fields[subtitleField] && (
                <span className="ck-cth-co ck-fg-3">
                  <ReadOnlyField
                    value={selectedObject[subtitleField]}
                    metadata={metadata.fields[subtitleField]}
                    link={false}
                  />
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {selectedObject && metadata.actions && metadata.actions.map((action) => (
              <button
                key={action.action}
                type="button"
                onClick={() => runAction(action)}
                className="ck-btn ck-btn-secondary ck-btn-sm"
              >
                <Icon name="zap" size={12} color="currentColor" />
                {action.verbose_name}
              </button>
            ))}
            {selectedObject && editHref && (
              <Link to={editHref} className="ck-btn ck-btn-primary ck-btn-sm">
                <Icon name="edit-3" size={12} color="currentColor" />
                Edit
                <span className="ck-kbd">E</span>
              </Link>
            )}
          </div>
        </div>

        {selectedRows.length > 0 ? (
          <Messages
            key={`${selectedRows[0] || ''}-${refreshKey}`}
            parentId={selectedRows[0] || null}
          />
        ) : (
          <div className="flex items-center justify-center flex-1 h-full">
            <p className="text-sm text-fg-3">Select a conversation</p>
          </div>
        )}
      </section>

      {/* Right pane: object detail */}
      <aside className="ck-conv-side">
        {/* Customer card */}
        {selectedObject && (
          <div>
            <div className="ck-cs-head">Customer</div>
            <Link to={url(selectedRows[0])} className="ck-cs-customer">
              <Avatar
                name={String(headerLabel)}
                size={36}
                src={selectedObject.object_images?.[0]}
              />
              <div>
                <div className="ck-cs-who">{selectedObject.label || selectedObject.id}</div>
                {subtitleField && metadata.fields[subtitleField] && (
                  <div className="ck-cs-meta">
                    <ReadOnlyField
                      value={selectedObject[subtitleField]}
                      metadata={metadata.fields[subtitleField]}
                      link={false}
                    />
                  </div>
                )}
              </div>
            </Link>
          </div>
        )}

        {/* Linked deal — picks up the first FK whose name matches the
            configured conversation_link_pattern */}
        {selectedObject && (() => {
          const dealField = Object.keys(selectedObject).find(k =>
            new RegExp(appConfig.conversation_link_pattern, "i").test(k)
            && selectedObject[k]
            && typeof selectedObject[k] === "object"
            && selectedObject[k].label
          );
          if (!dealField) return null;
          const deal = selectedObject[dealField];
          return (
            <div>
              <div className="ck-cs-head">Linked {dealField.replace(/_/g, ' ')}</div>
              <Link to={url(deal.id)} className="ck-cs-deal">
                <div className="ck-cs-deal-name">{deal.label}</div>
                <div className="ck-cs-deal-meta">{deal.id}</div>
              </Link>
            </div>
          );
        })()}

        {/* Assignee */}
        {selectedObject?.assignee && (
          <div>
            <div className="ck-cs-head">Assignee</div>
            <span className="ck-cs-assignee">
              <Avatar
                name={selectedObject.assignee.label || String(selectedObject.assignee)}
                size={20}
                src={selectedObject.assignee.object_images?.[0]}
              />
              {selectedObject.assignee.label || selectedObject.assignee}
            </span>
          </div>
        )}

        {/* Tags */}
        {Array.isArray(selectedObject?.tags) && selectedObject.tags.length > 0 && (
          <div>
            <div className="ck-cs-head">Tags</div>
            <div className="ck-cs-tags">
              {selectedObject.tags.map((t, i) => (
                <span key={i} className="ck-cs-tag">
                  {typeof t === "object" ? (t.label || t.name || t.id) : t}
                </span>
              ))}
              <button type="button" className="ck-cs-add">
                <Icon name="plus" size={10} color="currentColor" /> Add
              </button>
            </div>
          </div>
        )}

        {/* Properties (any other view-defined fields not surfaced above) */}
        {selectedObject && view.fields.length > 0 && (
          <div>
            <div className="ck-cs-head">Properties</div>
            <div>
              {view.fields.map((field) => (
                <div className="ck-cs-row" key={field}>
                  <dt className="ck-cs-label truncate">
                    {metadata.fields[field]?.verbose_name || field}
                  </dt>
                  <dd className="ck-cs-value truncate">
                    <ReadOnlyField
                      field={field}
                      value={selectedObject[field]}
                      metadata={metadata.fields[field]}
                    />
                  </dd>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}