import { useParams } from 'react-router-dom';
import { useDeleteForm } from '../../utils/formHooks';
import DeleteConfirmation from '../../components/DeleteConfirmation';
import { url } from '../../utils/urls';

export default function DeleteRoute() {
  const { segment } = useParams();
  const id = segment || '';
  const type = id.substring(0, 3);

  const {
    handleDelete,
    isLoading,
    isError,
    errorMessage,
    objectQuery,
    deleteMutation,
  } = useDeleteForm({ type, id });

  const object = !objectQuery.isPending ? objectQuery.data : null;

  return (
    <DeleteConfirmation
      isLoading={isLoading}
      isError={isError}
      errorMessage={errorMessage}
      object={object}
      onDelete={handleDelete}
      onCancel={url(id)}
      isPending={deleteMutation.isPending}
    />
  );
}
