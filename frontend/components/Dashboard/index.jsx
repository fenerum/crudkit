import WebDashboard from './WebDashboard';

export default function Dashboard({
  rootViews,
  widgets,
  isLoading,
  isLoadingWidgets,
  error,
  widgetsError,
}) {
  return (
    <WebDashboard
      rootViews={rootViews}
      widgets={widgets}
      isLoading={isLoading}
      isLoadingWidgets={isLoadingWidgets}
      error={error}
      widgetsError={widgetsError}
    />
  );
}
