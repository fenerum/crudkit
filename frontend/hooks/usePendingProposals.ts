import { useQuery } from '@tanstack/react-query';
import { fetchObjects } from '../data/api';
import { useRealtimeConnected } from '../data/realtime';
import { useAuth } from '../context/AuthContext';

// The signed-in user's proposals waiting for Confirm or Skip, from the
// assistant, MCP clients and agents. Shared by the Inbox tab and its nav badge.
export function usePendingProposals() {
  const { user } = useAuth();
  const enabled = !!user?.assistant?.proposals;
  const realtimeConnected = useRealtimeConnected();
  const query = useQuery({
    queryKey: ['list', 'ASP', { status: 'pending' }],
    queryFn: () => fetchObjects('ASP', { status: 'pending', page_size: 50 }),
    enabled,
    refetchInterval: realtimeConnected ? false : 60_000,
  });
  return { enabled, ...query };
}
