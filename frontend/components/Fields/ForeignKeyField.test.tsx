import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import ForeignKeyField from "./ForeignKeyField";

const api = vi.hoisted(() => ({
  relatedMetadata: {} as Record<string, unknown>,
  create: vi.fn(),
}));

vi.mock("../../data/api", () => {
  class Client {
    async list() { return []; }
    async metadata() { return api.relatedMetadata; }
    async initial() { return {}; }
    create(...args: unknown[]) { return api.create(...args); }
    cleanObject(_metadata: unknown, data: unknown) { return data; }
  }
  return {
    default: Client,
    fetchMetadata: async () => api.relatedMetadata,
  };
});

const customerMetadata = (canCreate: boolean) => ({
  verbose_name: "customer",
  type: "CUS",
  allowed_prefills: [],
  search_fields: ["name"],
  can_create: canCreate,
  inline_create: true,
  fields: {
    name: { name: "name", verbose_name: "Name", type: "CharField", editable: true, required: true },
  },
  relations: [],
  actions: [],
});

let formValues: () => Record<string, unknown>;

function Harness() {
  const methods = useForm();
  formValues = methods.getValues;
  return (
    <FormProvider {...methods}>
      <ForeignKeyField fieldName="customer" metadata={{ related_model_type: "CUS", blank: true }} />
    </FormProvider>
  );
}

function renderField() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function typeInPicker(text: string) {
  fireEvent.change(screen.getByRole("combobox"), { target: { value: text } });
}

describe("ForeignKeyField inline create", () => {
  beforeEach(() => {
    api.create.mockReset();
  });

  test("creates the typed record in a modal and selects it", async () => {
    api.relatedMetadata = customerMetadata(true);
    api.create.mockResolvedValue({ id: "CUS9", label: "Acme" });
    renderField();

    await typeInPicker("Acme");
    fireEvent.click(await screen.findByText('+ Create customer "Acme"'));

    const dialog = await screen.findByRole("dialog");
    const nameInput = await waitFor(() => {
      const input = dialog.querySelector<HTMLInputElement>('input[name="name"]');
      expect(input).not.toBeNull();
      return input!;
    });
    expect(nameInput.value).toBe("Acme");

    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(api.create).toHaveBeenCalledWith("CUS", { name: "Acme" }, {});
    expect(formValues().customer).toEqual({ id: "CUS9", label: "Acme" });
    expect(screen.getByText("Acme")).toBeInTheDocument();
  });

  test("hides the create option without add permission", async () => {
    api.relatedMetadata = customerMetadata(false);
    renderField();

    await typeInPicker("Acme");
    await screen.findByText("No matches");
    expect(screen.queryByText(/Create customer/)).toBeNull();
  });
});
