import { Link } from "react-router-dom";
import { useBreadcrumbs } from "../hooks/useBreadcrumbs";

export default function Breadcrumbs() {
  const { crumbs } = useBreadcrumbs();

  return crumbs.map((crumb, index) => {
    const isLast = index === crumbs.length - 1;
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
            {crumb.text}
          </Link>
        </div>
      </li>
    );
  });
}
