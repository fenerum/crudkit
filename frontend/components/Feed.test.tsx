import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import Feed, { FeedItem } from "./Feed";

const api = vi.hoisted(() => ({
  metadata: {} as Record<string, unknown>,
  retrieve: vi.fn(),
  list: vi.fn(),
  create: vi.fn(),
  action: vi.fn(),
}));

vi.mock("../data/api", () => {
  class Client {
    retrieve(...args: unknown[]) { return api.retrieve(...args); }
    list(...args: unknown[]) { return api.list(...args); }
    async metadata(type: string) { return api.metadata[type]; }
    async initial() { return {}; }
    create(...args: unknown[]) { return api.create(...args); }
    action(...args: unknown[]) { return api.action(...args); }
    cleanObject(_metadata: unknown, data: unknown) { return data; }
  }
  return { default: Client, fetchMetadata: async (type: string) => api.metadata[type], changeSetOf: () => null };
});

const callEntry = {
  icon: "phone",
  verb: "logged a call",
  fields: ["subject", "minutes", "notes"],
  action: null,
  compose: true,
  reply: false,
  attachments: null,
};

const callMetadata = (entry: Record<string, unknown> = {}, notesType = "WYSIWYGEditorField") => ({
  verbose_name: "call",
  type: "CAL",
  allowed_prefills: [],
  fields: {
    subject: { name: "subject", verbose_name: "Subject", type: "CharField", editable: true, required: true },
    minutes: { name: "minutes", verbose_name: "Minutes", type: "PositiveIntegerField", editable: true },
    notes: { name: "notes", verbose_name: "Notes", type: notesType, editable: true },
  },
  actions: [{ action: "send_summary", verbose_name: "Send summary", requires_approval: false }],
  relations: [],
  feed_entry: { ...callEntry, ...entry },
});

const entryItem = {
  id: "FEI1",
  related_object: "CAL1",
  body: null,
  created_at: "2026-11-10T10:00:00Z",
  created_by: { label: "Alice" },
};

function renderWithProviders(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.metadata = { CAL: callMetadata() };
  api.list.mockResolvedValue([]);
});

describe("FeedItem", () => {
  test("shows the feed item's body when its record is not a kind of entry", async () => {
    api.metadata = { MSG: { type: "MSG", fields: {}, feed_entry: null } };
    const object = { ...entryItem, related_object: "MSG1", body: "<p>Hello from chat</p>" };
    const { container } = renderWithProviders(<FeedItem object={object} onReply={vi.fn()} isReplyTarget={false} next="/AUT1" />);
    await waitFor(() => expect(container.querySelector("iframe")?.getAttribute("srcdoc")).toContain("<p>Hello from chat</p>"));
    expect(screen.getByText("posted")).toBeInTheDocument();
  });

  test("shows an entry with its kind's words and fields", async () => {
    api.retrieve.mockResolvedValue({ id: "CAL1", subject: "Renewal chat", minutes: 15, notes: "<p>Went well</p>" });
    const { container } = renderWithProviders(<FeedItem object={entryItem} onReply={vi.fn()} isReplyTarget={false} next="/AUT1" />);
    expect(await screen.findByText("Renewal chat")).toBeInTheDocument();
    expect(screen.getByText("logged a call")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(container.querySelector(".ck-note-body")?.innerHTML).toBe("<p>Went well</p>");
    expect(container.querySelector("iframe")).toBeNull();
    expect(screen.getByText("Edit").getAttribute("href")).toBe("/CAL1/edit?next=%2FAUT1");
  });

  test("frames an email body instead of showing it inline", async () => {
    api.metadata = { CAL: callMetadata({}, "EmailWYSIWYGEditorField") };
    api.retrieve.mockResolvedValue({ id: "CAL1", subject: "Hi", notes: "<p>From outside</p>" });
    const { container } = renderWithProviders(<FeedItem object={entryItem} onReply={vi.fn()} isReplyTarget={false} next="/AUT1" />);
    await waitFor(() => expect(container.querySelector("iframe")?.getAttribute("srcdoc")).toContain("<p>From outside</p>"));
    expect(container.querySelector(".ck-note-body")).toBeNull();
  });

  test("lists the entry's files", async () => {
    api.metadata = { CAL: callMetadata({ attachments: { type: "CRC", link: "call", file: "recording" } }) };
    api.retrieve.mockResolvedValue({ id: "CAL1", subject: "Hi" });
    api.list.mockResolvedValue([{ id: "CRC1", recording: "/media/recordings/abc.mp3", filename: "call.mp3" }]);
    renderWithProviders(<FeedItem object={entryItem} onReply={vi.fn()} isReplyTarget={false} next="/AUT1" />);
    expect(await screen.findByText("call.mp3")).toBeInTheDocument();
    expect(api.list).toHaveBeenCalledWith("CRC", { call: "CAL1" });
  });

  test("leaves out an entry whose record is gone", async () => {
    api.retrieve.mockRejectedValue(Object.assign(new Error("Not found"), { statusCode: 404 }));
    const { container } = renderWithProviders(<FeedItem object={entryItem} onReply={vi.fn()} isReplyTarget={false} next="/AUT1" />);
    await waitFor(() => expect(api.retrieve).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  test("offers Reply on kinds that take replies", async () => {
    api.metadata = { CAL: callMetadata({ reply: true }) };
    api.retrieve.mockResolvedValue({ id: "CAL1", subject: "Hi" });
    const onReply = vi.fn();
    renderWithProviders(<FeedItem object={entryItem} onReply={onReply} isReplyTarget={false} next="/AUT1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Reply" }));
    expect(onReply).toHaveBeenCalledWith("CAL", "CAL1");
  });
});

describe("Feed composer", () => {
  const feedMetadata = { verbose_name_plural: "feed items", fields: {} };

  test("offers a tab per kind, creates the entry from the record, then runs its action", async () => {
    api.metadata = { CAL: callMetadata({ fields: ["subject"], action: "send_summary" }) };
    api.create.mockResolvedValue({ id: "CAL1", label: "Renewal chat" });
    api.action.mockResolvedValue({ messages: ["Summary sent"] });
    renderWithProviders(
      <Feed model="FEI" parent_object_id="AUT1" metadata={feedMetadata} related_field_name="parent_object"
            parentType="AUT" parentMetadata={{ feed_entries: ["CAL"], relations: [] }} />
    );

    fireEvent.click(await screen.findByRole("tab", { name: "Call" }));
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "Renewal chat" } });
    fireEvent.click(screen.getByRole("button", { name: "Send summary" }));

    await waitFor(() => expect(api.action).toHaveBeenCalledWith("CAL", "CAL1", "send_summary"));
    expect(api.create).toHaveBeenCalledWith("CAL", { subject: "Renewal chat" }, { from_object: "AUT1" });
  });
});
