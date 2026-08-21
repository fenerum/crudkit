// Resolve a workspace's ordered list of view CK-IDs (e.g. ["VIW3", "VIW1"])
// against the fetched view objects. Missing/deleted ids and duplicates are
// skipped so a stale workspace degrades to fewer tabs instead of crashing.
export function resolveWorkspaceViews(workspace, allViews) {
  if (!workspace || !Array.isArray(workspace.views) || !Array.isArray(allViews)) {
    return [];
  }
  const byId = new Map(allViews.map((v) => [String(v.id), v]));
  const seen = new Set();
  const resolved = [];
  for (const id of workspace.views) {
    const key = String(id);
    if (seen.has(key)) continue;
    seen.add(key);
    const view = byId.get(key);
    if (view) resolved.push(view);
  }
  return resolved;
}
