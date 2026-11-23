// A saved view as one person may see it. The metadata leaves out the fields
// their roles hide, so a shared view drops those columns. A board or chart
// that needs a hidden field to group or plot by falls back to a plain list.

const BOARD_LAYOUTS: Record<string, string[]> = {
  kanban: ['group_by'],
  swimlane: ['group_by', 'pivot_by'],
};

export function visibleView(view: any, metadata: any) {
  if (!view || !metadata?.fields) return view;
  const known = (name: string | null | undefined) => !name || Boolean(metadata.fields[name.split('__')[0]]);
  const fields = (view.fields || []).filter((name: string) => known(name));
  const dropped = ['group_by', 'pivot_by', 'aggregate_by'].filter((key) => !known(view[key]));
  if (fields.length === (view.fields || []).length && dropped.length === 0) return view;

  const next = { ...view, fields };
  for (const key of dropped) next[key] = null;
  if (dropped.includes('aggregate_by')) next.aggregate_type = null;
  const needs = BOARD_LAYOUTS[view.layout] || [];
  if (needs.some((key) => dropped.includes(key)) || (view.layout === 'quadrant' && fields.length < 2)) {
    next.layout = 'list';
  }
  return next;
}
