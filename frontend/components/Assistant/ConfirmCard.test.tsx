import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test, vi } from "vitest";
import ConfirmCard from "./ConfirmCard";

const props = { label: "Update priority", kind: "patch", payload: { fields: { priority: "high" } }, target: "RDG2" };

describe("ConfirmCard", () => {
  test("shows Applying… instead of the buttons while a confirm is in flight", () => {
    render(
      <MemoryRouter>
        <ConfirmCard {...props} deciding="confirm" onConfirm={vi.fn()} onSkip={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByText("Applying…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });
});
