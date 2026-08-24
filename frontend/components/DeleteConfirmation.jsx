import { Link, useNavigate } from "react-router-dom";
import ActionButton from "./ActionButton";
import { useHotkeys } from "react-hotkeys-hook";
import { Kbd } from "./ui";

export default function DeleteConfirmation({
  isLoading,
  isError,
  errorMessage,
  object,
  onDelete,
  onCancel,
  isPending = false
}) {
  const navigate = useNavigate();

  useHotkeys("escape", (e) => {
    if (!onCancel || isPending) return;
    e?.preventDefault?.();
    navigate(onCancel);
  });

  if (isLoading) {
    return <p>Loading...</p>;
  }

  if (isError) {
    return <p>Error: {errorMessage}</p>;
  }

  return (
    <div className="p-4 bg-bg-2 rounded-lg shadow max-w-md mx-auto mt-8">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-fg-1 mb-2">Confirm Delete</h2>
        <p className="text-fg-2">
          Are you sure you want to delete {object?.label || "this item"}? This action cannot be undone.
        </p>
      </div>

      {isPending && (
        <div className="mb-4">
          <svg className="animate-spin h-5 w-5 text-primary-300" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
          </svg>
        </div>
      )}

      <div className="flex flex-row justify-end items-center gap-4">
        <Link
          to={onCancel}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-fg-2 hover:text-fg-1"
        >
          Cancel
          <Kbd>esc</Kbd>
        </Link>

        <ActionButton
          text="Delete"
          color="red"
          onPress={onDelete}
        />
      </div>
    </div>
  );
}
