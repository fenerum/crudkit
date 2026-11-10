import { useMemo, useState } from "react";
import moment from "moment-timezone";
import DOMPurify from "dompurify";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormProvider } from "react-hook-form";
import { toast } from "react-toastify";
import CrudKitAPIClient from "../data/api";
import { invalidateModel } from "../data/invalidate";
import { capitalize, url } from "../utils/urls";
import { formatApiError } from "../utils/apiErrors";
import { handleActionResult } from "../utils/actionResult";
import { useCreateForm, useMetadata } from "@/utils/formHooks";
import { useFeedEntry } from "../hooks/useFeedEntry";
import { Avatar, Icon } from "./ui";
import GenericDetailField from "./GenericDetailField.jsx";
import ReadOnlyField from "./ReadOnlyField";
import HtmlFrame from "./HtmlFrame";
import WYSIWYGEditorField from "./Fields/WYSIWYGEditorField";

const IMAGE_FILENAME = /\.(png|jpe?g|gif|webp|svg|bmp|avif)$/i;
const PREVIEW_MAX_HEIGHT = 250;
// Fields that get a full-width block of their own, rather than a label/value line.
const BLOCK_TYPES = new Set(["WYSIWYGEditorField", "EmailWYSIWYGEditorField", "TextField"]);

const isBlank = (value) => value === null || value === undefined || value === "";
const isBlock = (meta) => BLOCK_TYPES.has(meta.type);

function AttachmentRow({ name, href }) {
    const [previewStyle, setPreviewStyle] = useState(null);
    const isImage = IMAGE_FILENAME.test(name || "");

    // Fixed positioning so the preview isn't clipped by scrolling feed/tab containers.
    const showPreview = (event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setPreviewStyle(rect.top > PREVIEW_MAX_HEIGHT
            ? {left: rect.left, bottom: window.innerHeight - rect.top + 4}
            : {left: rect.left, top: rect.bottom + 4});
    };

    return (
        <li
            className="flex items-center justify-between py-1.5 pl-3 pr-4 text-xs leading-6"
            onMouseEnter={isImage ? showPreview : undefined}
            onMouseLeave={isImage ? () => setPreviewStyle(null) : undefined}
        >
            <div className="flex w-0 flex-1 items-center min-w-0 gap-2">
                {isImage ? (
                    <img className="ck-att-thumb" src={href} alt="" />
                ) : (
                    <span className="text-fg-3 flex-shrink-0">
                        <Icon name="paperclip" size={13} color="currentColor" />
                    </span>
                )}
                <span className="truncate text-fg-1">{name}</span>
            </div>
            <a href={href} target="_blank" rel="noreferrer"
               className="ml-3 flex-shrink-0 text-primary-300 hover:text-primary-200">Download</a>
            {previewStyle && (
                <div className="ck-att-preview" style={previewStyle}>
                    <img src={href} alt={name} />
                </div>
            )}
        </li>
    );
}

// One timeline row: the rail icon, who did what and when, links, and the body.
function Row({ object, icon, color, verb, className = "", links, children }) {
    const who = object.created_by?.label || "System";
    return (
        <div className={`ck-act ${className}`}>
            <div className="ck-act-ic" style={{ color }}>
                <Icon name={icon} size={12} color="currentColor" />
            </div>
            <div className="ck-act-body">
                <div className="ck-act-head flex items-center gap-2 flex-wrap">
                    <Avatar name={who} src={object.created_by?.object_images?.[0]} size={16} />
                    <span className="ck-act-who">{who}</span>
                    <span className="ck-act-what">{verb}</span>
                    <span className="ck-act-when">·&nbsp;{moment(object.created_at).fromNow()}</span>
                    <span className="ml-auto inline-flex items-center gap-2 text-2xs text-fg-3">{links}</span>
                </div>
                {children}
            </div>
        </div>
    );
}

function RecordLinks({ id, next }) {
    return (
        <>
            <Link to={url(id, "edit", { next })} className="hover:text-fg-1">Edit</Link>
            <Link to={url(id, "delete", { next })} className="hover:text-danger">Delete</Link>
        </>
    );
}

function NoteRow({ object, next }) {
    return (
        <Row object={object} icon="sticky-note" color="var(--warn)" verb="left an internal note"
             className="is-internal" links={<RecordLinks id={object.id} next={next} />}>
            {object.body && (
                <div className="ck-note-body ck-act-text mt-2"
                     dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(object.body) }} />
            )}
        </Row>
    );
}

// About a record that isn't a kind of feed entry: shows what the feed item says.
function OtherRow({ object, next }) {
    return (
        <Row object={object} icon="activity" color="var(--fg-2)" verb="posted"
             links={<RecordLinks id={object.id} next={next} />}>
            {object.body && <div className="ck-act-text mt-2"><HtmlFrame html={object.body} /></div>}
        </Row>
    );
}

// The files of an entry, as records of the kind's attachment type.
function useAttachments(attachments, entryId) {
    const filters = attachments ? { [attachments.link]: entryId } : {};
    const { data } = useQuery({
        queryKey: ["list", attachments?.type, filters],
        queryFn: () => new CrudKitAPIClient().list(attachments.type, filters),
        enabled: !!attachments,
    });
    return (data?.isPaginated ? data.results : data) || [];
}

function EntryRow({ object, type, metadata, entry, onReply, isReplyTarget, next }) {
    const id = object.related_object;
    const [showInline, setShowInline] = useState(false);
    const recordQuery = useQuery({
        queryKey: ["detail", type, id, "feed"],
        queryFn: () => new CrudKitAPIClient().retrieve(type, id),
        retry: false,
    });
    const attachments = useAttachments(entry.attachments, id);
    // Deleted since, or not for this person to see.
    if (recordQuery.isError) return null;

    const record = recordQuery.data;
    const fields = entry.fields.filter((name) => metadata.fields[name] && record && !isBlank(record[name]));
    const file = entry.attachments?.file;
    // Files the entry's HTML shows itself (`cid:` references) stay out of the list.
    const html = fields.filter((name) => metadata.fields[name].type.endsWith("WYSIWYGEditorField"))
        .map((name) => record[name]).join("");
    const isInline = (attachment) => !!attachment.content_id && html.includes(`cid:${attachment.content_id}`);
    const inlineFiles = attachments.filter(isInline);
    const withInlineFiles = (value) => inlineFiles
        .reduce((resolved, attachment) => resolved.replaceAll(`cid:${attachment.content_id}`, attachment[file]), value);
    const listed = showInline ? attachments : attachments.filter((attachment) => !isInline(attachment));
    const plain = fields.filter((name) => !isBlock(metadata.fields[name]));
    const blocks = fields.filter((name) => isBlock(metadata.fields[name]));

    const block = (name) => {
        const meta = metadata.fields[name];
        if (meta.type === "EmailWYSIWYGEditorField") return <HtmlFrame key={name} html={withInlineFiles(record[name])} />;
        if (meta.type === "WYSIWYGEditorField") {
            return <div key={name} className="ck-note-body"
                        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(withInlineFiles(record[name])) }} />;
        }
        return <ReadOnlyField key={name} value={record[name]} metadata={meta} expandable />;
    };

    return (
        <Row object={object} icon={entry.icon} color="var(--primary-400)" verb={entry.verb}
             className={isReplyTarget ? "is-replying" : ""}
             links={<>
                 {entry.reply && (
                     <button type="button" onClick={() => onReply(type, id)}
                             className="inline-flex items-center gap-1 hover:text-fg-1">
                         <Icon name="corner-up-left" size={11} color="currentColor" />
                         Reply
                     </button>
                 )}
                 <RecordLinks id={id} next={next} />
             </>}>
            {fields.length > 0 && (
                <div className="ck-act-text mt-2 flex flex-col gap-2">
                    {plain.length > 0 && (
                        <div className="ck-entry-fields">
                            {plain.map((name) => (
                                <div key={name} className="ck-entry-field">
                                    <span className="ck-entry-field-l">{metadata.fields[name].verbose_name}</span>
                                    <ReadOnlyField value={record[name]} metadata={metadata.fields[name]} />
                                </div>
                            ))}
                        </div>
                    )}
                    {blocks.map(block)}
                </div>
            )}
            {listed.length > 0 && (
                <ul role="list" className="divide-y divide-border-1 rounded-md border border-border-1 mt-2">
                    {listed.map((attachment) => (
                        <AttachmentRow key={attachment.id} href={attachment[file]}
                                       name={attachment.filename || attachment[file]?.split("/").pop()} />
                    ))}
                </ul>
            )}
            {inlineFiles.length > 0 && (
                <button type="button" className="text-2xs text-fg-3 hover:text-fg-1 mt-1"
                        onClick={() => setShowInline(!showInline)}>
                    {showInline
                        ? "Hide inline images"
                        : `Show ${inlineFiles.length} inline image${inlineFiles.length === 1 ? "" : "s"}`}
                </button>
            )}
        </Row>
    );
}

export function FeedItem({ object, onReply, isReplyTarget, next }) {
    const { type, metadata, entry, isLoading } = useFeedEntry(object.related_object);
    if (!object.related_object) return <NoteRow object={object} next={next} />;
    if (isLoading) return null;
    if (entry) {
        return <EntryRow object={object} type={type} metadata={metadata} entry={entry}
                         onReply={onReply} isReplyTarget={isReplyTarget} next={next} />;
    }
    return <OtherRow object={object} next={next} />;
}

function FieldError({ error }) {
    if (!error) return null;
    return <div className="text-2xs text-danger mt-1">{Array.isArray(error) ? error[0] : error}</div>;
}

// A label/value line of a composer form, lined up with the other lines.
function FieldRow({ name, meta, value, error, type }) {
    return (
        <div className="ck-cmp-row">
            <div className="ck-cmp-label">
                <span>{meta.verbose_name}{meta.required && <span className="ck-req"> *</span>}</span>
                {meta.help_text && <span className="ck-cmp-hint">{meta.help_text}</span>}
            </div>
            <div className="ck-cmp-field">
                <GenericDetailField fieldName={name} value={value} metadata={meta} form={true} modelType={type} />
                <FieldError error={error} />
            </div>
        </div>
    );
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function AttachmentPicker({ files, setFiles }) {
    return (
        <div className="ck-att-row">
            {files.map((file, index) => (
                <span key={index} className="ck-att-card">
                    <span className="ck-att-icon">
                        <Icon name="paperclip" size={13} color="currentColor" />
                    </span>
                    <span className="ck-att-meta">
                        <span className="ck-att-name" title={file.name}>{file.name}</span>
                        <span className="ck-att-size">{formatFileSize(file.size)}</span>
                    </span>
                    <button
                        type="button"
                        className="ck-icon-btn ck-icon-btn-sm"
                        style={{ color: "var(--fg-3)" }}
                        onClick={() => setFiles(files.filter((_, i) => i !== index))}
                        aria-label="Remove attachment"
                    >
                        <Icon name="x" size={11} color="currentColor" />
                    </button>
                </span>
            ))}
            <label className="ck-att-add" title="Attach files">
                <Icon name="plus" size={12} color="currentColor" /> Attach file
                <input type="file" multiple
                       onChange={(e) => setFiles([...files, ...Array.from(e.target.files || [])])} />
            </label>
        </div>
    );
}

const readAsDataURL = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
});

function NoteForm({ parentId, metadata, parentType, onPosted }) {
    const { isLoading, formMethods } = useCreateForm({ type: "FEI", params: { parent_object: parentId } });

    const submit = formMethods.handleSubmit((data) => {
        new CrudKitAPIClient().create("FEI", { ...data, parent_object: parentId })
            .then(() => {
                toast.success("Note posted");
                formMethods.reset();
                onPosted();
            })
            .catch((error) => {
                toast.error("Failed to add comment");
                console.error("Feed item creation error:", error);
            });
    });

    return (
        <FormProvider {...formMethods}>
            <form onSubmit={submit}>
                <div className="ck-composer-body ck-composer-rich">
                    <WYSIWYGEditorField fieldName="body" defaultValue="" metadata={metadata.fields.body}
                                        modelType={parentType} />
                </div>
                <div className="ck-composer-foot">
                    <div className="ck-composer-tools">
                        <span className="text-2xs text-fg-3">Use the toolbar to format · @mentions coming soon</span>
                    </div>
                    <button type="submit" disabled={isLoading} className="ck-btn ck-btn-primary ck-btn-sm">
                        {isLoading ? "Posting…" : "Post note"}
                    </button>
                </div>
            </form>
        </FormProvider>
    );
}

// The form for adding one kind of feed entry: its declared fields, files when
// it keeps attachments, and its action, run once the record is created.
function EntryForm({ type, metadata, parentId, parentMetadata, replyTo, onDone }) {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const entry = metadata.feed_entry;
    const { metadata: attachmentMetadata } = useMetadata(entry.attachments?.type);
    const [files, setFiles] = useState([]);
    const parentLink = parentMetadata?.relations?.find((relation) => relation.related_model_type === type)?.field_name;
    const params = useMemo(() => ({
        from_object: parentId,
        ...(parentLink && { [parentLink]: parentId }),
        ...(replyTo && { reply_to: replyTo }),
    }), [parentId, parentLink, replyTo]);

    const upload = async (client, record) => {
        const { type: attachmentType, link, file } = entry.attachments;
        const fields = attachmentMetadata?.fields || {};
        for (const picked of files) {
            await client.create(attachmentType, {
                [link]: record.id,
                [file]: await readAsDataURL(picked),
                ...(fields.filename && { filename: picked.name }),
                ...(fields.content_type && { content_type: picked.type || "application/octet-stream" }),
            }, {});
        }
        invalidateModel(queryClient, attachmentType);
    };

    const onCreated = async (record) => {
        const client = new CrudKitAPIClient();
        try {
            if (files.length) await upload(client, record);
            if (entry.action) handleActionResult(await client.action(type, record.id, entry.action), navigate, queryClient);
        } catch (error) {
            toast.error(formatApiError(error) || "Something went wrong");
        }
        onDone();
    };

    const { errors, formMethods, initialQuery, createMutation, handleSubmit } = useCreateForm({ type, params, onCreated });
    if (initialQuery.isPending) return <div className="px-3.5 py-3 text-sm text-fg-3">Loading…</div>;

    const initial = initialQuery.data || {};
    const fields = entry.fields.filter((name) => metadata.fields[name]?.editable && !metadata.fields[name].auto_created);
    const plain = fields.filter((name) => !isBlock(metadata.fields[name]));
    const blocks = fields.filter((name) => isBlock(metadata.fields[name]));
    const action = metadata.actions?.find((candidate) => candidate.action === entry.action);
    const busy = createMutation.isPending;

    return (
        <FormProvider {...formMethods}>
            <form onSubmit={handleSubmit}>
                <div className="ck-composer-body">
                    {plain.length > 0 && (
                        <div className="ck-cmp-fields">
                            {plain.map((name) => (
                                <FieldRow key={name} name={name} meta={metadata.fields[name]} value={initial[name]}
                                          error={errors?.[name]} type={type} />
                            ))}
                        </div>
                    )}
                    {blocks.map((name) => (
                        <div key={name} className="ck-composer-rich">
                            <GenericDetailField fieldName={name} value={initial[name]} metadata={metadata.fields[name]}
                                                form={true} modelType={type} />
                            <FieldError error={errors?.[name]} />
                        </div>
                    ))}
                    {entry.attachments && <AttachmentPicker files={files} setFiles={setFiles} />}
                    {errors?.non_field_errors && (
                        <div className="px-3.5 pb-2 text-xs text-danger">{errors.non_field_errors.join(", ")}</div>
                    )}
                </div>
                <div className="ck-composer-foot">
                    <span className="flex-1" />
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button type="button" onClick={onDone} className="ck-btn ck-btn-ghost ck-btn-sm">Discard</button>
                        <button type="submit" disabled={busy} className="ck-btn ck-btn-primary ck-btn-sm">
                            <Icon name={action ? "send" : "plus"} size={12} color="currentColor" />
                            {busy ? "Saving…" : action?.verbose_name || `Add ${metadata.verbose_name}`}
                        </button>
                    </div>
                </div>
            </form>
        </FormProvider>
    );
}

function ComposerTab({ tab, label, icon, active, onSelect }) {
    return (
        <button type="button" role="tab" aria-selected={active}
                className={`ck-composer-tab ${active ? "is-on" : ""}`} onClick={() => onSelect(tab)}>
            <Icon name={icon} size={12} color="currentColor" />
            {label}
        </button>
    );
}

function KindTab({ type, active, onSelect }) {
    const { metadata } = useMetadata(type);
    if (!metadata?.feed_entry) return null;
    return <ComposerTab tab={type} label={capitalize(metadata.verbose_name)} icon={metadata.feed_entry.icon}
                        active={active} onSelect={onSelect} />;
}

function KindForm({ type, ...props }) {
    const { metadata } = useMetadata(type);
    if (!metadata?.feed_entry) return null;
    return <EntryForm type={type} metadata={metadata} {...props} />;
}

export default function Feed({ model, parent_object_id, metadata, related_field_name, parentType, parentMetadata }) {
    const { pathname } = useLocation();
    const queryClient = useQueryClient();
    const kinds = parentMetadata?.feed_entries || [];

    // The composer: Note or a kind's TYPE_ID. A kind's form mounts the first
    // time its tab opens and then stays, hidden, so switching tabs keeps what
    // was typed. Lifted here so a row's Reply can drive it.
    const [activeTab, setActiveTab] = useState("note");
    const [opened, setOpened] = useState(() => new Set());
    const [replyTo, setReplyTo] = useState(null);
    // Bumped when a kind's form is sent or discarded, so it starts over.
    const [versions, setVersions] = useState({});

    const openTab = (tab) => {
        setActiveTab(tab);
        setOpened((previous) => new Set(previous).add(tab));
    };
    const refreshFeed = () => queryClient.invalidateQueries({ queryKey: ["inline-feed", model, parent_object_id] });
    const reply = (type, id) => {
        setReplyTo({ type, id });
        openTab(type);
        document.getElementById("feed-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    const done = (type) => {
        setVersions((previous) => ({ ...previous, [type]: (previous[type] || 0) + 1 }));
        setReplyTo(null);
        setActiveTab("note");
        refreshFeed();
    };

    const { data: feedData = [], isPending: isLoading, isError } = useQuery({
        queryKey: ["inline-feed", model, parent_object_id],
        queryFn: async () => {
            if (!related_field_name) return [];
            return await new CrudKitAPIClient().list(model, { [related_field_name]: parent_object_id });
        },
    });
    const objectList = feedData?.isPaginated ? feedData.results : feedData;

    return (
        <>
            <div className="flex items-center justify-between my-5 gap-3">
                <h2 className="text-xl font-semibold text-fg-1 capitalize tracking-tight">{metadata.verbose_name_plural}</h2>
            </div>
            <div id="feed-form" className="mb-5 flex flex-col gap-2">
                <div className="eyebrow">Compose</div>
                <div className="ck-composer">
                    <div className="ck-composer-tabs" role="tablist">
                        <ComposerTab tab="note" label="Note" icon="message-square" active={activeTab === "note"}
                                     onSelect={openTab} />
                        {kinds.map((type) => (
                            <KindTab key={type} type={type} active={activeTab === type} onSelect={openTab} />
                        ))}
                    </div>
                    {metadata.fields?.body && (
                        <div hidden={activeTab !== "note"}>
                            <NoteForm parentId={parent_object_id} metadata={metadata} parentType={parentType}
                                      onPosted={refreshFeed} />
                        </div>
                    )}
                    {kinds.filter((type) => opened.has(type)).map((type) => {
                        const replyId = replyTo?.type === type ? replyTo.id : null;
                        return (
                            <div key={`${type}:${replyId}:${versions[type] || 0}`} hidden={activeTab !== type}>
                                <KindForm type={type} parentId={parent_object_id} parentMetadata={parentMetadata}
                                          replyTo={replyId} onDone={() => done(type)} />
                            </div>
                        );
                    })}
                </div>
            </div>

            {isLoading ? (
                <div className="animate-pulse p-6 text-center text-fg-3">Loading feed items…</div>
            ) : isError ? (
                <div className="p-6 text-center text-danger">Error loading feed items. Please try again.</div>
            ) : objectList.length === 0 ? (
                <div className="p-6 text-center text-fg-3 italic">Nothing here yet.</div>
            ) : (
                <div className="ck-act-list">
                    {objectList.map((object) => (
                        <FeedItem key={object.id} object={object} onReply={reply} next={pathname}
                                  isReplyTarget={!!replyTo && object.related_object === replyTo.id} />
                    ))}
                </div>
            )}
        </>
    );
}
