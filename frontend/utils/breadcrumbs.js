// Build the breadcrumb trail for a given pathname.
//
// Returns objects of the shape `{ path, text, modelType? }`. `modelType` is
// set on the model-level crumb so the consumer can swap in a verbose label
// (e.g. "Companies") once metadata loads.

import { capitalize } from "./urls";

const SPECIAL_ROUTES = {
  "all-objects": "All Objects",
  profile: "Profile",
  inbox: "Inbox",
  search: "Search",
};

export function generateBreadcrumbs(pathname, _params = {}) {
  const crumbs = [];
  if (!pathname) return crumbs;

  const pathParts = pathname.split("/").filter(Boolean);
  if (pathParts.length === 0) return crumbs;

  const firstPart = pathParts[0];

  if (SPECIAL_ROUTES[firstPart]) {
    crumbs.push({ path: `/${firstPart}`, text: SPECIAL_ROUTES[firstPart] });
    return crumbs;
  }

  // CrudKit IDs follow `XXX` (list/model code) or `XXX123` (object id).
  const detailMatch = firstPart.match(/^([A-Z]{3})(\d+)$/);
  const listMatch = firstPart.match(/^([A-Z]{3})$/);

  let modelType = null;
  let objectId = null;
  if (detailMatch) {
    modelType = detailMatch[1];
    objectId = firstPart;
  } else if (listMatch) {
    modelType = firstPart;
  } else {
    crumbs.push({ path: `/${firstPart}`, text: capitalize(firstPart) });
    return crumbs;
  }

  // Model-level crumb. The text is the canonical fallback; the consumer can
  // upgrade it to verbose_name_plural once metadata is available.
  crumbs.push({
    path: `/${modelType}`,
    text: capitalize(modelType),
    modelType,
  });

  if (objectId) {
    crumbs.push({ path: `/${objectId}`, text: objectId });
  }

  const action = pathParts[1];
  if (action === "edit") {
    crumbs.push({ path: `/${objectId || modelType}/edit`, text: "Edit" });
  } else if (action === "delete") {
    crumbs.push({ path: `/${objectId || modelType}/delete`, text: "Delete" });
  } else if (action === "create") {
    crumbs.push({ path: `/${modelType}/create`, text: "Create" });
  } else if (action === "merge") {
    crumbs.push({ path: `/${modelType}/merge`, text: "Merge" });
  } else if (action === "VIW" && pathParts.length > 2) {
    const viewId = pathParts[2];
    crumbs.push({
      path: `/${modelType}/VIW/${viewId}`,
      text: viewId,
      viewId,
    });
  }

  return crumbs;
}
