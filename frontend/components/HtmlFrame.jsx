import { useRef, useState } from "react";

const COLLAPSED_HEIGHT = 140;

// Readable defaults for HTML written elsewhere (an email, a synced page), which
// brings no styles of its own, or styles that must not leak into the app.
const BASE_STYLE = `<style>
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

/** HTML in a sandboxed frame (no scripts), collapsed to a preview that can be expanded. */
export default function HtmlFrame({ html }) {
  const frameRef = useRef(null);
  const [height, setHeight] = useState(COLLAPSED_HEIGHT);
  const [fullHeight, setFullHeight] = useState(0);

  const measure = () => {
    const contentHeight = frameRef.current.contentWindow.document.body.scrollHeight + 50;
    setFullHeight(contentHeight);
    setHeight(Math.min(contentHeight, COLLAPSED_HEIGHT));
  };
  const expanded = height > COLLAPSED_HEIGHT;

  return (
    <div>
      <iframe
        ref={frameRef}
        title="content"
        width="100%"
        height={`${height}px`}
        onLoad={measure}
        srcDoc={BASE_STYLE + (html || "")}
        sandbox="allow-same-origin"
        style={{
          background: "#fff",
          border: "1px solid var(--border-1)",
          borderRadius: "var(--r-md)",
          colorScheme: "light",
        }}
      />
      {fullHeight > COLLAPSED_HEIGHT && (
        <button
          type="button"
          className="text-2xs text-fg-3 hover:text-fg-1 mt-1"
          onClick={() => setHeight(expanded ? COLLAPSED_HEIGHT : fullHeight)}
        >
          Show {expanded ? "less" : "more"}
        </button>
      )}
    </div>
  );
}
