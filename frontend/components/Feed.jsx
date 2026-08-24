import * as React from "react";
import moment from "moment-timezone";
import DOMPurify from "dompurify";
import CrudKitAPIClient from "../data/api";
import {useEffect, useState} from "react";
import {url} from "../utils/urls";
import {Link} from "react-router-dom";

import {useQuery, useQueryClient} from '@tanstack/react-query';
import {useCreateForm} from "@/utils/formHooks";
import {FormProvider} from "react-hook-form";
import {toast} from "react-toastify";
import {getIdPrefix} from "../utils/crudkit";
import ActionButton from "./ActionButton.jsx";
import {useAuth} from "../context/AuthContext";
import { Avatar, Icon } from "./ui";
import GenericDetailField from "./GenericDetailField.jsx";
import WYSIWYGEditorField from "./Fields/WYSIWYGEditorField";

function FeedItem({object, model, sendEmailAction, onReply, isReplyTarget}) {
    let internalFeedItem = object.related_object === null;
    const client = new CrudKitAPIClient();
    const [relatedObject, setRelatedObject] = useState(null);
    const [attachments, setAttachments] = useState(null);
    const [showOriginal, setShowOriginal] = useState(false);
    const queryClient = useQueryClient();
    const {user} = useAuth();
    const preferredLanguage = user?.preferred_language || "en";

    const isEmail = object.related_content_type ? object.related_content_type.app_label === "crm_email" : false;
    const isAISuggestion = object.related_content_type ? object.related_content_type.model === "aisuggestion" : false;

    useEffect(() => {
        if (!internalFeedItem && !relatedObject) {
            if (isEmail) {
                // legacy hack
                client.retrieve("EML", object.related_object).then((data) => {
                    setRelatedObject(data);
                });
            } else if (isAISuggestion) {
                client.retrieve("AIS", object.related_object).then((data) => {
                    setRelatedObject(data);
                });
            } else {
                client.retrieve(getIdPrefix(object.related_object) || 'N/A', object.related_object).then((data) => {
                    setRelatedObject(data);
                });
            }
        }
    }, []);

    useEffect(() => {
        if(!internalFeedItem && isEmail && !attachments && relatedObject) {
            client.list("EMA", {message: object.related_object, _fields: "filename,attachment,content_id"}).then((data) => {
                // Handle both paginated and non-paginated responses
                const attachmentData = data?.isPaginated ? data.results : data;
                setAttachments(attachmentData);
            });
        }
    }, [relatedObject]);

    const iframeRef = React.useRef();
    const iframeDefaultHeight = "140px";
    const [iframeHeight, setIframeHeight] = React.useState(iframeDefaultHeight);

    const toggleSize = () => {
        const height = iframeHeight === iframeDefaultHeight ? (iframeRef.current.contentWindow.document.body.scrollHeight + 50) + "px": iframeDefaultHeight;
        setIframeHeight(height);
    }
    const setInitialSize = () => {
        const height = Math.min(iframeRef.current.contentWindow.document.body.scrollHeight+50, parseInt(iframeDefaultHeight));
        setIframeHeight(height + "px");
    }

    const contributeAttachments = (html) => {
        if (attachments) {
            attachments.forEach((attachment) => {
                html = html.replace(`cid:${attachment.content_id}`, attachment.attachment);
            });
        }
        return html;
    }

    const iframeBaseStyle = `<style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #000; margin: 0; padding: 10px; }
      p { margin: 0 0 0.75em; }
      h1, h2, h3, h4, h5, h6 { margin: 1em 0 0.5em; font-weight: 600; line-height: 1.3; }
      h1 { font-size: 1.25em; } h2 { font-size: 1.15em; } h3 { font-size: 1.05em; }
      ul, ol { margin: 0 0 0.75em; padding-left: 1.5em; }
      li { margin-bottom: 0.25em; }
      a { color: #4f46e5; text-decoration: none; } a:hover { text-decoration: underline; }
      hr { border: none; border-top: 1px solid #e5e7eb; margin: 0.75em 0; }
      code { background: #f3f4f6; padding: 0.15em 0.35em; border-radius: 3px; font-size: 0.9em; }
      pre { background: #f3f4f6; padding: 0.75em; border-radius: 4px; overflow-x: auto; }
      pre code { background: none; padding: 0; }
      blockquote { margin: 0 0 0.75em; padding: 0.5em 1em; border-left: 3px solid #d1d5db; color: #6b7280; }
      table { border-collapse: collapse; margin: 0 0 0.75em; } td, th { border: 1px solid #e5e7eb; padding: 0.4em 0.75em; }
      strong { font-weight: 600; }
    </style>`;

    const hasTranslation = isEmail && relatedObject && relatedObject.translation
        && relatedObject.detected_language && relatedObject.detected_language !== preferredLanguage;
    const emailContent = isEmail && relatedObject
        ? contributeAttachments(relatedObject?.text_html ? relatedObject?.text_html : relatedObject?.text)
        : "";
    const translatedContent = hasTranslation ? `<p>${(relatedObject.translation || "").replace(/\n/g, "<br/>")}</p>` : "";
    // Trusted in-app content (internal notes, AI suggestions) renders inline
    // on the dark surface. External email HTML stays sandboxed in an iframe.
    const inlineHtml = (internalFeedItem || isAISuggestion) ? (object.body || "") : "";
    const useIframe = !(internalFeedItem || isAISuggestion);
    const iframeRawContent = hasTranslation && !showOriginal ? translatedContent : emailContent;
    const iframeInlineContent = iframeBaseStyle + (iframeRawContent || "");

    const handleUseSuggestion = async (suggestion) => {
        try {
            // Copy the suggested text to clipboard
            await navigator.clipboard.writeText(suggestion.suggested_text);
            
            // Mark the suggestion as applied using PATCH
            await client.partialUpdate("AIS", suggestion.id, {
                was_applied: true
            });
            
            // Update the local state
            setRelatedObject({...relatedObject, was_applied: true});
            
            toast.success('Suggestion copied to clipboard!');
            
            // Invalidate queries to refresh the feed
            queryClient.invalidateQueries(['list', 'FEI']);
        } catch (error) {
            toast.error('Failed to use suggestion');
            console.error(error);
        }
    };

    const handleDismissSuggestion = async (suggestion) => {
        try {
            // Mark the suggestion as dismissed using PATCH
            await client.partialUpdate("AIS", suggestion.id, {
                was_applied: false
            });
            
            // Soft delete the feed item
            await client.delete("FEI", object.id);
            
            toast.success('Suggestion dismissed');
            
            // Invalidate queries to refresh the feed
            queryClient.invalidateQueries(['list', 'FEI']);
        } catch (error) {
            toast.error('Failed to dismiss suggestion');
            console.error(error);
        }
    };

    // Handler for sending existing draft emails from the feed
    const handleSendEmail = async () => {
        try {
            await sendEmailAction(relatedObject.id);
            
            // Refresh feed to show updated status
            queryClient.invalidateQueries(['inline-feed', model, object.parent_object]);
        } catch {
            // Error already handled in sendEmailAction
        }
    };

    // Pick the channel icon (mail / phone / chat / etc) so each row's rail
    // dot tells you at a glance how the customer was reached. Status only
    // affects the colour and the verb — the icon stays channel-shaped.
    const channelModel = String(object.related_content_type?.model || '').toLowerCase();
    let railIcon = 'activity';
    let railColor = 'var(--fg-2)';
    let verb = 'posted';
    let subject = null;
    let isError = false;
    if (internalFeedItem) {
        railIcon = 'sticky-note';
        railColor = 'var(--warn)';
        verb = 'left an internal note';
    } else if (isAISuggestion) {
        railIcon = 'sparkles';
        railColor = 'var(--info)';
        verb = 'shared an AI suggestion';
    } else if (channelModel.includes('email')) {
        railIcon = 'mail';
        if (relatedObject) {
            subject = relatedObject.subject;
            switch (relatedObject.status) {
                case 'draft':     railColor = 'var(--fg-3)';        verb = 'drafted an email'; break;
                case 'scheduled': railColor = 'var(--danger)';      verb = 'failed to send (scheduled)'; isError = true; break;
                case 'sent':     railColor = 'var(--fg-3)';        verb = 'sent an email'; break;
                case 'delivered': railColor = 'var(--success)';    verb = 'delivered an email'; break;
                case 'read':     railColor = 'var(--success)';    verb = 'email was read'; break;
                case 'received': railColor = 'var(--primary-400)';  verb = 'received an email'; break;
                default:         railColor = 'var(--fg-2)';        verb = 'sent an email';
            }
        } else {
            verb = 'sent an email';
        }
    } else if (channelModel.includes('call') || channelModel.includes('phone') || channelModel.includes('voice')) {
        railIcon = 'phone';
        railColor = 'var(--success)';
        verb = 'logged a call';
    } else if (channelModel.includes('sms')) {
        railIcon = 'message-square';
        railColor = 'var(--info)';
        verb = 'sent an SMS';
    } else if (channelModel.includes('chat') || channelModel.includes('conversation') || channelModel.includes('message')) {
        railIcon = 'messages-square';
        railColor = 'var(--info)';
        verb = 'sent a chat message';
    } else if (channelModel.includes('meeting') || channelModel.includes('event') || channelModel.includes('calendar')) {
        railIcon = 'calendar';
        railColor = 'var(--primary-400)';
        verb = 'scheduled a meeting';
    }

    const whoName = object.created_by?.label || 'System';
    const whoImage = object.created_by?.object_images?.[0];

    const rowClass =
        'ck-act' +
        (internalFeedItem ? ' is-internal' : '') +
        (isError ? ' is-error' : '') +
        (isAISuggestion ? ' is-ai-suggestion' : '') +
        (isReplyTarget ? ' is-replying' : '');

    return (
        <div className={rowClass}>
            <div
                className="ck-act-ic"
                style={{
                    color: railColor,
                    ...(isError ? { borderColor: 'var(--danger)', background: 'var(--danger-bg)' } : null),
                }}
            >
                <Icon name={railIcon} size={12} color="currentColor" />
            </div>
            <div className="ck-act-body">
                <div className="ck-act-head flex items-center gap-2 flex-wrap">
                    <Avatar name={whoName} src={whoImage} size={16} />
                    <span className="ck-act-who">{whoName}</span>
                    <span className="ck-act-what">{verb}</span>
                    <span className="ck-act-when">·&nbsp;{moment(object.created_at).fromNow()}</span>
                    {isAISuggestion && relatedObject?.confidence_score != null && (
                        <span className="ck-act-when">· confidence {(relatedObject.confidence_score * 100).toFixed(0)}%</span>
                    )}
                    <span className="ml-auto inline-flex items-center gap-2 text-2xs text-fg-3">
                        {isEmail && relatedObject && relatedObject.status !== 'draft' && onReply && (
                            <button
                                type="button"
                                onClick={() => onReply(object.related_object)}
                                className="inline-flex items-center gap-1 hover:text-fg-1"
                            >
                                <Icon name="corner-up-left" size={11} color="currentColor" />
                                Reply
                            </button>
                        )}
                        <Link to={url(object.id, 'edit')} className="hover:text-fg-1">Edit</Link>
                        <Link to={url(object.id, 'delete')} className="hover:text-danger">Delete</Link>
                    </span>
                </div>
                {hasTranslation && (
                    <button
                        onClick={() => setShowOriginal(!showOriginal)}
                        className="mt-1 text-2xs text-primary-300 hover:text-primary-200"
                    >
                        {showOriginal
                            ? `Show translation (${relatedObject.detected_language} → ${preferredLanguage})`
                            : `Show original (${relatedObject.detected_language})`
                        }
                    </button>
                )}
                {useIframe ? (
                    <div className="ck-act-text mt-2">
                        {isEmail && relatedObject && (() => {
                            // Try to split "Name <addr@example.com>" into a display name + bare address.
                            const fromRaw = String(relatedObject.from_email || '');
                            const angleMatch = fromRaw.match(/^\s*"?([^"<]+?)"?\s*<\s*([^>]+)\s*>\s*$/);
                            const fromName = angleMatch ? angleMatch[1].trim() : fromRaw.split('@')[0];
                            const fromAddr = angleMatch ? angleMatch[2].trim() : fromRaw;
                            return (
                                <div className="ck-email-head">
                                    <Avatar name={fromName} size={32} />
                                    <div className="ck-email-meta">
                                        <div className="ck-email-from">
                                            <span className="ck-email-from-name">{fromName}</span>
                                            {fromAddr && fromAddr !== fromName && (
                                                <span className="ck-email-from-addr">&lt;{fromAddr}&gt;</span>
                                            )}
                                        </div>
                                        {subject && <div className="ck-email-subject">{subject}</div>}
                                        <div className="ck-email-recip">
                                            <span className="ck-email-recip-l">To:</span>
                                            <span>{relatedObject.to_email}</span>
                                        </div>
                                        {relatedObject.cc_emails && (
                                            <div className="ck-email-recip">
                                                <span className="ck-email-recip-l">Cc:</span>
                                                <span>{relatedObject.cc_emails}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })()}
                        <iframe
                            id={"frame-" + object.id}
                            width={"100%"}
                            height={iframeHeight}
                            ref={iframeRef}
                            onLoad={setInitialSize}
                            srcDoc={iframeInlineContent}
                            sandbox="allow-same-origin"
                            style={{
                                background: '#fff',
                                border: '1px solid var(--border-1)',
                                borderRadius: 'var(--r-md)',
                                colorScheme: 'light'
                            }}
                        />
                        {parseInt(iframeHeight) >= parseInt(iframeDefaultHeight) && (
                            <a className="text-2xs text-fg-3 hover:text-fg-1 hover:cursor-pointer mt-1 inline-block" id="show-more" onClick={toggleSize}>
                                Show {iframeHeight === iframeDefaultHeight ? "more" : "less"}
                            </a>
                        )}
                    </div>
                ) : inlineHtml ? (
                    <div
                        className={(isAISuggestion ? "ck-act-text" : "ck-note-body ck-act-text") + " mt-2"}
                        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(inlineHtml) }}
                    />
                ) : null}
                {isEmail && relatedObject && relatedObject.status === 'draft' && (
                    <div className="mt-3 flex gap-2">
                        <ActionButton
                            onPress={handleSendEmail}
                            text="Send Email"
                            color="indigo"
                        />
                        {object.related_object && (
                            <ActionButton
                                url={url(object.related_object, 'edit')}
                                text="Edit Draft"
                                color="gray"
                            />
                        )}
                    </div>
                )}
                {isAISuggestion && relatedObject && !relatedObject.was_applied && (
                    <div className="mt-3 flex gap-2">
                        <button
                            type="button"
                            onClick={() => handleUseSuggestion(relatedObject)}
                            className="ck-btn ck-btn-primary ck-btn-sm"
                        >
                            Use reply
                        </button>
                        <button
                            type="button"
                            onClick={() => handleDismissSuggestion(relatedObject)}
                            className="ck-btn ck-btn-ghost ck-btn-sm"
                        >
                            Dismiss
                        </button>
                    </div>
                )}
                {attachments && (
                        <ul role="list" className="divide-y divide-border-1 rounded-md border border-border-1 mt-2">
                            {attachments.map((attachment) => (
                                    <li className="flex items-center justify-between py-1.5 pl-3 pr-4 text-xs leading-6" key={attachment.filename}>
                                        <div className="flex w-0 flex-1 items-center min-w-0 gap-2">
                                            <span className="text-fg-3 flex-shrink-0">
                                                <Icon name="paperclip" size={13} color="currentColor" />
                                            </span>
                                            <span className="truncate text-fg-1">{attachment.filename}</span>
                                        </div>
                                        <a href={attachment.attachment} target="_blank" rel="noreferrer"
                                           className="ml-3 flex-shrink-0 text-primary-300 hover:text-primary-200">Download</a>
                                    </li>
                                ))}
                        </ul>
                )}
            </div>
        </div>
    );
}

// Email composer row shape: each row is a single labeled field that lines
// up with the rest of the column rows (label / field / optional action).
// Defined at module scope so its identity is stable across AddToFeed renders;
// otherwise the field subtree would remount on every parent state change and
// steal focus from the input the user is typing into.
function EmailFieldRow({ label, hint, required, fieldName, action, emailMetadata, emailInitial, emailErrors, parentType }) {
    const meta = emailMetadata?.[fieldName];
    if (!meta) return null;
    return (
        <div className="ck-cmp-row">
            <div className="ck-cmp-label">
                <span>{label}{required && <span className="ck-req"> *</span>}</span>
                {hint && <span className="ck-cmp-hint">{hint}</span>}
            </div>
            <div className="ck-cmp-field">
                <GenericDetailField
                    fieldName={fieldName}
                    value={emailInitial?.[fieldName]}
                    metadata={meta}
                    form={true}
                    modelType={parentType}
                />
                {emailErrors?.[fieldName] && (
                    <div className="text-2xs text-danger mt-1">
                        {Array.isArray(emailErrors[fieldName])
                            ? emailErrors[fieldName][0]
                            : emailErrors[fieldName]}
                    </div>
                )}
            </div>
            {action && <div className="ck-cmp-act">{action}</div>}
        </div>
    );
}

function AddToFeed({ parent_object_id, feedMetadata, model, sendEmailAction, parentType, activeTab, setActiveTab, replyToMessageId, setReplyToMessageId }) {

    // State for email attachments
    const [emailAttachments, setEmailAttachments] = useState([]);
    
    const handleFilesSelected = (files) => {
        setEmailAttachments(prev => [...prev, ...files]);
    };
    
    const handleRemoveAttachment = (index) => {
        setEmailAttachments(prev => prev.filter((_, i) => i !== index));
    };
    
    const formatFileSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };
    
    // Setup for email form
    const emailParams = replyToMessageId
        ? { from_object: parent_object_id, reply_to_message: replyToMessageId }
        : { from_object: parent_object_id };
    const {
        errors: emailErrors,
        isLoading: emailIsLoading,
        initialQuery: emailInitialQuery,
        metadataQuery: emailMetadataQuery,
        formMethods: emailFormMethods
    } = useCreateForm({ 
        type: "EML", 
        params: emailParams 
    });

    // Setup for feed item form
    const {
        errors: feedErrors,
        isLoading: feedIsLoading,
        formMethods: feedFormMethods
    } = useCreateForm({ 
        type: "FEI", 
        params: { parent_object: parent_object_id } 
    });

    // Get access to the query client for refreshing data
    const queryClient = useQueryClient();
    
    // Custom handler to submit and send email
    const submitEmail = () => {
        return emailFormMethods.handleSubmit((data) => {
        // Create a clean copy of the data
        const cleanData = { ...data };
        
        // Add conversation from initialData if available
        if (emailInitialQuery.data?.conversation?.id) {
            cleanData.conversation = emailInitialQuery.data.conversation.id;
        }
        
        // Create the email and stay on the page
        const client = new CrudKitAPIClient();
        
        // Try to clean object if metadata exists, but have a fallback
        let dataToSubmit = cleanData;
        try {
            if (emailMetadataQuery.data) {
                dataToSubmit = client.cleanObject(emailMetadataQuery.data, cleanData);
            }
        } catch (error) {
            console.warn('Error cleaning email data:', error);
            // Continue with the original data if there was an error
        }
        
        // Step 1: Create email as DRAFT
        client.create("EML", dataToSubmit, emailParams)
            .then((createdEmail) => {
                console.log('Email created:', createdEmail);
                console.log('Email status:', createdEmail.status);
                // Step 2: Add attachments if any
                const attachmentPromises = emailAttachments.map(async file => {
                    // Convert file to base64
                    const fileReader = new FileReader();
                    return new Promise((resolve, reject) => {
                        fileReader.readAsDataURL(file);
                        fileReader.onload = () => {
                            const base64Data = fileReader.result;
                            
                            // Create attachment with base64 data
                            resolve(client.create("EMA", {
                                message: createdEmail.id,
                                attachment: base64Data,
                                filename: file.name,
                                content_type: file.type || 'application/octet-stream',
                                content_disposition: 'attachment'
                            }));
                        };
                        fileReader.onerror = (error) => {
                            reject(error);
                        };
                    });
                });
                
                return Promise.all(attachmentPromises).then(() => createdEmail);
            })
            .then(async (createdEmail) => {
                // Step 3: Use the send_email action to trigger sending
                await sendEmailAction(createdEmail.id);
                return createdEmail;
            })
            .then(() => {
                // Reset the form and attachments; collapse back to the Note
                // tab so the composer is ready for a quick note.
                emailFormMethods.reset();
                setEmailAttachments([]);
                setActiveTab('note');
                setReplyToMessageId(null);

                // Refresh feed data
                queryClient.invalidateQueries(['inline-feed', model, parent_object_id]);
            })
            .catch((error) => {
                toast.error('Failed to send email');
                console.error('Email creation error:', error);
            });
        });
    };

    const submitFeedItem = feedFormMethods.handleSubmit((data) => {
        // Create the feed item and stay on the page
        const client = new CrudKitAPIClient();
        
        // Don't use cleanObject since it tries to validate parent_object field
        // Instead, send a direct request with the required data
        const cleanData = { ...data };
        
        // Manually add the parent_object
        cleanData.parent_object = parent_object_id;
        
        client.create("FEI", cleanData)
            .then(() => {
                toast.success('Note posted');

                // Reset the form; composer stays on the Note tab.
                feedFormMethods.reset();

                // Refresh feed data
                queryClient.invalidateQueries(['inline-feed', model, parent_object_id]);
            })
            .catch((error) => {
                toast.error('Failed to add comment');
                console.error('Feed item creation error:', error);
            });
    });

    // Setup email form fields
    const emailMetadata = !emailMetadataQuery.isPending ? emailMetadataQuery.data?.fields : null;
    const emailInitial = !emailInitialQuery.isPending ? emailInitialQuery.data : {};


    return (
        <div id="feed-form" className="mb-5 flex flex-col gap-2">
            <div className="eyebrow">Compose</div>
            <div className="ck-composer">
                <div className="ck-composer-tabs" role="tablist">
                    <button
                        type="button"
                        role="tab"
                        aria-selected={activeTab === 'note'}
                        className={`ck-composer-tab ${activeTab === 'note' ? 'is-on' : ''}`}
                        onClick={() => setActiveTab('note')}
                    >
                        <Icon name="message-square" size={12} color="currentColor" />
                        Note
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={activeTab === 'email'}
                        className={`ck-composer-tab ${activeTab === 'email' ? 'is-on' : ''}`}
                        onClick={() => setActiveTab('email')}
                    >
                        <Icon name="mail" size={12} color="currentColor" />
                        Email
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-disabled="true"
                        disabled
                        className="ck-composer-tab"
                        title="Call logging is not configured for this object"
                    >
                        <Icon name="phone" size={12} color="currentColor" />
                        Call
                    </button>
                    {activeTab === 'email' && (
                        <>
                            <span className="flex-1" />
                            <div className="flex items-center pr-1.5">
                                <button
                                    type="button"
                                    onClick={submitEmail()}
                                    disabled={emailIsLoading}
                                    className="ck-btn ck-btn-primary ck-btn-sm"
                                >
                                    <Icon name="send" size={12} color="currentColor" />
                                    {emailIsLoading ? 'Sending…' : 'Send'}
                                </button>
                            </div>
                        </>
                    )}
                </div>

                {activeTab === 'note' && feedMetadata && feedMetadata.fields?.body && (
                    <FormProvider {...feedFormMethods}>
                        <form onSubmit={submitFeedItem}>
                            <div className="ck-composer-body ck-composer-rich">
                                <WYSIWYGEditorField
                                    fieldName="body"
                                    defaultValue=""
                                    metadata={feedMetadata.fields.body}
                                    modelType={parentType}
                                />
                                {feedErrors && (
                                    <div className="px-3 pb-2 text-sm text-danger">
                                        {Object.values(feedErrors).map((error, i) => (
                                            <div key={i}>{error}</div>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <div className="ck-composer-foot">
                                <div className="ck-composer-tools">
                                    <span className="text-2xs text-fg-3">
                                        Use the toolbar to format · @mentions coming soon
                                    </span>
                                </div>
                                <button
                                    type="submit"
                                    disabled={feedIsLoading}
                                    className="ck-btn ck-btn-primary ck-btn-sm"
                                >
                                    {feedIsLoading ? 'Posting…' : 'Post note'}
                                </button>
                            </div>
                        </form>
                    </FormProvider>
                )}

                {activeTab === 'email' && emailMetadata && (
                    <FormProvider {...emailFormMethods}>
                        <form onSubmit={(e) => e.preventDefault()}>
                            <div className="ck-composer-body">
                                <div className="ck-cmp-fields">
                                    <EmailFieldRow label="From" required fieldName="email_inbox" emailMetadata={emailMetadata} emailInitial={emailInitial} emailErrors={emailErrors} parentType={parentType} />
                                    <EmailFieldRow label="To" required fieldName="to_email" emailMetadata={emailMetadata} emailInitial={emailInitial} emailErrors={emailErrors} parentType={parentType} />
                                    <EmailFieldRow label="Cc" fieldName="cc_emails" emailMetadata={emailMetadata} emailInitial={emailInitial} emailErrors={emailErrors} parentType={parentType} />
                                    <EmailFieldRow label="Subject" required fieldName="subject" emailMetadata={emailMetadata} emailInitial={emailInitial} emailErrors={emailErrors} parentType={parentType} />
                                </div>
                                {emailMetadata?.text_html && (
                                    <div className="ck-composer-rich">
                                        <WYSIWYGEditorField
                                            fieldName="text_html"
                                            defaultValue={emailInitial?.text_html || ''}
                                            metadata={emailMetadata.text_html}
                                            modelType={parentType}
                                        />
                                    </div>
                                )}
                                <div className="ck-att-row">
                                    {emailAttachments.map((file, index) => (
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
                                                style={{ color: 'var(--fg-3)' }}
                                                onClick={() => handleRemoveAttachment(index)}
                                                aria-label="Remove attachment"
                                            >
                                                <Icon name="x" size={11} color="currentColor" />
                                            </button>
                                        </span>
                                    ))}
                                    <label className="ck-att-add" title="Attach files">
                                        <Icon name="plus" size={12} color="currentColor" /> Attach file
                                        <input
                                            type="file"
                                            multiple
                                            onChange={(e) => handleFilesSelected(Array.from(e.target.files || []))}
                                        />
                                    </label>
                                </div>
                                {emailErrors?.non_field_errors && (
                                    <div className="px-3.5 pb-2 text-xs text-danger">
                                        {emailErrors.non_field_errors.join(', ')}
                                    </div>
                                )}
                            </div>
                            <div className="ck-composer-foot">
                                <span className="flex-1" />
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    <button
                                        type="button"
                                        onClick={() => { emailFormMethods.reset(); setEmailAttachments([]); setActiveTab('note'); setReplyToMessageId(null); }}
                                        className="ck-btn ck-btn-ghost ck-btn-sm"
                                    >
                                        Discard
                                    </button>
                                    <button
                                        type="button"
                                        onClick={submitEmail()}
                                        disabled={emailIsLoading}
                                        className="ck-btn ck-btn-primary ck-btn-sm"
                                    >
                                        <Icon name="send" size={12} color="currentColor" />
                                        {emailIsLoading ? 'Sending…' : 'Send'}
                                    </button>
                                </div>
                            </div>
                        </form>
                    </FormProvider>
                )}
            </div>
        </div>
    );
}


export default function Feed({fields, model, parent_object_id, metadata, related_field_name, parentType}) {
    const client = new CrudKitAPIClient();

    // Composer state is lifted here so that a Reply button on any timeline
    // row can drive the composer (switch to email tab + target a specific
    // message). Defaults reproduce the previous AddToFeed-local behavior.
    const [activeTab, setActiveTab] = useState('note');
    const [replyToMessageId, setReplyToMessageId] = useState(null);

    const handleReply = (emailId) => {
        setReplyToMessageId(emailId);
        setActiveTab('email');
        document.getElementById('feed-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    
    // Common function to send an email using the send_email action
    const sendEmailAction = async (emailId) => {
        const client = new CrudKitAPIClient();
        
        try {
            console.log('Triggering send_email action for:', emailId);
            const response = await client.action("EML", emailId, "send_email");
            console.log('Send email response:', response);
            
            // Handle successful responses (200, 202)
            if (response.messages && response.messages.length > 0) {
                // Show each message as a success toast
                response.messages.forEach(message => {
                    toast.success(message);
                });
            } else {
                // Unexpected response - warn the user
                toast.warning('Unexpected response - please check if the email was sent');
                console.warn('No messages in action response:', response);
            }
            
            // Handle redirects if needed
            if (response.redirect) {
                console.log('Redirecting to:', response.redirect);
                // Handle redirect if needed
            }
            
            return response;
        } catch (error) {
            console.error('Send email error:', error);
            
            // Try to parse error response
            if (error.response && error.response.data && error.response.data.messages) {
                // Show error messages from server
                error.response.data.messages.forEach(message => {
                    toast.error(message);
                });
            } else {
                // Generic error message
                toast.error('Failed to send email: ' + (error.message || 'Unknown error'));
            }
            
            throw error; // Re-throw for caller to handle if needed
        }
    };
    
    // Fetch the feed data
    const { data: feedData = [], isPending: isLoading, isError } = useQuery({
        queryKey: ['inline-feed', model, parent_object_id],
        queryFn: async () => {
            if (!related_field_name) return [];
            
            const params = {
                [related_field_name]: parent_object_id
            };
            
            return await client.list(model, params);
        }
    });
    
    // Extract the object list from potentially paginated response
    const objectList = feedData?.isPaginated ? feedData.results : feedData;
    
    return (
        <>
            <div className="flex items-center justify-between my-5 gap-3">
                <h2 className="text-xl font-semibold text-fg-1 capitalize tracking-tight">{metadata.verbose_name_plural}</h2>
            </div>
            <AddToFeed
                feedMetadata={metadata}
                parent_object_id={parent_object_id}
                model={model}
                sendEmailAction={sendEmailAction}
                parentType={parentType}
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                replyToMessageId={replyToMessageId}
                setReplyToMessageId={setReplyToMessageId}
            />

            {isLoading ? (
                <div className="animate-pulse p-6 text-center text-fg-3">
                    Loading feed items…
                </div>
            ) : isError ? (
                <div className="p-6 text-center text-danger">
                    Error loading feed items. Please try again.
                </div>
            ) : objectList.length === 0 ? (
                <div className="p-6 text-center text-fg-3 italic">
                    Nothing here yet.
                </div>
            ) : (
                <div className="ck-act-list">
                    {objectList.map((object) => (
                        <FeedItem
                            object={object}
                            fields={fields}
                            model={model}
                            key={object.id}
                            sendEmailAction={sendEmailAction}
                            onReply={handleReply}
                            isReplyTarget={replyToMessageId && object.related_object === replyToMessageId}
                        />
                    ))}
                </div>
            )}
        </>
    );
}