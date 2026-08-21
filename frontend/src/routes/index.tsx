import { useQuery } from '@tanstack/react-query';
import CrudKitAPIClient from '../../data/api';
import Dashboard from '../../components/Dashboard';
import { useMenuViews } from '../../hooks/useMenuViews';

export default function Index() {
  const client = new CrudKitAPIClient();

  const { isPending, error, items: allViews } = useMenuViews();
  const rootViews = allViews.filter((v) => v.show_in_menu);

  const {
    isPending: isPendingWidgets,
    error: widgetsError,
    data: widgets,
  } = useQuery({
    queryKey: ['widgets'],
    queryFn: async () => {
      const response = await client.httpGet('api/v1/widgets/');
      return await response.json();
    },
  });

  return (
    <Dashboard
      rootViews={rootViews}
      widgets={widgets}
      isLoading={isPending}
      isLoadingWidgets={isPendingWidgets}
      error={error}
      widgetsError={widgetsError}
    />
  );
}
