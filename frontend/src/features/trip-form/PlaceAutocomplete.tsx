import clsx from 'clsx';
import { useEffect, useId, useRef, useState } from 'react';
import { useGeocode } from '../../api/queries';
import type { Place } from '../../api/types';

const DEBOUNCE_MS = 250;

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

interface Props {
  label: string;
  value: Place | null;
  onChange: (place: Place | null) => void;
  error?: string;
  placeholder?: string;
  name: string;
}

/** ARIA 1.2 combobox with a listbox popup; keyboard: ↑/↓, Enter, Escape. */
export function PlaceAutocomplete({ label, value, onChange, error, placeholder, name }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const errorId = `${id}-error`;
  const [text, setText] = useState(value?.label ?? '');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const query = useDebounced(text, DEBOUNCE_MS);
  const typing = !value || value.label !== text;
  const { data, isFetching, isError } = useGeocode(typing ? query : '');
  const options = typing ? (data ?? []) : [];
  const showList = open && typing && query.trim().length >= 3;

  useEffect(() => {
    setText(value?.label ?? '');
  }, [value]);

  useEffect(() => setActive(-1), [data]);

  const choose = (place: Place) => {
    onChange(place);
    setText(place.label);
    setOpen(false);
  };

  return (
    <div className="relative">
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300"
      >
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        name={name}
        type="text"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        autoComplete="off"
        placeholder={placeholder}
        value={text}
        className={clsx('field', error && 'field-error')}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
          if (value) onChange(null);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setOpen(true);
            setActive((i) => Math.min(options.length - 1, i + 1));
          } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActive((i) => Math.max(0, i - 1));
          } else if (e.key === 'Enter' && showList) {
            const pick = options[active >= 0 ? active : 0];
            if (pick) {
              e.preventDefault();
              choose(pick);
            }
          } else if (e.key === 'Escape') {
            setOpen(false);
          }
        }}
      />
      {showList && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-card border border-slate-200 bg-white py-1 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          {options.map((place, i) => (
            <li
              key={`${place.label}-${place.lat}-${place.lon}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={clsx(
                'cursor-pointer px-3 py-2',
                i === active
                  ? 'bg-accent/10 text-accent'
                  : 'hover:bg-slate-100 dark:hover:bg-slate-800',
              )}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(place);
              }}
              onMouseEnter={() => setActive(i)}
            >
              {place.label}
            </li>
          ))}
          {!isFetching && !isError && options.length === 0 && (
            <li className="px-3 py-2 text-slate-500" aria-live="polite">
              No matches
            </li>
          )}
          {isFetching && options.length === 0 && (
            <li className="px-3 py-2 text-slate-500" aria-live="polite">
              Searching…
            </li>
          )}
          {isError && (
            <li className="px-3 py-2 text-red-600" role="alert">
              Address search is unavailable.
            </li>
          )}
        </ul>
      )}
      {error && (
        <p id={errorId} className="mt-1 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
