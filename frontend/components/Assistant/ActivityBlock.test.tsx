import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import ActivityBlock from "./ActivityBlock";

const steps = [
  { id: "a", label: "Reading the selected rows", ok: true },
  { id: "b", label: "Drafting a change to RDG3", ok: null },
];

describe("ActivityBlock", () => {
  test("live: shows every step and the reasoning tail", () => {
    render(<ActivityBlock steps={steps} thinking="Now I should update RDG3." live startedAt={Date.now()} />);
    expect(screen.getByText(/^Working · \d+s$/)).toBeInTheDocument();
    expect(screen.getByText("Reading the selected rows")).toBeInTheDocument();
    expect(screen.getByText("Drafting a change to RDG3")).toBeInTheDocument();
    expect(screen.getByText("Now I should update RDG3.")).toBeInTheDocument();
  });

  test("finished: collapses to a summary that expands", () => {
    render(<ActivityBlock steps={steps} thinking="" live={false} seconds={38} />);
    expect(screen.queryByText("Reading the selected rows")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "2 steps · 38s" }));
    expect(screen.getByText("Reading the selected rows")).toBeInTheDocument();
  });
});
