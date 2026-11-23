// The top of a list-style page: title and count, actions on the right, then
// optional tabs and a toolbar row. Breaks out of the content gutters itself.
export default function PageHeader({ title, count, actions, tabs, toolbar }) {
  return (
    <div className="ck-page-header">
      <div className="ck-page-title-row">
        <div className="ck-page-title-group">
          <h1 className="ck-page-title">{title}</h1>
          {count != null && <span className="ck-page-count">{count}</span>}
        </div>
        {actions && <div className="ck-page-actions">{actions}</div>}
      </div>
      {tabs}
      {toolbar && <div className="ck-view-toolbar">{toolbar}</div>}
    </div>
  );
}
