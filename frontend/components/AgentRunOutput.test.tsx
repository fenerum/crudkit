import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";
import AgentRunOutput from "./AgentRunOutput";

function renderRun(run: Record<string, unknown>) {
  return render(
    <MemoryRouter>
      <AgentRunOutput run={run} />
    </MemoryRouter>,
  );
}

describe("AgentRunOutput", () => {
  test("shows the summary and each proposal with its outcome", () => {
    renderRun({
      status: "succeeded",
      output: "Renamed Acme and asked about the email.",
      preview: [
        {
          id: "ASP1",
          kind: "patch",
          label: 'Update name="Acme Inc"',
          payload: { fields: { name: "Acme Inc" } },
          target: "CUS1",
          target_label: "Acme",
          status: "confirmed",
        },
        {
          id: "ASP2",
          kind: "patch",
          label: 'Update email="ceo@acme.test"',
          payload: { fields: { email: "ceo@acme.test" } },
          target: "CUS1",
          target_label: "Acme",
          status: "pending",
        },
      ],
    });
    expect(screen.getByText("Renamed Acme and asked about the email.")).toBeInTheDocument();
    const [applied, waiting] = screen.getAllByTestId("agent-run-proposal");
    expect(within(applied).getByText("Applied")).toBeInTheDocument();
    expect(within(applied).getByText('name = "Acme Inc"')).toBeInTheDocument();
    expect(within(applied).getByRole("link", { name: 'Update name="Acme Inc"' })).toHaveAttribute("href", "/ASP1");
    expect(within(waiting).getByText("Waiting for approval")).toBeInTheDocument();
  });

  test("a dry run lists what it would propose", () => {
    renderRun({
      status: "succeeded",
      dry_run: true,
      preview: [{ id: null, dry_run: true, kind: "note", label: "Add note: Finished", payload: { body: "Loved it" } }],
    });
    expect(screen.getByText("Would propose")).toBeInTheDocument();
    expect(screen.getByText("Dry run")).toBeInTheDocument();
    expect(screen.getByText("Loved it")).toBeInTheDocument();
    expect(screen.queryByRole("link")).toBeNull();
  });

  test("shows the error of a failed run", () => {
    renderRun({ status: "failed", error: "No AI model is configured.", preview: [] });
    expect(screen.getByText("No AI model is configured.")).toBeInTheDocument();
    expect(screen.getByText("Nothing proposed.")).toBeInTheDocument();
  });
});
