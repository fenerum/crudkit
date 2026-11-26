import { Link } from "react-router-dom";
import { useBreadcrumbs } from "../hooks/useBreadcrumbs";

export default function Breadcrumbs() {
  const { crumbs } = useBreadcrumbs();

  // A list's views are tabs right after the trail, so the open view isn't a crumb.
  return crumbs.filter((crumb) => !crumb.viewId).map((crumb, index, shown) => {
    const isLast = index === shown.length - 1;
    return (
      <li key={index} data-breadcrumbs-title={isLast ? "true" : "false"}>
        <div className="flex items-center gap-2">
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
              "text-md truncate capitalize transition-colors duration-fast " +
              (isLast ? "text-fg-1 font-medium" : "text-fg-3 hover:text-fg-1")
            }
            aria-current={isLast ? "page" : undefined}
          >
            {crumb.text}
          </Link>
        </div>
      </li>
    );
  });
}
