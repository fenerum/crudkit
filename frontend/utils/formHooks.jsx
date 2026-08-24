import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FormProvider, useForm } from 'react-hook-form';
import { toast } from 'react-toastify';
import CrudKitAPIClient, { fetchMetadata } from '../data/api';
import { invalidateModel } from '../data/invalidate';
import generateFieldPairs from './fieldpairs';
import { url } from './urls';

const showSuccessToastWithLink = (action, data, navigate) => {
  const label = data.label || data._label || 'Item';
  const itemId = data.id;

  toast.success(
    <button
      type="button"
      onClick={() => navigate(url(itemId))}
      className="text-left bg-transparent border-0 p-0 cursor-pointer"
    >
      <span className="underline font-semibold">{label}</span>
      <span> {action} successfully</span>
    </button>,
  );
};

export function useCrudForm({ type, defaultValues = {} }) {
  const [errors, setErrors] = useState(null);
  const navigate = useNavigate();

  const methods = useForm({ defaultValues, mode: 'onBlur' });

  const client = new CrudKitAPIClient();

  const metadataQuery = useQuery({
    queryKey: ['metadata', type],
    queryFn: () => client.metadata(type),
  });

  const layoutsQuery = useQuery({
    queryKey: ['layouts', type],
    queryFn: () => client.list('LAY', { model: type }),
  });

  let layoutData = null;
  if (!layoutsQuery.isPending && layoutsQuery.data) {
    const layouts = layoutsQuery.data?.isPaginated
      ? layoutsQuery.data.results
      : layoutsQuery.data;
    if (Array.isArray(layouts) && layouts.length > 0) {
      layoutData = layouts[0];
    }
  }

  const getFieldPairs = () => {
    if (!metadataQuery.data) return [];
    return generateFieldPairs(metadataQuery.data, layoutData);
  };

  const handleMutationError = (error) => {
    let errorData = null;

    if (error.errorData) {
      errorData = error.errorData;
      if (typeof errorData === 'object') {
        Object.keys(errorData).forEach((key) => {
          if (Array.isArray(errorData[key])) {
            methods.setError(key, { type: 'server', message: errorData[key][0] });
          }
        });
      }
    } else if (error.errors) {
      errorData = error.errors;
      Object.keys(errorData).forEach((key) => {
        methods.setError(key, {
          type: 'validation',
          message: Array.isArray(errorData[key]) ? errorData[key][0] : errorData[key],
        });
      });
    } else {
      errorData = { non_field_errors: [error.message || 'An error occurred'] };
      methods.setError('root', { type: 'server', message: error.message || 'An error occurred' });
    }

    setErrors(errorData);
  };

  const getFormData = () => methods.getValues();

  const isLoading = metadataQuery.isPending || layoutsQuery.isPending;
  const isError = metadataQuery.isError || layoutsQuery.isError;
  const errorMessage = metadataQuery.error?.message || layoutsQuery.error?.message;

  return {
    client,
    metadataQuery,
    layoutsQuery,
    errors,
    setErrors,
    handleMutationError,
    getFormData,
    getFieldPairs,
    layoutData,
    isLoading,
    isError,
    errorMessage,
    router: { push: navigate, replace: (to) => navigate(to, { replace: true }) },
    formMethods: methods,
  };
}

export function useCreateForm({ type, params = {} }) {
  const [searchParams] = useSearchParams();
  const nextUrl = searchParams.get('next');

  const formUtils = useCrudForm({ type, params, defaultValues: {} });
  const { client, handleMutationError, router, formMethods, metadataQuery } = formUtils;
  const queryClient = useQueryClient();

  // Filter the URL params to those the model exposes as `allowed_prefills`.
  // The `/initial/` endpoint applies the same gate server-side, but doing it
  // here keeps the form submission body free of stray query keys (`next`, etc.)
  // so cleanObject doesn't warn about unknown fields.
  const allowedPrefillsParams = useMemo(() => {
    const allowed = metadataQuery.data?.allowed_prefills || [];
    const out = {};
    for (const key of allowed) {
      if (params[key] !== undefined) out[key] = params[key];
    }
    // `from_object` is a meta-param consumed by `Model.from_query_params` to
    // resolve initial relations (e.g. Email→Conversation, signature, history).
    // Not a model field, so it isn't in `allowed_prefills` — pass it through
    // explicitly so /initial/ and /create/ both receive it.
    if (params.from_object !== undefined) out.from_object = params.from_object;
    if (params.reply_to_message !== undefined) out.reply_to_message = params.reply_to_message;
    return out;
  }, [metadataQuery.data, params]);

  const initialQuery = useQuery({
    queryKey: ['initial', type, JSON.stringify(allowedPrefillsParams)],
    queryFn: () => client.initial(type, allowedPrefillsParams),
    enabled: !!metadataQuery.data,
  });

  // Apply prefills onto the form whenever the initial query resolves.
  // (react-query v5 dropped `onSuccess`, so we wire this through useEffect.)
  useEffect(() => {
    if (!initialQuery.data) return;
    for (const [key, value] of Object.entries(initialQuery.data)) {
      formMethods.setValue(key, value, { shouldValidate: true });
    }
  }, [initialQuery.data, formMethods]);

  const createMutation = useMutation({
    mutationFn: (data) => {
      try {
        const cleanedData = client.cleanObject(metadataQuery.data, data);
        return client.create(type, cleanedData, allowedPrefillsParams);
      } catch (error) {
        if (error.errors) formUtils.setErrors(error.errors);
        throw error;
      }
    },
    onSuccess: (data) => {
      invalidateModel(queryClient, type, { viewModel: data?.model });
      showSuccessToastWithLink('created', data, router.push);
      router.push(nextUrl || url(data.id));
    },
    onError: (error) => {
      const detail = error.message ? `: ${error.message}` : '';
      toast.error(`Failed to create item${detail}`);
      handleMutationError(error);
    },
  });

  const handleSubmit = formMethods.handleSubmit((data) => createMutation.mutateAsync(data));

  return {
    ...formUtils,
    initialQuery,
    createMutation,
    handleSubmit,
    FormProvider,
    isLoading: formUtils.isLoading || initialQuery.isPending,
    isError: formUtils.isError || initialQuery.isError,
    errorMessage: formUtils.errorMessage || initialQuery.error?.message,
  };
}

export function useEditForm({ type, id }) {
  const [searchParams] = useSearchParams();
  const nextUrl = searchParams.get('next');

  const formUtils = useCrudForm({ type, id });
  const { client, handleMutationError, router, formMethods } = formUtils;
  const queryClient = useQueryClient();

  const objectQuery = useQuery({
    queryKey: ['detail', type, id],
    queryFn: () => client.retrieve(type, id),
  });

  useEffect(() => {
    if (!objectQuery.data || !formUtils.metadataQuery.data) return;
    // Only seed values for keys the model actually exposes as fields. The
    // detail endpoint returns server-side extras (`label`, `object_images`, …)
    // that aren't editable and would otherwise get echoed back in the
    // submission payload, tripping cleanObject's "Key not found in metadata".
    const fields = formUtils.metadataQuery.data.fields || {};
    for (const [key, value] of Object.entries(objectQuery.data)) {
      if (!fields[key]) continue;
      formMethods.setValue(key, value, { shouldValidate: true });
    }
  }, [objectQuery.data, formUtils.metadataQuery.data, formMethods]);

  const updateMutation = useMutation({
    mutationFn: (data) => {
      try {
        const cleanedData = client.cleanObject(formUtils.metadataQuery.data, data);
        return client.update(type, id, cleanedData);
      } catch (error) {
        if (error.errors) formUtils.setErrors(error.errors);
        throw error;
      }
    },
    onSuccess: (data) => {
      invalidateModel(queryClient, type, { viewModel: data?.model });
      showSuccessToastWithLink('updated', data, router.push);
      router.push(nextUrl || url(data.id));
    },
    onError: (error) => {
      const detail = error.message ? `: ${error.message}` : '';
      toast.error(`Failed to update item${detail}`);
      handleMutationError(error);
    },
  });

  const handleSubmit = formMethods.handleSubmit((data) => updateMutation.mutateAsync(data));

  return {
    ...formUtils,
    objectQuery,
    updateMutation,
    handleSubmit,
    FormProvider,
    isLoading: formUtils.isLoading || objectQuery.isPending,
    isError: formUtils.isError || objectQuery.isError,
    errorMessage: formUtils.errorMessage || objectQuery.error?.message,
  };
}

export function useDeleteForm({ type, id }) {
  const [searchParams] = useSearchParams();
  const nextUrl = searchParams.get('next');

  const formUtils = useCrudForm({ type, id });
  const { client, router } = formUtils;
  const queryClient = useQueryClient();

  const objectQuery = useQuery({
    queryKey: ['detail', type, id],
    queryFn: () => client.retrieve(type, id),
  });

  const deleteMutation = useMutation({
    mutationFn: () => client.delete(type, id),
    onSuccess: () => {
      invalidateModel(queryClient, type, { viewModel: objectQuery.data?.model });
      const label = objectQuery.data?.label || objectQuery.data?._label || 'Item';
      toast.success(`${label} deleted successfully`);
      router.push(nextUrl || `/${type}/`);
    },
    onError: (error) => {
      const detail = error.message ? `: ${error.message}` : '';
      toast.error(`Failed to delete item${detail}`);
      formUtils.handleMutationError(error);
    },
  });

  const handleDelete = () => deleteMutation.mutateAsync();

  return {
    ...formUtils,
    objectQuery,
    deleteMutation,
    handleDelete,
    isLoading: formUtils.isLoading || objectQuery.isPending || deleteMutation.isPending,
    isError: formUtils.isError || objectQuery.isError,
    errorMessage: formUtils.errorMessage || objectQuery.error?.message,
  };
}

export function useMetadata(modelType) {
  const { data: metadata, isLoading: isMetadataLoading, error: metadataError } = useQuery({
    queryKey: ['metadata', modelType],
    queryFn: () => fetchMetadata(modelType),
    enabled: !!modelType,
  });

  return { metadata, isMetadataLoading, metadataError };
}
