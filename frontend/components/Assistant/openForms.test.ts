import { describe, expect, test, vi } from "vitest";
import { activeForm, formScreen, formSnapshot, registerForm, toFormValue, type OpenForm } from "./openForms";

vi.mock("../../utils/appConfig", () => ({ appConfig: { default_currency: "DKK" } }));

function makeForm(overrides: Partial<OpenForm> = {}, values: Record<string, unknown> = {}): OpenForm {
  return {
    type: "BOK",
    mode: "create",
    metadata: {},
    formMethods: { getValues: () => values } as unknown as OpenForm["formMethods"],
    fill: () => {},
    ...overrides,
  };
}

describe("open forms", () => {
  test("the innermost form is active until it closes", () => {
    const page = makeForm({ type: "RDG" });
    const modal = makeForm({ type: "BOK" });
    const closePage = registerForm(page);
    const closeModal = registerForm(modal);
    expect(activeForm()).toBe(modal);
    closeModal();
    expect(activeForm()).toBe(page);
    closePage();
    expect(activeForm()).toBeNull();
  });

  test("snapshot keeps editable values as scalars", () => {
    const form = makeForm(
      {
        mode: "edit",
        recordId: "BOK3",
        metadata: {
          title: { type: "CharField", editable: true },
          author: { type: "ForeignKey", editable: true },
          price: { type: "MoneyField", editable: true },
          notes: { type: "TextField", editable: true },
          id: { type: "CrudKitIDField", editable: false },
        },
      },
      { id: "BOK3", title: "Dune", author: { id: "AUT1", label: "Herbert" }, price: { amount: "9.50" }, notes: "x".repeat(900) },
    );
    expect(formScreen(form)).toEqual({ type_id: "BOK", mode: "edit", record_id: "BOK3" });
    expect(formScreen(form, true).values).toEqual({ title: "Dune", author: "AUT1", price: "9.50", notes: "x".repeat(500) });
    expect(formSnapshot(form)).not.toHaveProperty("id");
  });

  test("money values become the field's object, keeping the chosen currency", () => {
    const meta = { type: "MoneyField" };
    expect(toFormValue(meta, 12.5)).toEqual({
      currency: "DKK",
      amount: "12.5",
      amount_default_currency: "12.5",
      default_currency: "DKK",
    });
    expect(toFormValue(meta, "3", { currency: "EUR", amount: "1" })).toMatchObject({ currency: "EUR", amount: "3" });
    expect(toFormValue(meta, null)).toBeNull();
    const author = { id: "AUT1", label: "Herbert" };
    expect(toFormValue({ type: "ForeignKey" }, author)).toBe(author);
    expect(toFormValue(undefined, "Dune")).toBe("Dune");
  });
});
