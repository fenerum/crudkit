import { FormProvider, type UseFormReturn, useForm } from "react-hook-form";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import FiltersEditor from "./FiltersEditor";

const metadataByType = vi.hoisted<Record<string, unknown>>(() => ({
  CUS: {
    fields: {
      name: { name: "name", verbose_name: "Name", type: "CharField" },
      status: {
        name: "status",
        verbose_name: "Status",
        type: "CharField",
        choices: [["active", "Active"], ["churned", "Churned"]],
      },
      pages: { name: "pages", verbose_name: "Pages", type: "PositiveIntegerField" },
      owner: { name: "owner", verbose_name: "Owner", type: "ForeignKey", related_model: "User", related_model_type: null },
    },
  },
  TOP: { fields: { name: { name: "name", verbose_name: "Name", type: "CharField" } } },
}));

vi.mock("../../data/api", () => {
  class Client {
    async list() { return []; }
    async retrieve() { return {}; }
  }
  return {
    default: Client,
    fetchMetadata: async (type: string) => metadataByType[type],
  };
});

let form: UseFormReturn;

function Harness({ filters }: { filters: unknown }) {
  form = useForm({ defaultValues: { model: "CUS", filters } });
  return (
    <FormProvider {...form}>
      <FiltersEditor fieldName="filters" defaultValue={filters} metadata={{}} />
    </FormProvider>
  );
}

async function renderEditor(filters: unknown) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <Harness filters={filters} />
    </QueryClientProvider>,
  );
  await waitFor(() =>
    expect(screen.queryByTestId("filters-editor") || screen.queryByLabelText("Raw filters")).not.toBeNull(),
  );
}

const rows = () => screen.getAllByTestId("filter-row");
const filters = () => form.getValues("filters");

async function pick(select: HTMLElement, option: string) {
  fireEvent.keyDown(select, { key: "ArrowDown" });
  fireEvent.click(await screen.findByText(option, { selector: "[role=option], [role=option] *" }));
}

describe("FiltersEditor", () => {
  test("renders existing filters with their labels", async () => {
    await renderEditor([["status", "=", "active"], ["pages", ">=", 100]]);
    expect(rows()).toHaveLength(2);
    expect(within(rows()[0]).getByText("Status")).toBeInTheDocument();
    expect(within(rows()[0]).getByText("Active")).toBeInTheDocument();
    expect(within(rows()[1]).getByLabelText("Filter value")).toHaveValue("100");
    expect(screen.getByText("2 filters · all must match")).toBeInTheDocument();
  });

  test("adds a filter, sets its comparator and value, and removes it", async () => {
    await renderEditor([]);
    await pick(screen.getByLabelText("Filter field"), "Status");
    expect(filters()).toEqual([["status", "=", null]]);

    await pick(within(rows()[0]).getByLabelText("Filter comparator"), "!=");
    await pick(within(rows()[0]).getByLabelText("Filter value"), "Churned");
    expect(filters()).toEqual([["status", "!=", "churned"]]);

    fireEvent.click(screen.getByLabelText("Remove filter"));
    expect(filters()).toEqual([]);
  });

  test("stores numbers as numbers", async () => {
    await renderEditor([["pages", ">", null]]);
    fireEvent.change(screen.getByLabelText("Filter value"), { target: { value: "250" } });
    expect(filters()).toEqual([["pages", ">", 250]]);
  });

  test("inserts the current user variable", async () => {
    await renderEditor([["owner", "=", null]]);
    fireEvent.click(screen.getByLabelText("Insert variable"));
    fireEvent.click(screen.getByRole("button", { name: "Current user" }));
    expect(filters()).toEqual([["owner", "=", "${user}"]]);

    fireEvent.click(screen.getByLabelText("Remove Current user"));
    expect(filters()).toEqual([["owner", "=", null]]);
  });

  test("flags invalid filters without breaking, and clears the error once fixed", async () => {
    await renderEditor([
      ["status", "=", "archived"],
      ["colour", "=", "red"],
      ["name", "~", "x"],
      ["pages", ">=", "lots"],
      "oops",
    ]);
    const [choice, field, comparator, number, malformed] = rows();
    for (const row of rows()) expect(row).toHaveAttribute("data-invalid", "true");
    expect(within(choice).getByText('"archived" is not one of the choices')).toBeInTheDocument();
    expect(within(choice).getByText('"archived" (invalid)')).toBeInTheDocument();
    expect(within(field).getByText('Unknown field "colour"')).toBeInTheDocument();
    expect(within(comparator).getByText('Unknown comparator "~"')).toBeInTheDocument();
    expect(within(number).getByText('"lots" is not a number')).toBeInTheDocument();
    expect(within(malformed).getByText(/Not a \[field, comparator, value\] filter/)).toBeInTheDocument();
    expect(screen.getByText("5 filters need fixing before the view can be saved.")).toBeInTheDocument();

    await pick(within(choice).getByLabelText("Filter value"), "Active");
    expect(rows()[0]).not.toHaveAttribute("data-invalid");
    expect(filters()[0]).toEqual(["status", "=", "active"]);

    await pick(within(rows()[4]).getByLabelText("Filter field"), "Name");
    expect(filters()[4]).toEqual(["name", "=", null]);
    expect(rows()[4]).not.toHaveAttribute("data-invalid");
  });

  test("blocks submitting while a filter is invalid", async () => {
    await renderEditor([["colour", "=", "red"]]);
    let valid = true;
    await act(async () => { valid = await form.trigger("filters"); });
    expect(valid).toBe(false);
    expect(form.getFieldState("filters").error?.message).toBe("Fix the highlighted filters");
  });

  test("shows unreadable filters as text and can start over", async () => {
    await renderEditor('[["name", "="');
    expect(screen.getByLabelText("Raw filters")).toHaveValue('[["name", "="');
    fireEvent.click(screen.getByText("Start over"));
    await screen.findByTestId("filters-editor");
    expect(filters()).toEqual([]);
  });

  test("drops filters the new model doesn't have when the model changes", async () => {
    await renderEditor([["name", "=", "x"], ["status", "=", "active"]]);
    act(() => form.setValue("model", "TOP"));
    await waitFor(() => expect(filters()).toEqual([["name", "=", "x"]]));
  });
});
