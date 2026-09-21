import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import ReadOnlyField from "./ReadOnlyField";

const textMeta = { type: "TextField" };
const longText = "line one\nline two\nline three\nline four";

// jsdom has no layout, so scrollHeight is always 0 and the overflow check never
// fires. Stub it to simulate text taller than the clamp.
function stubScrollHeight(px: number) {
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
        configurable: true,
        get: () => px,
    });
}

afterEach(() => {
    delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollHeight;
});

describe("ReadOnlyField", () => {
    test("wraps long multiline text when expandable", () => {
        const { container } = render(<ReadOnlyField value={longText} metadata={textMeta} expandable />);
        const body = container.querySelector(".ck-ro-text-body");
        expect(body?.textContent).toBe(longText);
        expect(body?.classList.contains("is-clamped")).toBe(true);
    });

    test("leaves short values as a plain span", () => {
        const { container } = render(<ReadOnlyField value="short" metadata={textMeta} expandable />);
        expect(container.querySelector(".ck-ro-text")).toBeNull();
        expect(container.textContent).toBe("short");
    });

    test("does not wrap outside the detail view", () => {
        const { container } = render(<ReadOnlyField value={longText} metadata={textMeta} />);
        expect(container.querySelector(".ck-ro-text")).toBeNull();
    });

    test("renders the label of a choice value", () => {
        const metadata = { type: "CharField", choices: [["to_read", "To read"]] };
        const { container } = render(<ReadOnlyField value="to_read" metadata={metadata} />);
        expect(container.textContent).toBe("To read");
    });

    test("falls back to the raw value for an unknown choice", () => {
        const metadata = { type: "CharField", choices: [["to_read", "To read"]] };
        const { container } = render(<ReadOnlyField value="legacy" metadata={metadata} />);
        expect(container.textContent).toBe("legacy");
    });

    test("does not wrap choice values", () => {
        const metadata = { type: "TextField", choices: [["a", "A"]] };
        const { container } = render(
            <ReadOnlyField value={"x".repeat(200)} metadata={metadata} expandable />
        );
        expect(container.querySelector(".ck-ro-text")).toBeNull();
    });

    test("toggles between Show more and Show less when clamped text overflows", () => {
        stubScrollHeight(500);
        const { container } = render(<ReadOnlyField value={longText} metadata={textMeta} expandable />);
        const button = container.querySelector("button");
        expect(button?.textContent).toBe("Show more");

        act(() => { button!.click(); });
        expect(container.querySelector(".ck-ro-text-body")?.classList.contains("is-clamped")).toBe(false);
        expect(container.querySelector("button")?.textContent).toBe("Show less");

        act(() => { container.querySelector("button")!.click(); });
        expect(container.querySelector(".ck-ro-text-body")?.classList.contains("is-clamped")).toBe(true);
        expect(container.querySelector("button")?.textContent).toBe("Show more");
    });

    test("shows no toggle when the text fits", () => {
        const { container } = render(<ReadOnlyField value={longText} metadata={textMeta} expandable />);
        expect(container.querySelector("button")).toBeNull();
    });
});
