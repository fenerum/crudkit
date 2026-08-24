import * as React from "react";
import { describe, expect, test, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import MarkdownComposer from "./MarkdownComposer";

function Harness({ initial = "", onSubmit }: { initial?: string; onSubmit?: () => void }) {
    const [v, setV] = React.useState(initial);
    return <MarkdownComposer value={v} onChange={setV} onSubmit={onSubmit} />;
}

function selectAll(textarea: HTMLTextAreaElement) {
    textarea.setSelectionRange(0, textarea.value.length);
}

describe("MarkdownComposer", () => {
    test("Bold button wraps selection in **…**", async () => {
        render(<Harness initial="hello" />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/^Bold/));
        await act(async () => {});
        expect(ta.value).toBe("**hello**");
    });

    test("Italic button wraps selection in *…*", async () => {
        render(<Harness initial="hi" />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/^Italic/));
        await act(async () => {});
        expect(ta.value).toBe("*hi*");
    });

    test("Code button wraps selection in backticks", async () => {
        render(<Harness initial="x" />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/Inline code/));
        await act(async () => {});
        expect(ta.value).toBe("`x`");
    });

    test("Bulleted list prefixes each line with - ", async () => {
        render(<Harness initial={"a\nb"} />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/Bulleted list/));
        await act(async () => {});
        expect(ta.value).toBe("- a\n- b");
    });

    test("Numbered list prefixes each line with N. ", async () => {
        render(<Harness initial={"a\nb"} />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/Numbered list/));
        await act(async () => {});
        expect(ta.value).toBe("1. a\n2. b");
    });

    test("Link button inserts [text](url) using window.prompt", async () => {
        const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("https://example.com");
        render(<Harness initial="docs" />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.click(screen.getByLabelText(/^Link/));
        await act(async () => {});
        expect(ta.value).toBe("[docs](https://example.com)");
        promptSpy.mockRestore();
    });

    test("Cmd-B keyboard shortcut applies bold", async () => {
        render(<Harness initial="abc" />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        selectAll(ta);
        fireEvent.keyDown(ta, { key: "b", metaKey: true });
        await act(async () => {});
        expect(ta.value).toBe("**abc**");
    });

    test("Enter (no shift) calls onSubmit", () => {
        const onSubmit = vi.fn();
        render(<Harness onSubmit={onSubmit} />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        fireEvent.keyDown(ta, { key: "Enter" });
        expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    test("Shift-Enter does NOT submit", () => {
        const onSubmit = vi.fn();
        render(<Harness onSubmit={onSubmit} />);
        const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
        fireEvent.keyDown(ta, { key: "Enter", shiftKey: true });
        expect(onSubmit).not.toHaveBeenCalled();
    });
});
