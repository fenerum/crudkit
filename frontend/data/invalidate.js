// Standardised React-Query invalidation for CRUD-shaped data.
//
// Convention used across the app:
//   ['list',   model, ...rest]   list/index queries (incl. sidebar's VIW menu)
//   ['detail', model, id]        single-object queries
//   ['history', model, id]       an object's change history
//   ['views',  model]            view configs for a target model
//   ['metadata', model]          model metadata
//   ['layouts',  model]          layout configs
//
// `invalidateModel(qc, model)` invalidates every query keyed off `model` so that
// any list, detail, or view-config that depends on it refetches.
//
// Saving a `VIW` always also invalidates `views` for its target model — a new
// or updated view should make the target model's list page pick it up too.
export function invalidateModel(qc, model, options = {}) {
  if (!qc || !model) return;
  qc.invalidateQueries({ queryKey: ['list', model] });
  qc.invalidateQueries({ queryKey: ['detail', model] });
  qc.invalidateQueries({ queryKey: ['views', model] });
  qc.invalidateQueries({ queryKey: ['history', model] });

  const related = options.relatedModels || [];
  if (model === 'VIW' && options.viewModel) related.push(options.viewModel);
  related.forEach((m) => {
    qc.invalidateQueries({ queryKey: ['list', m] });
    qc.invalidateQueries({ queryKey: ['views', m] });
  });
}

// After a change made outside the page's own forms (e.g. a confirmed assistant
// proposal): refresh the object's model and every inline list, count and feed,
// which are keyed by their own model rather than the parent's.
export function invalidateObject(qc, ckId) {
  if (!qc || !ckId) return;
  invalidateModel(qc, ckId.slice(0, 3));
  ['inline-list', 'inline-count', 'inline-feed'].forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
}

// After an undo, which may touch any number of records of any model.
export function invalidateRecords(qc) {
  if (!qc) return;
  ['list', 'detail', 'history', 'inline-list', 'inline-count', 'inline-feed'].forEach((key) =>
    qc.invalidateQueries({ queryKey: [key] }),
  );
}
