import * as React from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import CrudKitAPIClient from "../data/api";
import { generateBreadcrumbs } from "../utils/breadcrumbs";

const apiClient = new CrudKitAPIClient();

export default function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = generateBreadcrumbs(pathname);

  // Pick up the verbose plural for the model-level crumb if there is one.
  // react-query caches by ['metadata', type] so this hits the same entry the
  // List/Detail pages already populate.
  const modelType = crumbs.find((c) => c.modelType)?.modelType;
  const { data: metadata } = useQuery({
    queryKey: ["metadata", modelType],
    queryFn: () => apiClient.metadata(modelType),
    enabled: !!modelType,
    staleTime: 60_000,
  });

  // If a `/VIW/<id>` segment is in the trail, fetch the view so we can show
  // its `name` instead of the raw id. Same react-query cache as List/Detail.
  const viewId = crumbs.find((c) => c.viewId)?.viewId;
  const { data: view } = useQuery({
    queryKey: ["detail", "VIW", viewId],
    queryFn: () => apiClient.retrieve("VIW", viewId),
    enabled: !!viewId,
    staleTime: 60_000,
  });

  return crumbs.map((crumb, index) => {
    const isLast = index === crumbs.length - 1;
    let text = crumb.text;
    if (crumb.modelType && metadata?.verbose_name_plural) text = metadata.verbose_name_plural;
    if (crumb.viewId && view?.name) text = view.name;
    return (
      <li key={index} data-breadcrumbs-title={isLast ? "true" : "false"}>
        <div className="flex items-center gap-1.5">
          <svg
            className="h-3 w-3 flex-shrink-0 text-fg-4"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth="1.5"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <Link
            to={crumb.path}
            className={
              "text-sm truncate capitalize transition-colors duration-fast " +
              (isLast ? "text-fg-1 font-semibold" : "text-fg-2 hover:text-fg-1")
            }
            aria-current={isLast ? "page" : undefined}
          >
            {text}
          </Link>
        </div>
      </li>
    );
  });
}
