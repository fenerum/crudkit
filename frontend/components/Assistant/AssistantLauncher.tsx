import { useState } from 'react';
import AssistantWindow from './AssistantWindow';
import { Icon } from '../ui';
import { useAuth } from '../../context/AuthContext';

type Props = {
  objectType: string;
  objectId: string;
};

export default function AssistantLauncher({ objectType, objectId }: Props) {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const name = user?.assistant?.name || 'Assistant';

  if (!user) return null;

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-4 right-4 z-30 rounded-full shadow-lg bg-primary-400 hover:bg-primary-500 text-white px-4 py-3 flex items-center gap-2 text-sm font-semibold"
          aria-label={`Open ${name}`}
        >
          <Icon name="sparkles" size={16} color="currentColor" />
          <span>{name}</span>
        </button>
      )}
      {open && (
        <AssistantWindow objectType={objectType} objectId={objectId} onClose={() => setOpen(false)} />
      )}
    </>
  );
}
