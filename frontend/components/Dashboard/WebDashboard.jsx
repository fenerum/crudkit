import React from 'react';
import { WidgetRenderer } from '@/components/Widgets';

export default function WebDashboard({ widgets, isLoadingWidgets, widgetsError }) {
  return (
    <div className="flex flex-col">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-fg-1 tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-fg-3">Today's snapshot across the workspace.</p>
        </div>
      </div>

      <div className="eyebrow mb-3">Widgets</div>

      {isLoadingWidgets ? (
        <p className="text-sm text-fg-3">Loading widgets…</p>
      ) : widgetsError ? (
        <p className="text-sm text-danger">Error loading widgets: {widgetsError.message}</p>
      ) : widgets && widgets.length > 0 ? (
        <div className="widget-grid">
          {widgets.map((widget, index) => {
            const widgetWidth = widget.width || 1;
            return (
              <div
                key={index}
                className={`widget-width-${widgetWidth}`}
                style={{ gridColumn: `span ${widgetWidth}` }}
              >
                <WidgetRenderer
                  type={widget.type}
                  data={widget.data}
                  title={widget.title}
                  width={widget.width}
                  containerClassName="widget-item"
                />
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-sm text-fg-3">No widgets configured yet.</p>
      )}
    </div>
  );
}
