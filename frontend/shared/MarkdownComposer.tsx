import * as React from "react";
import { Bold, Code, Italic, Link as LinkIcon, List, ListOrdered } from "lucide-react";

type Props = {
    value: string;
    onChange: (value: string) => void;
    onSubmit?: () => void;
    placeholder?: string;
    disabled?: boolean;
    rows?: number;
    submitOnEnter?: boolean;
    className?: string;
    textareaClassName?: string;
    toolbarClassName?: string;
    autoFocus?: boolean;
};

type Selection = { start: number; end: number };

function wrap(value: string, sel: Selection, prefix: string, suffix: string): { value: string; sel: Selection } {
    const before = value.slice(0, sel.start);
    const inner = value.slice(sel.start, sel.end);
    const after = value.slice(sel.end);
    const placeholder = inner || "text";
    const next = before + prefix + placeholder + suffix + after;
    const start = before.length + prefix.length;
    const end = start + placeholder.length;
    return { value: next, sel: { start, end } };
}

function prefixLines(value: string, sel: Selection, line: (i: number) => string): { value: string; sel: Selection } {
    const lineStart = value.lastIndexOf("\n", sel.start - 1) + 1;
    let lineEnd = value.indexOf("\n", sel.end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd) || "item";
    const lines = block.split("\n");
    const prefixed = lines.map((l, i) => line(i) + l).join("\n");
    const next = value.slice(0, lineStart) + prefixed + value.slice(lineEnd);
    return {
        value: next,
        sel: { start: lineStart, end: lineStart + prefixed.length },
    };
}

function insertLink(value: string, sel: Selection, url: string): { value: string; sel: Selection } {
    const before = value.slice(0, sel.start);
    const inner = value.slice(sel.start, sel.end) || "link";
    const after = value.slice(sel.end);
    const snippet = `[${inner}](${url})`;
    const next = before + snippet + after;
    return {
        value: next,
        sel: { start: before.length + 1, end: before.length + 1 + inner.length },
    };
}

export default function MarkdownComposer({
    value,
    onChange,
    onSubmit,
    placeholder,
    disabled,
    rows = 3,
    submitOnEnter = true,
    className,
    textareaClassName,
    toolbarClassName,
    autoFocus,
}: Props) {
    const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

    const apply = (transform: (v: string, sel: Selection) => { value: string; sel: Selection }) => {
        const el = textareaRef.current;
        if (!el) return;
        const sel: Selection = { start: el.selectionStart ?? value.length, end: el.selectionEnd ?? value.length };
        const next = transform(value, sel);
        onChange(next.value);
        requestAnimationFrame(() => {
            const node = textareaRef.current;
            if (!node) return;
            node.focus();
            node.setSelectionRange(next.sel.start, next.sel.end);
        });
    };

    const doBold = () => apply((v, s) => wrap(v, s, "**", "**"));
    const doItalic = () => apply((v, s) => wrap(v, s, "*", "*"));
    const doCode = () => apply((v, s) => wrap(v, s, "`", "`"));
    const doBullet = () => apply((v, s) => prefixLines(v, s, () => "- "));
    const doNumber = () => apply((v, s) => prefixLines(v, s, (i) => `${i + 1}. `));
    const doLink = () => {
        const url = typeof window !== "undefined" ? window.prompt("Link URL") : "";
        if (!url) return;
        apply((v, s) => insertLink(v, s, url));
    };

    const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        const mod = e.metaKey || e.ctrlKey;
        if (mod && (e.key === "b" || e.key === "B")) {
            e.preventDefault();
            doBold();
            return;
        }
        if (mod && (e.key === "i" || e.key === "I")) {
            e.preventDefault();
            doItalic();
            return;
        }
        if (mod && (e.key === "k" || e.key === "K")) {
            e.preventDefault();
            doLink();
            return;
        }
        if (submitOnEnter && e.key === "Enter" && !e.shiftKey && onSubmit) {
            e.preventDefault();
            onSubmit();
        }
    };

    return (
        <div className={className ?? "ck-md-composer"}>
            <div className={toolbarClassName ?? "ck-md-toolbar"} role="toolbar" aria-label="Formatting">
                <ToolBtn label="Bold (Ctrl/Cmd-B)" onClick={doBold} disabled={disabled}>
                    <Bold size={16} />
                </ToolBtn>
                <ToolBtn label="Italic (Ctrl/Cmd-I)" onClick={doItalic} disabled={disabled}>
                    <Italic size={16} />
                </ToolBtn>
                <ToolBtn label="Inline code" onClick={doCode} disabled={disabled}>
                    <Code size={16} />
                </ToolBtn>
                <ToolBtn label="Bulleted list" onClick={doBullet} disabled={disabled}>
                    <List size={16} />
                </ToolBtn>
                <ToolBtn label="Numbered list" onClick={doNumber} disabled={disabled}>
                    <ListOrdered size={16} />
                </ToolBtn>
                <ToolBtn label="Link (Ctrl/Cmd-K)" onClick={doLink} disabled={disabled}>
                    <LinkIcon size={16} />
                </ToolBtn>
            </div>
            <textarea
                ref={textareaRef}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={placeholder}
                rows={rows}
                disabled={disabled}
                className={textareaClassName}
                autoFocus={autoFocus}
            />
        </div>
    );
}

type ToolBtnProps = {
    label: string;
    onClick: () => void;
    disabled?: boolean;
    children: React.ReactNode;
};

function ToolBtn({ label, onClick, disabled, children }: ToolBtnProps) {
    return (
        <button
            type="button"
            className="ck-md-tool"
            title={label}
            aria-label={label}
            onMouseDown={(e) => e.preventDefault()}
            onClick={onClick}
            disabled={disabled}
        >
            {children}
        </button>
    );
}
