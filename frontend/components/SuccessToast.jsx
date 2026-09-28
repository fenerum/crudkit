import { useState } from 'react';
import { toast } from 'react-toastify';
import CrudKitAPIClient from '../data/api';
import { formatApiError } from '../utils/apiErrors';
import { Button } from './ui';

function SuccessMessage({ label, verb, onOpen, changeSet, onUndone, closeToast }) {
  const [undoing, setUndoing] = useState(false);

  const undo = async () => {
    setUndoing(true);
    try {
      const result = await new CrudKitAPIClient().revertChangeSet(changeSet);
      closeToast();
      if (result.conflicts) {
        toast.error(`Not undone: ${label} has changed since. You can still revert it from History.`);
        return;
      }
      toast.success(`Undone: ${label}`);
      onUndone?.();
    } catch (error) {
      setUndoing(false);
      toast.error(`Undo failed: ${formatApiError(error)}`);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button type="button" onClick={onOpen} className="flex-1 text-left bg-transparent border-0 p-0 cursor-pointer">
        <span className="underline font-semibold">{label}</span>
        <span> {verb} successfully</span>
      </button>
      {changeSet && (
        <Button size="sm" icon="rotate-ccw" onClick={undo} disabled={undoing}>
          Undo
        </Button>
      )}
    </div>
  );
}

// A success toast linking to the record, with an Undo button when the write
// reported its change set.
export function showSuccessToast({ label, verb, onOpen, changeSet, onUndone }) {
  toast.success(
    ({ closeToast }) => (
      <SuccessMessage
        label={label}
        verb={verb}
        onOpen={onOpen}
        changeSet={changeSet}
        onUndone={onUndone}
        closeToast={closeToast}
      />
    ),
    { closeOnClick: false },
  );
}
