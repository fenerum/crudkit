import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import History, { sourceLabel } from "./History";

const api = vi.hoisted(() => ({ history: vi.fn(), revertChangeSet: vi.fn() }));

vi.mock("../data/api", () => {
  class Client {
    history = api.history;
    revertChangeSet = api.revertChangeSet;
  }
  return { default: Client };
});

vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: { id: 1 } }) }));

const metadata = {
  fields: {
    name: { verbose_name: "Name" },
    status: { verbose_name: "Status", choices: [["to_read", "To read"], ["finished", "Finished"]] },
  },
};

function batch(overrides: Record<string, unknown>) {
  return {
    change_set: "cs-1",
    at: "2026-09-28T12:00:00Z",
    by: { id: 1, label: "admin" },
    source: "ui",
    client: "",
    label: "",
    actions: ["update"],
    entries: [{ id: "CHG1", action: "update", field_changes: { name: ["Old", "New"] } }],
    other_records: 0,
    reverted: false,
    revertible: true,
    ...overrides,
  };
}

function renderHistory() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <History type="RDG" id="RDG1" metadata={metadata} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  api.history.mockReset();
  api.revertChangeSet.mockReset();
});

describe("sourceLabel", () => {
  test("names who or what made the change", () => {
    const me = { id: 1 };
    expect(sourceLabel(batch({}), me)).toBe("You");
    expect(sourceLabel(batch({ by: { id: 2, label: "Ada" } }), me)).toBe("Ada");
    expect(sourceLabel(batch({ source: "mcp", client: "Claude" }), me)).toBe("MCP: Claude");
    expect(sourceLabel(batch({ source: "api", client: "" }), me)).toBe("API");
    expect(sourceLabel(batch({ source: "assistant" }), me)).toBe("Assistant");
    expect(sourceLabel(batch({ source: "agent" }), me)).toBe("Agent");
    expect(sourceLabel(batch({ source: "agent", client: "Churn watch" }), me)).toBe("Agent: Churn watch");
  });
});

describe("History", () => {
  test("renders batches with their source, diff and revert state", async () => {
    api.history.mockResolvedValue([
      batch({}),
      batch({
        change_set: "cs-2",
        source: "mcp",
        client: "Claude",
        label: "Mark finished",
        actions: ["action"],
        entries: [{ id: "CHG2", action: "action", field_changes: { status: ["to_read", "finished"] } }],
        other_records: 2,
        reverted: true,
        revertible: false,
      }),
    ]);

    renderHistory();

    const [mine, theirs] = await screen.findAllByTestId("history-batch");
    expect(within(mine).getByText("You")).toBeInTheDocument();
    expect(within(mine).getByText("Updated")).toBeInTheDocument();
    expect(within(mine).getByText("Old")).toBeInTheDocument();
    expect(within(mine).getByText("New")).toBeInTheDocument();
    expect(within(mine).getByRole("button", { name: "Revert" })).toBeInTheDocument();

    expect(within(theirs).getByText("MCP: Claude")).toBeInTheDocument();
    expect(within(theirs).getByText("Mark finished")).toBeInTheDocument();
    expect(within(theirs).getByText("To read")).toBeInTheDocument();
    expect(within(theirs).getByText("Reverted")).toBeInTheDocument();
    expect(within(theirs).getByText(/Also changed 2 other records/)).toBeInTheDocument();
    expect(within(theirs).queryByRole("button", { name: "Revert" })).toBeNull();
  });

  test("asks before overwriting values changed since", async () => {
    api.history.mockResolvedValue([batch({})]);
    api.revertChangeSet
      .mockResolvedValueOnce({
        conflicts: [{ object: "RDG1", label: "Newer", field: "name", expected: "New", current: "Newer" }],
      })
      .mockResolvedValueOnce({ change_set: "cs-3", reverted: 1 });

    renderHistory();
    fireEvent.click(await screen.findByRole("button", { name: "Revert" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Changed since")).toBeInTheDocument();
    expect(api.revertChangeSet).toHaveBeenLastCalledWith("cs-1", false);

    fireEvent.click(within(dialog).getByRole("button", { name: "Revert anyway" }));

    await vi.waitFor(() => expect(api.revertChangeSet).toHaveBeenLastCalledWith("cs-1", true));
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  test("says when nothing is recorded", async () => {
    api.history.mockResolvedValue([]);
    renderHistory();
    expect(await screen.findByText("No changes recorded yet.")).toBeInTheDocument();
  });
});
