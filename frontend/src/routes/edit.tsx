import { useParams, useSearchParams } from 'react-router-dom';
import { useEditForm } from '../../utils/formHooks';
import FormContainer from '../../components/FormContainer';
import { Button } from '../../components/ui';
import { url } from '../../utils/urls';

export default function Edit() {
  const { segment } = useParams();
  const [searchParams] = useSearchParams();
  const nextUrl = searchParams.get('next') || undefined;

  const id = segment || '';
  const type = id.substring(0, 3);

  const {
    handleSubmit,
    errors,
    isLoading,
    isError,
    errorMessage,
    seededObject,
    remoteChanged,
    reloadRemote,
    metadataQuery,
    getFieldPairs,
    formMethods,
  } = useEditForm({ type, id });

  const object = seededObject || {};
  const metadata = !metadataQuery.isPending ? metadataQuery.data?.fields : {};
  const fieldPairs = getFieldPairs();

  return (
    <>
      {remoteChanged && (
        <div
          role="status"
          className="mb-4 flex items-center gap-3 rounded-md border border-border-1 bg-bg-2 px-3 py-2 text-sm"
        >
          <span className="flex-1 text-fg-2">
            <span className="text-warn">●</span> This record was changed elsewhere. Reloading discards your unsaved edits.
          </span>
          <Button size="sm" icon="refresh" onClick={reloadRemote}>
            Reload
          </Button>
        </div>
      )}
      <FormContainer
        isLoading={isLoading}
        isError={isError}
        errorMessage={errorMessage}
        object={object}
        metadata={metadata}
        fieldPairs={fieldPairs}
        errors={errors}
        onSubmit={handleSubmit}
        submitButtonText="Save"
        cancelHref={nextUrl || url(id)}
        deleteHref={url(id, 'delete', nextUrl ? { next: nextUrl } : {})}
        formMethods={formMethods}
        modelType={type}
      />
    </>
  );
}
