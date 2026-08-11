import * as React from "react";
import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CrudKitAPIClient from "../data/api";
import { groupBy } from "../utils/groupby";
import { detail as detailRegex } from "../utils/urls";
import { useHotkeys } from "react-hotkeys-hook";
import { getIdPrefix, isObjectTypeCode } from "../utils/crudkit";

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

export default function Search() {
  const [focused, setFocused] = useState(false);
  const [rawQuery, setRawQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const query = rawQuery.toLowerCase().replace(/^[#>]/, '');
  const navigate = useNavigate();

  const [debounceTimeout, setDebounceTimeout] = useState(null);
  const client = new CrudKitAPIClient();
  const searchRef = useRef(null);
  const resultsRef = useRef([]);

  useHotkeys('/', (event) => {
    event.preventDefault();
    searchRef.current?.focus();
  });

  useHotkeys('down', (event) => {
    if (focused && resultsRef.current.length > 0) {
      event.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, resultsRef.current.length - 1));
    }
  });

  useHotkeys('up', (event) => {
    if (focused && resultsRef.current.length > 0) {
      event.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, -1));
    }
  });

  useHotkeys('enter', (event) => {
    if (focused && selectedIndex >= 0 && selectedIndex < resultsRef.current.length) {
      event.preventDefault();
      handleSelectItem(resultsRef.current[selectedIndex].id);
    }
  });

  React.useEffect(() => {
    if (results.length > 0) {
      const flatResults = [];
      Object.entries(groupBy(results, (object) => getIdPrefix(object.id) || 'N/A', (object) => object))
        .forEach(([_, groupResults]) => {
          groupResults.forEach(result => flatResults.push(result));
        });
      resultsRef.current = flatResults;
      setSelectedIndex(-1);
    } else {
      resultsRef.current = [];
      setSelectedIndex(-1);
    }
  }, [results]);

  const [isTypeCode, setIsTypeCode] = useState(false);
  const [objectTypeMatch, setObjectTypeMatch] = useState(null);
  const [directMatch, setDirectMatch] = useState(null);

  const debouncedLoadOptions = useCallback((inputValue) => {
    if (debounceTimeout) clearTimeout(debounceTimeout);

    setDirectMatch(null);
    setObjectTypeMatch(null);
    setIsTypeCode(false);

    const timeout = setTimeout(async () => {
      if (inputValue.trim().length > 0) {
        try {
          if (detailRegex.test(inputValue.toUpperCase())) {
            const id = inputValue.toUpperCase();
            const modelType = id.slice(0, 3);
            try {
              const response = await client.retrieve(modelType, id);
              if (response) {
                const result = {
                  id,
                  label: response.label || response.object_repr || id,
                  object_images: response.object_images || [],
                  type: modelType,
                  object_data: response,
                };
                setDirectMatch(result);
                setResults([result]);
                return;
              }
            } catch (error) {
              console.error("Object fetch error:", error);
            }
          } else if (isObjectTypeCode(inputValue.toUpperCase())) {
            setIsTypeCode(true);
            const typeCode = inputValue.toUpperCase();
            try {
              const metadata = await client.metadata(typeCode);
              if (metadata) {
                setObjectTypeMatch({
                  type: typeCode,
                  name: metadata.verbose_name_plural || metadata.verbose_name || typeCode,
                  isDirectObject: false,
                });
                setResults([]);
                return;
              }
            } catch (error) {
              console.error("Object type metadata error:", error);
            }
          }

          const response = await client.search(inputValue);
          setResults(response.results || []);
        } catch (error) {
          console.error("Search error:", error);
          setResults([]);
        }
      } else {
        setResults([]);
      }
    }, 500);

    setDebounceTimeout(timeout);
  }, [debounceTimeout]);

  const handleSelectItem = (id) => {
    navigate(`/${id}`);
    setRawQuery('');
    setResults([]);
    setFocused(false);
  };

  const handleViewAll = (type, q) => {
    const qs = q ? `?q=${encodeURIComponent(q)}` : '';
    navigate(`/${type}${qs}`);
    setRawQuery('');
    setResults([]);
    setFocused(false);
  };

  return (
    <div className="relative w-full">
      <input
        className="block h-full w-full border-0 bg-transparent py-0 pl-8 pr-0 text-fg-1 placeholder:text-fg-3 focus:ring-0 sm:text-sm font-sans"
        placeholder="Search… (Press / to focus)"
        value={rawQuery}
        onChange={(event) => {
          setRawQuery(event.target.value);
          debouncedLoadOptions(event.target.value);
        }}
        ref={searchRef}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setTimeout(() => {
            setFocused(false);
            setResults([]);
          }, 150);
        }}
      />

      {focused && (
        <div className="absolute left-0 right-0 z-10 mt-1 overflow-hidden rounded-md bg-bg-4 border border-border-2 shadow-modal">
          {(directMatch || objectTypeMatch) && (
            <div className="py-2 border-b border-border-1">
              <div className="px-4 py-1 eyebrow">Quick access</div>
              <ul>
                {directMatch && (
                  <li
                    className="relative cursor-pointer select-none py-2 px-4 border-l-2 hover:bg-bg-5"
                    style={{ borderLeftColor: 'var(--success)' }}
                    onClick={() => handleSelectItem(directMatch.id)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <span className="font-medium text-fg-1">{directMatch.label}</span>
                        <p className="text-xs text-fg-3 font-mono truncate">
                          {directMatch.id} · Open this {directMatch.type.toLowerCase()}
                        </p>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-fg-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </li>
                )}

                {objectTypeMatch && !directMatch && (
                  <li
                    className="relative cursor-pointer select-none py-2 px-4 border-l-2 hover:bg-bg-5"
                    style={{ borderLeftColor: 'var(--primary-400)' }}
                    onClick={() => handleViewAll(objectTypeMatch.type, "")}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <span className="font-medium text-fg-1">{objectTypeMatch.name}</span>
                        <p className="text-xs text-fg-3 truncate">
                          View all {objectTypeMatch.name.toLowerCase()}
                        </p>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-fg-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </li>
                )}
              </ul>
            </div>
          )}

          {results.length > 0 && (
            <div className="divide-y divide-border-1">
              {Object.entries(groupBy(results, (object) => getIdPrefix(object.id) || 'N/A', (object) => object)).map(([key, groupResults]) => (
                <div key={key} className="py-2">
                  <div className="px-4 py-1 flex justify-between items-center">
                    <span className="eyebrow">{key}</span>
                    <button
                      className="text-xs text-primary-300 hover:text-primary-200"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleViewAll(key, query);
                      }}
                    >
                      Show all
                    </button>
                  </div>

                  <ul>
                    {groupResults.map((obj) => {
                      const overallIndex = resultsRef.current.findIndex(r => r.id === obj.id);
                      const isSelected = overallIndex === selectedIndex;
                      return (
                        <li
                          key={obj.id}
                          className={classNames(
                            "relative cursor-pointer select-none py-2 px-4 hover:bg-bg-5",
                            isSelected ? "bg-bg-5" : ""
                          )}
                          onClick={() => handleSelectItem(obj.id)}
                          onMouseEnter={() => setSelectedIndex(overallIndex)}
                        >
                          <div className="flex items-center gap-3">
                            {obj.object_images && obj.object_images.length > 0 && (
                              <img src={obj.object_images[0]} alt="" className="h-5 w-5 flex-shrink-0 rounded-full" />
                            )}
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm text-fg-1">{obj.label}</div>
                              <div className="text-2xs text-fg-3 font-mono">{obj.id}</div>
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}

          {rawQuery === '?' && (
            <div className="px-6 py-8 text-center">
              <p className="font-semibold text-fg-1">Help with searching</p>
              <p className="mt-2 text-sm text-fg-3">
                Use this tool to quickly search across the platform. Type prefixes like
                <span className="ck-kbd mx-1">CMP:</span> or <span className="ck-kbd mx-1">OPP:</span>
                to limit results to specific types.
              </p>
            </div>
          )}

          {query !== '' && rawQuery !== '?' && results.length === 0 && (
            <div className="px-6 py-8 text-center">
              <p className="font-semibold text-fg-1">No results found</p>
              <p className="mt-2 text-sm text-fg-3">
                We couldn't find anything with that term. Please try again.
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 bg-bg-3 px-4 py-2.5 text-xs text-fg-3 border-t border-border-1">
            <span>Type</span>
            {['CMP:', 'OPP:', 'CSE:'].map((text) => (
              <kbd key={text} className="ck-kbd">{text}</kbd>
            ))}
            <span>for specific types,</span>
            <kbd className="ck-kbd">↑</kbd>
            <kbd className="ck-kbd">↓</kbd>
            <span>to navigate</span>
            <kbd className="ck-kbd">↵</kbd>
            <span>to select</span>
          </div>
        </div>
      )}
    </div>
  );
}
