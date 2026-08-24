import { describe, expect, test } from "vitest";
import { render } from "@testing-library/react";
import SafeMarkdown from "./SafeMarkdown";

describe("SafeMarkdown", () => {
    test("renders bold", () => {
        const { container } = render(<SafeMarkdown source="**hi**" />);
        expect(container.querySelector("strong")?.textContent).toBe("hi");
    });

    test("renders italic", () => {
        const { container } = render(<SafeMarkdown source="*hi*" />);
        expect(container.querySelector("em")?.textContent).toBe("hi");
    });

    test("renders ordered list", () => {
        const { container } = render(<SafeMarkdown source={"1. a\n2. b"} />);
        const items = container.querySelectorAll("ol > li");
        expect(items.length).toBe(2);
        expect(items[0].textContent).toBe("a");
        expect(items[1].textContent).toBe("b");
    });

    test("renders bulleted list", () => {
        const { container } = render(<SafeMarkdown source={"- a\n- b"} />);
        const items = container.querySelectorAll("ul > li");
        expect(items.length).toBe(2);
    });

    test("renders inline code", () => {
        const { container } = render(<SafeMarkdown source="`x`" />);
        expect(container.querySelector("code")?.textContent).toBe("x");
    });

    test("does NOT parse raw HTML — script renders as literal text", () => {
        const hostile = "<script>alert(1)</script>";
        const { container } = render(<SafeMarkdown source={hostile} />);
        expect(container.querySelector("script")).toBeNull();
        expect(container.textContent).toContain("alert(1)");
    });

    test("does NOT parse raw HTML — img onerror is inert", () => {
        const hostile = "<img src=x onerror=alert(1)>";
        const { container } = render(<SafeMarkdown source={hostile} />);
        expect(container.querySelector("img")).toBeNull();
    });

    test("javascript: links are stripped (rendered as text)", () => {
        const src = "[click](javascript:alert(1))";
        const { container } = render(<SafeMarkdown source={src} />);
        const anchor = container.querySelector("a");
        expect(anchor).toBeNull();
        expect(container.textContent).toContain("click");
    });

    test("http(s) links pass through with safe attrs", () => {
        const { container } = render(<SafeMarkdown source="[ex](https://example.com)" />);
        const a = container.querySelector("a") as HTMLAnchorElement | null;
        expect(a).not.toBeNull();
        expect(a!.getAttribute("href")).toBe("https://example.com");
        expect(a!.getAttribute("target")).toBe("_blank");
        expect(a!.getAttribute("rel")).toBe("noopener noreferrer");
    });

    test("mailto: links pass through", () => {
        const { container } = render(<SafeMarkdown source="[mail](mailto:a@b.com)" />);
        const a = container.querySelector("a") as HTMLAnchorElement | null;
        expect(a?.getAttribute("href")).toBe("mailto:a@b.com");
    });

    test("gfm autolinks bare URLs", () => {
        const { container } = render(<SafeMarkdown source="see https://example.com here" />);
        const a = container.querySelector("a") as HTMLAnchorElement | null;
        expect(a?.getAttribute("href")).toBe("https://example.com");
    });

    test("headings are stripped (not in allowlist)", () => {
        const { container } = render(<SafeMarkdown source="# big" />);
        expect(container.querySelector("h1")).toBeNull();
        expect(container.textContent).toContain("big");
    });

    test("empty/null source renders empty wrapper", () => {
        const { container } = render(<SafeMarkdown source={null} />);
        expect(container.firstChild?.textContent).toBe("");
    });
});
