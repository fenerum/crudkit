import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Icon } from "./ui";
import { usePageSearch } from "./ui/PageSearchContext";

export default function PageSearch({ placeholder = "Search this view…" }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const urlQ = searchParams.get("q") || "";

  const [value, setValue] = useState(urlQ);
  const inputRef = useRef(null);
  const { registerInput } = usePageSearch();

  useEffect(() => {
    setValue(urlQ);
  }, [urlQ]);

  useEffect(() => {
    const unregister = registerInput(inputRef);
    return unregister;
  }, [registerInput]);

  const pushUrl = useCallback((nextQ) => {
    const next = new URLSearchParams(searchParams);
    if (nextQ) next.set("q", nextQ);
    else next.delete("q");
    next.delete("page");
    const qs = next.toString();
    navigate(qs ? `${pathname}?${qs}` : pathname, { replace: true });
  }, [searchParams, pathname, navigate]);

  const debounceRef = useRef(null);
  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);
  const onChange = (e) => {
    const v = e.target.value;
    setValue(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => pushUrl(v), 250);
  };

  const onClear = () => {
    setValue("");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    pushUrl("");
    inputRef.current?.focus();
  };

  return (
    <div className="relative flex items-center">
      <span className="absolute left-2 inline-flex items-center pointer-events-none text-fg-3">
        <Icon name="search" size={12} color="currentColor" />
      </span>
      <input
        ref={inputRef}
        type="search"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="ck-input pl-7 pr-7"
        style={{ width: 220, height: 26, fontSize: 12 }}
        aria-label="Search this view"
      />
      {value && (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-1.5 inline-flex items-center justify-center w-4 h-4 rounded text-fg-3 hover:text-fg-1 hover:bg-bg-3"
          aria-label="Clear search"
        >
          <Icon name="x" size={11} color="currentColor" />
        </button>
      )}
    </div>
  );
}
