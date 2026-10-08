import { describe, expect, test } from "vitest";
import { fromTranscript, screenLabel, suggestionsFor } from "./AssistantSidebar";

describe("fromTranscript", () => {
  test("restores messages and proposals with their resolution", () => {
    const items = fromTranscript([
      { role: "user", text: "rename it" },
      {
        role: "proposal",
        id: "ASP4",
        kind: "patch",
        label: "Update name",
        payload: { fields: { name: "Acme" } },
        target: "CUS1",
        target_label: "Acme Ltd",
        status: "confirmed",
        summary: "Applied fields: name",
      },
      { role: "proposal", id: "ASP5", kind: "note", label: "Add note", payload: {}, status: "pending" },
      { role: "activity", steps: [{ id: "t1", label: "Reading CUS1", ok: true }], seconds: 12 },
    ]);
    expect(items[3]).toMatchObject({ kind: "activity", live: false, seconds: 12, steps: [{ label: "Reading CUS1" }] });
    expect(items[0]).toMatchObject({ kind: "user", text: "rename it" });
    expect(items[1]).toMatchObject({ kind: "proposal", id: "ASP4", target: "CUS1", targetLabel: "Acme Ltd", resolved: "confirmed" });
    expect(items[2]).toMatchObject({ kind: "proposal", resolved: undefined });
  });
});

describe("screenLabel and suggestions", () => {
  test("list with a selection", () => {
    const screen = { route: "list", type_id: "CUS", view_id: "VIW3", selected_ids: ["CUS1", "CUS2"] };
    expect(screenLabel(screen)).toBe("CUS list · VIW3 · 2 selected");
    expect(suggestionsFor(screen)[0]).toBe("Summarize the selected rows");
  });

  test("detail page", () => {
    const screen = { route: "detail", record_id: "CUS1", tab: "properties" };
    expect(screenLabel(screen)).toBe("CUS1 · properties");
    expect(suggestionsFor(screen)).toContain("Summarize this record");
  });

  test("open form", () => {
    const create = { route: "create", type_id: "BOK", form: { type_id: "BOK", mode: "create" } };
    expect(screenLabel(create)).toBe("New BOK");
    expect(suggestionsFor(create)).toContain("Help me fill in this form");
    const modal = { route: "detail", record_id: "AUT1", form: { type_id: "BOK", mode: "edit", record_id: "BOK3" } };
    expect(screenLabel(modal)).toBe("Editing BOK3");
  });
});
