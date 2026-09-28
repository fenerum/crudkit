import { useMemo } from "react";
import { useCreateForm, useMetadata } from "../utils/formHooks";
import FormContainer from "./FormContainer";
import Modal from "./Modal";

const TEXT_FIELD_TYPES = ["CharField", "TextField", "EmailField"];

/**
 * Create form for `type` in a modal, used by ForeignKeyField's "Create new…"
 * option and the kanban column "+". The text typed into the picker prefills
 * the model's first search field when that is a plain text field; `prefill`
 * sets further field values (e.g. the kanban column's group-by value).
 */
export default function InlineCreateModal({ type, initialText, prefill, onCreated, onClose }) {
  const { metadata } = useMetadata(type);

  const initialValues = useMemo(() => {
    const field = metadata?.search_fields?.[0];
    const fieldMeta = metadata?.fields?.[field];
    const isText = fieldMeta?.editable && TEXT_FIELD_TYPES.includes(fieldMeta.type);
    const values = { ...prefill, ...(initialText && isText && { [field]: initialText }) };
    return Object.keys(values).length ? values : null;
  }, [metadata, initialText, prefill]);

  const {
    handleSubmit,
    errors,
    isLoading,
    isError,
    errorMessage,
    initialQuery,
    getFieldPairs,
    formMethods,
  } = useCreateForm({ type, onCreated, initialValues });

  return (
    <Modal onClose={onClose} className="max-w-[80vw] h-[80vh] overflow-y-auto">
      <h2 className="text-lg font-semibold text-fg-1 px-4">
        New {metadata?.verbose_name || type}
      </h2>
      <FormContainer
        isLoading={isLoading}
        isError={isError}
        errorMessage={errorMessage}
        object={{ ...initialQuery.data, ...initialValues }}
        metadata={metadata?.fields || {}}
        fieldPairs={getFieldPairs()}
        errors={errors}
        onSubmit={handleSubmit}
        submitButtonText="Create"
        onCancel={onClose}
        formMethods={formMethods}
        modelType={type}
      />
    </Modal>
  );
}
