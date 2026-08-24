
/**
 * Web-specific widget component for displaying embedded Metabase questions
 * @param {Object} props - Component props
 * @param {Object} props.data - Widget data containing the metabase URL
 * @param {string} props.data.url - The embedded Metabase question URL
 * @param {string} props.title - The title of the widget
 */
const MetabaseEmbeddedQuestionWidget = ({ data, title }) => {
  // If no URL is provided, return empty div
  if (!data || !data.url) {
    return (
      <div className="h-[300px] w-full rounded-lg bg-bg-1 border border-border-1">
        <div className="p-3 border-b border-border-1 bg-bg-2">
          <h3 className="text-sm font-semibold text-fg-1">{title || 'Metabase Widget'}</h3>
        </div>
        <div className="p-4 text-fg-3 text-sm">No data available</div>
      </div>
    );
  }

  return (
    <div className="h-[350px] w-full rounded-lg overflow-hidden bg-bg-1 border border-border-1 flex flex-col">
      <div className="p-3 border-b border-border-1 bg-bg-2">
        <h3 className="text-sm font-semibold text-fg-1">{title || 'Metabase Widget'}</h3>
      </div>
      <div className="flex-1">
        <iframe
          src={data.url}
          title={title || "Metabase Question"}
          frameBorder="0"
          className="w-full h-full"
        />
      </div>
    </div>
  );
};

export default MetabaseEmbeddedQuestionWidget;