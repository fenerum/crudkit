import { useQuery } from '@tanstack/react-query';
import CrudKitAPIClient from '../../data/api';
import Dashboard from '../../components/Dashboard';

export default function Index() {
  const client = new CrudKitAPIClient();

  const { isPending, error, data: viewsData } = useQuery({
    queryKey: ['rootViews'],
    queryFn: () => client.list('VIW', { show_in_menu: true }),
  });

  const rootViews = viewsData?.isPaginated ? viewsData.results : viewsData;

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
