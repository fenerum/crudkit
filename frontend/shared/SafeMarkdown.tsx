import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// SECURITY: do NOT add `rehype-raw` or any other plugin that enables raw HTML
// parsing. react-markdown's default behavior renders `<script>` etc. as
// literal text, which is exactly the XSS posture we want. Enabling rehype-raw
// would silently turn AI/customer-supplied markdown into executable HTML.

const ALLOWED_ELEMENTS = [
    "p",
    "strong",
    "em",
    "ol",
    "ul",
    "li",
    "code",
    "a",
    "br",
    "del",
];

const SAFE_URL = /^(https?:|mailto:)/i;

type LinkProps = {
    href?: string;
    children?: React.ReactNode;
};

function SafeLink({ href, children }: LinkProps) {
    if (!href || !SAFE_URL.test(href)) {
        return <>{children}</>;
    }
    return (
        <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
        </a>
    );
}

type Props = {
    source?: string | null;
    className?: string;
};

export default function SafeMarkdown({ source, className }: Props) {
    return (
        <div className={className ?? "ck-note-body"}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                allowedElements={ALLOWED_ELEMENTS}
                unwrapDisallowed
                components={{ a: SafeLink }}
            >
                {source ?? ""}
            </ReactMarkdown>
        </div>
    );
}
