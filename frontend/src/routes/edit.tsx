import { useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useEditForm } from '../../utils/formHooks';
import FormContainer from '../../components/FormContainer';
import { url } from '../../utils/urls';

export default function Edit() {
  const { segment } = useParams();
  const [searchParams] = useSearchParams();
  const nextUrl = searchParams.get('next') || undefined;

  const id = segment || '';
  const type = id.substring(0, 3);
  const editRef = useRef(null);

  const {
    handleSubmit,
    errors,
    isLoading,
    isError,
    errorMessage,
    objectQuery,
    metadataQuery,
    getFieldPairs,
    formMethods,
  } = useEditForm({ type, id });

  const object = !objectQuery.isPending ? objectQuery.data : {};
  const metadata = !metadataQuery.isPending ? metadataQuery.data?.fields : {};
  const fieldPairs = getFieldPairs();

  return (
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
      submitButtonRef={editRef}
      formMethods={formMethods}
      modelType={type}
    />
  );
}
