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

describe("DetailPane dependent fields", () => {
    const dealMetadata = {
        stage: { type: "CharField", verbose_name: "Stage", editable: true, depends_on: null },
        lost_reason: {
            type: "CharField", verbose_name: "Lost reason", editable: true,
            depends_on: { when: { stage: ["lost"] }, required: true },
        },
    };

    function DealForm({ stage }: { stage: string }) {
        const methods = useForm({ defaultValues: { stage } });
        return (
            <FormProvider {...methods}>
                <DetailPane field_pairs={[["stage"], ["lost_reason"]]} form={true} object={{ stage }} metadata={dealMetadata} />
            </FormProvider>
        );
    }

    test("leaves out a field that does not apply", () => {
        const { container } = render(<DealForm stage="open" />);
        const labels = [...container.querySelectorAll(".ck-vt-cell-l")].map((el) => el.textContent);
        expect(labels).toEqual(["Stage"]);
    });

    test("shows and requires the field once it applies", () => {
        const { container } = render(<DealForm stage="lost" />);
        const labels = [...container.querySelectorAll(".ck-vt-cell-l")].map((el) => el.textContent);
        expect(labels).toEqual(["Stage", "Lost reason*"]);
    });

    test("the read-only view follows the record's values", () => {
        const { container } = render(
            <DetailPane field_pairs={[["stage", "lost_reason"]]} form={null} object={{ stage: "open" }} metadata={dealMetadata} />
        );
        expect(container.querySelectorAll(".ck-vt-cell")).toHaveLength(1);
    });
});
