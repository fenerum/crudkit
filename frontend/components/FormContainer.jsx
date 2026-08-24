import { Link, useNavigate } from "react-router-dom";
import { FormProvider } from "react-hook-form";
import DetailPane from "./DetailPane";
import ActionButton from "./ActionButton";
import { useHotkeys } from "react-hotkeys-hook";

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
  deleteHref = null,
  formMethods,
  modelType,
}) {
  const navigate = useNavigate();

  useHotkeys('escape', () => {
    if (cancelHref) navigate(cancelHref);
  });

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
        <Link
          to={cancelHref}
          className="text-sm font-semibold leading-6 text-fg-1"
        >
          Cancel [Esc]
        </Link>
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
  const handleFormSubmit = (e) => {
    e.preventDefault();
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
