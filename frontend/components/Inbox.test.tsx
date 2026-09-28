import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import Inbox from "./Inbox";
import { prettyPayload } from "../shared/ProposalPayload";

const api = vi.hoisted(() => ({ list: vi.fn(), action: vi.fn(), fetchObjects: vi.fn() }));
const auth = vi.hoisted(() => ({ proposals: true }));

vi.mock("../data/api", () => {
  class Client {
    list = api.list;
    action = api.action;
  }
  return { default: Client, fetchObjects: api.fetchObjects };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ user: { id: 1, assistant: { proposals: auth.proposals } } }),
}));

const PROPOSALS = [
  {
    id: "ASP4",
    kind: "patch",
    label: "Update title",
    reasoning: "The title has a typo",
    payload: { fields: { title: "Dune" } },
    target: "BOK7",
    source: "mcp",
    client: "Research Bot",
    created_at: "2026-09-28T12:00:00Z",
  },
  {
    id: "ASP5",
    kind: "create",
    label: "Create book",
    payload: { type: "BOK", fields: { title: "Emma" } },
    target: null,
    source: "assistant",
    client: "",
  },
];

function renderInbox(qc = new QueryClient()) {
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/inbox?tab=proposals"]}>
        <Inbox />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return qc;
}

beforeEach(() => {
  auth.proposals = true;
  api.list.mockReset().mockResolvedValue([]);
  api.action.mockReset().mockResolvedValue({ messages: ["Confirmed"] });
  api.fetchObjects.mockReset().mockResolvedValue({ isPaginated: true, count: 2, results: PROPOSALS });
});

describe("Inbox proposals tab", () => {
  test("lists pending proposals with their target, source and payload", async () => {
    renderInbox();

    const rows = await screen.findAllByTestId("proposal");
    expect(api.fetchObjects).toHaveBeenCalledWith("ASP", { status: "pending", page_size: 50 });
    expect(rows).toHaveLength(2);

    const patch = within(rows[0]);
    expect(patch.getByText("Update title")).toBeInTheDocument();
    expect(patch.getByText("MCP: Research Bot")).toBeInTheDocument();
    expect(patch.getByRole("link", { name: "BOK7" })).toHaveAttribute("href", "/BOK7");
    expect(patch.getByText('title = "Dune"')).toBeInTheDocument();
    expect(patch.getByText("The title has a typo")).toBeInTheDocument();

    const create = within(rows[1]);
    expect(create.getByText("Assistant")).toBeInTheDocument();
    expect(create.getByRole("link", { name: "New BOK" })).toHaveAttribute("href", "/BOK/");
  });

  test("confirm runs the confirm action and refreshes the target", async () => {
    const qc = renderInbox();
    const invalidate = vi.spyOn(qc, "invalidateQueries");

    const [row] = await screen.findAllByTestId("proposal");
    fireEvent.click(within(row).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(api.action).toHaveBeenCalledWith("ASP", "ASP4", "confirm"));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["detail", "BOK"] }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["list", "ASP"] });
  });

  test("a confirmed create refreshes the new record's type", async () => {
    api.action.mockResolvedValue({ outcome: { kind: "create", id: "BOK9" } });
    const qc = renderInbox();
    const invalidate = vi.spyOn(qc, "invalidateQueries");

    const rows = await screen.findAllByTestId("proposal");
    fireEvent.click(within(rows[1]).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["list", "BOK"] }));
  });

  test("skip runs the skip action; errors show on the row", async () => {
    api.action.mockRejectedValue(Object.assign(new Error("Invalid Request"), { errors: ["Target is gone"] }));
    renderInbox();

    const [row] = await screen.findAllByTestId("proposal");
    fireEvent.click(within(row).getByRole("button", { name: "Skip" }));

    await waitFor(() => expect(api.action).toHaveBeenCalledWith("ASP", "ASP4", "skip"));
    expect(await within(row).findByText("Target is gone")).toBeInTheDocument();
  });

  test("empty state", async () => {
    api.fetchObjects.mockResolvedValue({ isPaginated: true, count: 0, results: [] });
    renderInbox();
    expect(await screen.findByText("Nothing to approve")).toBeInTheDocument();
  });

  test("falls back to all activity without proposals", async () => {
    auth.proposals = false;
    renderInbox();
    expect(await screen.findByText("Inbox zero")).toBeInTheDocument();
    expect(api.fetchObjects).not.toHaveBeenCalled();
  });
});

describe("prettyPayload", () => {
  test("describes a create", () => {
    expect(prettyPayload("create", { type: "BOK", fields: { title: "Emma", pages: 3 } })).toBe(
      'Create BOK\ntitle = "Emma"\npages = 3'
    );
  });
});
