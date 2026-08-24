import { useParams, useSearchParams } from 'react-router-dom';
import { useCreateForm } from '../../utils/formHooks';
import FormContainer from '../../components/FormContainer';

export default function Create() {
  const { segment } = useParams();
  const [searchParams] = useSearchParams();
  const params: Record<string, string> = {};
  searchParams.forEach((value, key) => { params[key] = value; });

  const type = (segment || '').substring(0, 3);
  const nextUrl = params.next;

  const {
    handleSubmit,
    errors,
    isLoading,
    isError,
    errorMessage,
    initialQuery,
    metadataQuery,
    getFieldPairs,
    formMethods,
  } = useCreateForm({ type, params });

  const initialObject = !initialQuery.isPending ? initialQuery.data : {};
  const metadata = !metadataQuery.isPending ? metadataQuery.data?.fields : {};
  const fieldPairs = getFieldPairs();

  return (
    <FormContainer
      isLoading={isLoading}
      isError={isError}
      errorMessage={errorMessage}
      object={initialObject}
      metadata={metadata}
      fieldPairs={fieldPairs}
      errors={errors}
      onSubmit={handleSubmit}
      submitButtonText="Create"
      cancelHref={nextUrl || `/${type}/`}
      formMethods={formMethods}
      modelType={type}
    />
  );
}
