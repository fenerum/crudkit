import moment from "moment-timezone";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { url, valid_url } from "../utils/urls";
import { Icon } from "./ui";

export default function ReadOnlyField({ value, metadata, link = true }) {
    const iframeRef = useRef();
    const iframeDefaultHeight = "140px";
    const [iframeHeight, setIframeHeight] = useState(iframeDefaultHeight);

    if (metadata === undefined) {
        return <>[undefined]</>;
    }

    const toggleSize = () => {
        if (iframeRef.current) {
            const height = iframeHeight === iframeDefaultHeight
                ? (iframeRef.current.contentWindow.document.body.scrollHeight + 50) + "px"
                : iframeDefaultHeight;
            setIframeHeight(height);
        }
    };

    const setInitialSize = () => {
        if (iframeRef.current) {
            const height = Math.min(
                iframeRef.current.contentWindow.document.body.scrollHeight + 50,
                parseInt(iframeDefaultHeight)
            );
            setIframeHeight(height + "px");
        }
    };

    const isAIField = metadata.type?.startsWith("AI");

    const content = <>
        {metadata.type === "JSONField" || metadata.type === "AITagsField" ? (
            <span>{JSON.stringify(value)}</span>
        ) : value && metadata.type === "ImageField" ? (
            <img src={value} className="h-5 w-5 rounded-full" width={50} height={50} alt="" />
        ) : value && metadata.type === "DateTimeField" ? (
            <span>{moment(value).tz("Europe/Copenhagen").format("lll")}</span>
        ) : value && metadata.type === "DateField" ? (
            <span>{moment(value).tz("Europe/Copenhagen").format("ll")}</span>
        ) : value && (metadata.type === "ForeignKey" || metadata.type === "OneToOneField" || metadata.type === "AIForeignKeyField") ? (
            link && valid_url(value.id) ? (
                <span className="flex flex-row items-center gap-1">
                    {value.object_images && value.object_images.length > 0 && (
                        <img src={value.object_images[0]} width={50} height={50} className="h-5 w-5 rounded-full" alt="" />
                    )}
                    <Link to={url(value.id)} className="ck-fk-link font-medium">{value.label}</Link>
                </span>
            ) : <span>{value.label}</span>
        ) : value && metadata.type === "WYSIWYGEditorField" ? (
            <div className="opacity-75 show">
                <iframe
                    width="100%"
                    height={iframeHeight}
                    ref={iframeRef}
                    onLoad={setInitialSize}
                    srcDoc={value}
                    sandbox="allow-same-origin"
                    title="content"
                />
                <button type="button" className="text-xs text-fg-3 hover:cursor-pointer" onClick={toggleSize}>
                    Show {iframeHeight === iframeDefaultHeight ? "more" : "less"}
                </button>
            </div>
        ) : value && (metadata.type === "BooleanField" || metadata.type === "AIBooleanField") ? (
            <span>{value ? "Yes" : "No"}</span>
        ) : value && metadata.type === "MoneyField" ? (
            <span>
                {typeof value === 'object' && value !== null && 'amount' in value
                    ? (value.currency === value.default_currency
                        ? `${value.amount} ${value.currency}`
                        : `${value.amount} ${value.currency} (${value.amount_default_currency} ${value.default_currency})`)
                    : value}
            </span>
        ) : value && metadata.type === "PhoneNumberField" ? (
            <a href={`tel:${value}`} className="ck-fk-link">{value}</a>
        ) : value && metadata.type === "FileField" ? (
            <a href={value} target="_blank" rel="noopener noreferrer" className="ck-fk-link font-medium">{value}</a>
        ) : value && metadata.type === "CrudKitPositiveIntegerField" && typeof value === 'string' && link && valid_url(value) ? (
            <Link to={url(value)} className="ck-fk-link font-medium">{value}</Link>
        ) : (
            <span>{value}</span>
        )}
    </>;

    if (isAIField && value) {
        return (
            <span className="flex flex-row items-center gap-1">
                <Icon name="sparkles" size={14} color="#3b82f6" />
                {content}
            </span>
        );
    }

    return content;
}
