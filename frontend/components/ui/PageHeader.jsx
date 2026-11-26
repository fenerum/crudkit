// The top of a page: title and count, actions on the right, then one bar of
// tabs with tools (search) at its right end. Breaks out of the content gutters itself.
export default function PageHeader({ title, count = null, actions = null, tabs = null, toolbar = null }) {
  return (
    <div className="ck-page-header">
      <div className="ck-page-title-row">
        <div className="ck-page-title-group">
          <h1 className="ck-page-title">{title}</h1>
          {count != null && <span className="ck-page-count">{count}</span>}
        </div>
        {actions && <div className="ck-page-actions">{actions}</div>}
      </div>
      {(tabs || toolbar) && (
        <div className="ck-view-bar">
          {tabs}
          {toolbar && <div className="ck-view-toolbar">{toolbar}</div>}
        </div>
      )}
    </div>
  );
}
