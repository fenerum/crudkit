import { Link, useNavigate } from "react-router-dom";
import { FormProvider } from "react-hook-form";
import DetailPane from "./DetailPane";
import ActionButton from "./ActionButton";
import { useHotkeys } from "react-hotkeys-hook";
import { isModalOpen } from "./Modal";

export default function FormContainer({
  isLoading,
  isError,
  errorMessage,
  object,
  metadata,
  fieldPairs,
  errors,
  onSubmit,
  submitButtonText = "Save",
  cancelHref,
  onCancel = null,
  deleteHref = null,
  formMethods,
  modelType,
}) {
  const navigate = useNavigate();

  // A form rendered inside a Modal (onCancel) leaves Esc to the Modal; the page
  // form must ignore Esc while any modal is open or it would discard itself.
  useHotkeys('escape', () => {
    if (cancelHref && !isModalOpen()) navigate(cancelHref);
  }, { enabled: !onCancel });

  if (isLoading) {
    return <p>Loading...</p>;
  }

  if (isError) {
    return <p>Error: {errorMessage}</p>;
  }

  const formContent = (
    <>
      <DetailPane
        field_pairs={fieldPairs}
        object={object}
        metadata={metadata}
        form={true}
        errors={errors}
        modelType={modelType}
      />
      <div className="mt-6 flex flex-row items-center justify-end gap-x-6 pb-8">
        {deleteHref && (
          <Link
            to={deleteHref}
            className="text-sm font-semibold leading-6 text-danger"
          >
            Delete
          </Link>
        )}
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="text-sm font-semibold leading-6 text-fg-1"
          >
            Cancel [Esc]
          </button>
        ) : (
          <Link
            to={cancelHref}
            className="text-sm font-semibold leading-6 text-fg-1"
          >
            Cancel [Esc]
          </Link>
        )}
        <ActionButton
          text={submitButtonText}
          onPress={onSubmit}
          color="green"
        />
      </div>
    </>
  );

  const containerStyle = { padding: '1rem' };

  // `onSubmit` from useCreate/useEditForm is already a `formMethods.handleSubmit`
  // wrapper, so the form's submit handler just hands the event off to it. Wrapping
  // again here would re-run validation and accidentally double-invoke mutations.
  // React events bubble through portals, so a form inside a Modal must not
  // let its submit reach the form rendered underneath it.
  const handleFormSubmit = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (formMethods?.formState.isSubmitting) return;
    onSubmit();
  };

  if (formMethods) {
    return (
      <FormProvider {...formMethods}>
        <form onSubmit={handleFormSubmit} style={containerStyle}>
          {formContent}
          {/* Hidden submit button so Enter inside any text input triggers
              the form's onSubmit. The visible Save ActionButton stays a
              type="button" with its own click handler / loading state. */}
          <button type="submit" tabIndex={-1} aria-hidden="true" style={{ display: 'none' }} />
        </form>
      </FormProvider>
    );
  }

  return (
    <div style={containerStyle}>
      {formContent}
    </div>
  );
}
