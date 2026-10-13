import { FormProvider, useForm } from "react-hook-form";
import { describe, expect, test } from "vitest";
import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import DetailPane from "./DetailPane";

const metadata = {
    name: { type: "CharField", verbose_name: "Name", editable: true, help_text: "Shown in the sidebar." },
    order: { type: "IntegerField", verbose_name: "Order", editable: true, help_text: "" },
};

function WithForm({ children }: { children: ReactNode }) {
    const methods = useForm();
    return <FormProvider {...methods}>{children}</FormProvider>;
}

function renderPane(form: boolean) {
    return render(
        <WithForm>
            <DetailPane field_pairs={[["name", "order"]]} form={form} object={{}} metadata={metadata} />
        </WithForm>
    );
}

describe("DetailPane help text", () => {
    test("shows a field's help text in the form", () => {
        const { container } = renderPane(true);
        const help = container.querySelectorAll(".ck-vt-cell-help");
        expect(help).toHaveLength(1);
        expect(help[0].textContent).toBe("Shown in the sidebar.");
    });

    test("hides help text on the read-only detail view", () => {
        const { container } = renderPane(false);
        expect(container.querySelector(".ck-vt-cell-help")).toBeNull();
    });
});
