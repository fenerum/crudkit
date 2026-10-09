import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchMetadata, fetchObject } from "../data/api";
import { generateBreadcrumbs } from "../utils/breadcrumbs";

// Breadcrumb trail with display text resolved: the model crumb gets the
// verbose plural and a `/VIW/<id>` crumb gets the view's name once loaded.
// Queries share the react-query cache entries the List/Detail pages populate.
export function useBreadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = generateBreadcrumbs(pathname);

  const modelType = crumbs.find((c) => c.modelType)?.modelType;
  const { data: metadata } = useQuery({
    queryKey: ["metadata", modelType],
    queryFn: () => fetchMetadata(modelType),
    enabled: !!modelType,
    staleTime: 60_000,
  });

  const viewId = crumbs.find((c) => c.viewId)?.viewId;
  const { data: view } = useQuery({
    queryKey: ["detail", "VIW", viewId],
    queryFn: () => fetchObject("VIW", viewId),
    enabled: !!viewId,
    staleTime: 60_000,
  });

  const resolved = crumbs.map((crumb) => {
    if (crumb.modelType && metadata?.verbose_name_plural) return { ...crumb, text: metadata.verbose_name_plural };
    if (crumb.viewId && view?.name) return { ...crumb, text: view.name };
    return crumb;
  });
  return { crumbs: resolved, view };
}
