import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormProvider, useForm } from "react-hook-form";
import { toast } from "react-toastify";
import CrudKitAPIClient from "../data/api";
import { invalidateModel, invalidateRecords } from "../data/invalidate";
import { JOBS_KEY } from "../data/jobs";
import { formatApiError } from "../utils/apiErrors";
import { url } from "../utils/urls";
import GenericDetailField from "./GenericDetailField";
import Modal from "./Modal";
import { showSuccessToast } from "./SuccessToast";
import { Button, OverflowMenu } from "./ui";

const SKIPPED_SHOWN = 3;

function editableFields(metadata) {
    return Object.entries(metadata.fields).filter(([, field]) => field.editable && !field.auto_created);
}

// What a bulk change did: a toast with Undo for the records it changed, and a
// warning naming those it skipped.
function report(result, metadata, verb, queryClient) {
    const { done, skipped } = result;
    if (done) {
        const noun = done === 1 ? metadata.verbose_name : metadata.verbose_name_plural;
        showSuccessToast({
            label: `${done} ${noun}`,
            verb,
            changeSet: result._change_set,
            onUndone: () => invalidateRecords(queryClient),
        });
    }
    if (skipped.length) {
        const names = skipped.slice(0, SKIPPED_SHOWN).map((row) => `${row.label} (${row.reason})`);
        const more = skipped.length > SKIPPED_SHOWN ? ` and ${skipped.length - SKIPPED_SHOWN} more` : "";
        toast.warning(`Skipped ${names.join(", ")}${more}`);
    }
}

function EditFieldModal({ metadata, count, onSubmit, onClose, isPending }) {
    const fields = editableFields(metadata);
    const [fieldName, setFieldName] = useState(fields[0]?.[0] || "");
    const methods = useForm();

    const submit = methods.handleSubmit((values) => {
        const value = values[fieldName];
        onSubmit({ [fieldName]: value && typeof value === "object" && "id" in value ? value.id : value });
    });

    return (
        <Modal onClose={onClose}>
            <form onSubmit={submit} className="flex flex-col gap-4">
                <h2 className="text-base font-semibold text-fg-1">
                    Edit {count} {count === 1 ? metadata.verbose_name : metadata.verbose_name_plural}
                </h2>
                <label className="flex flex-col gap-1 text-sm text-fg-2">
                    Field
                    <select
                        className="ck-input"
                        value={fieldName}
                        onChange={(e) => setFieldName(e.target.value)}
                        aria-label="Field"
                    >
                        {fields.map(([name, field]) => (
                            <option key={name} value={name}>{field.verbose_name || name}</option>
                        ))}
                    </select>
                </label>
                <FormProvider {...methods}>
                    <GenericDetailField
                        key={fieldName}
                        fieldName={fieldName}
                        form
                        metadata={metadata.fields[fieldName]}
                        modelType={metadata.type}
                    />
                </FormProvider>
                <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
                    <Button size="sm" variant="primary" type="submit" disabled={isPending}>
                        Set on {count}
                    </Button>
                </div>
            </form>
        </Modal>
    );
}

function DeleteModal({ metadata, count, onConfirm, onClose, isPending }) {
    return (
        <Modal onClose={onClose}>
            <h2 className="text-base font-semibold text-fg-1 mb-2">Delete {count} {metadata.verbose_name_plural}?</h2>
            <p className="text-sm text-fg-2 mb-4">You can undo this, or restore each one from its History.</p>
            <div className="flex justify-end gap-2">
                <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
                <Button size="sm" variant="danger" onClick={onConfirm} disabled={isPending}>
                    Delete {count}
                </Button>
            </div>
        </Modal>
    );
}

// The bar over a list's selection: change a field, run an action, merge or
// delete every selected record in one go.
export default function BulkBar({ model, metadata, selected, onClear }) {
    const [dialog, setDialog] = useState(null);
    const queryClient = useQueryClient();
    const count = selected.length;

    const mutation = useMutation({
        mutationFn: ({ operation, payload }) => new CrudKitAPIClient().bulk(model, selected, operation, payload),
        onSuccess: (result, { verb }) => {
            setDialog(null);
            onClear();
            invalidateModel(queryClient, model);
            if (result.job) queryClient.invalidateQueries({ queryKey: JOBS_KEY });
            report(result, metadata, verb, queryClient);
        },
        onError: (error) => toast.error(formatApiError(error, metadata.fields) || "Couldn't change the records"),
    });
    const run = (operation, verb, payload) => mutation.mutate({ operation, verb, payload });

    const actionItems = metadata.can_change
        ? metadata.actions.map((action) => ({
            label: action.verbose_name,
            onSelect: () => run("action", "changed", { action: action.action }),
        }))
        : [];
    const mergeUrl = `${url(model, "merge")}?${new URLSearchParams(selected.map((id) => ["object_id", id]))}`;

    return (
        <div className="flex items-center gap-2.5 rounded-md border border-border-1 bg-bg-2 px-3 py-2" role="toolbar" aria-label="Selection">
            <span className="text-sm text-fg-2">{count} selected</span>
            <button type="button" className="text-sm text-fg-3 underline" onClick={onClear}>Clear</button>
            <span className="flex-1" />
            {metadata.can_change && editableFields(metadata).length > 0 && (
                <Button size="sm" icon="edit-3" onClick={() => setDialog("edit")}>Edit field</Button>
            )}
            <OverflowMenu items={actionItems} label="Run action" shortcut={null} />
            {metadata.can_change && count > 1 && (
                <Link to={mergeUrl} className="ck-btn ck-btn-secondary ck-btn-sm">Merge</Link>
            )}
            {metadata.can_delete && (
                <Button size="sm" variant="danger" icon="trash-2" onClick={() => setDialog("delete")}>Delete</Button>
            )}
            {dialog === "edit" && (
                <EditFieldModal
                    metadata={metadata}
                    count={count}
                    isPending={mutation.isPending}
                    onClose={() => setDialog(null)}
                    onSubmit={(fields) => run("update", "updated", { fields })}
                />
            )}
            {dialog === "delete" && (
                <DeleteModal
                    metadata={metadata}
                    count={count}
                    isPending={mutation.isPending}
                    onClose={() => setDialog(null)}
                    onConfirm={() => run("delete", "deleted")}
                />
            )}
        </div>
    );
}
