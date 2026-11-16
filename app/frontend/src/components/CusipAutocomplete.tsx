import { useState, useRef, useEffect, useMemo, useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { Input } from "@/components/ui/input";

interface CusipAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onValidChange?: (valid: boolean) => void;
  className?: string;
  id?: string;
  placeholder?: string;
}

export default function CusipAutocomplete({
  value,
  onChange,
  onValidChange,
  className = "",
  id,
  placeholder = "e.g. 594918104",
}: CusipAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const listboxId = useId();

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const allCusips = useMemo(
    () => stocks.map((s) => ({ cusip: s.cusip, ticker: s.ticker, company: s.company })),
    [stocks],
  );

  const isValid = useMemo(() => allCusips.some((c) => c.cusip === value), [allCusips, value]);

  // Stabilise the parent's callback identity via a ref. Without this, an inline
  // arrow at the call site (e.g. `onValidChange={(v) => setFieldValid(...)}`)
  // changes identity every render, the effect dep array sees it as new, fires
  // again, triggers setState in the parent, re-renders us, ad infinitum —
  // React doesn't flag it as "max update depth" because the dep technically
  // changed each tick. Symptom: main thread saturated, no console error, the
  // app appears frozen.
  const onValidChangeRef = useRef(onValidChange);
  useEffect(() => {
    onValidChangeRef.current = onValidChange;
  });

  useEffect(() => {
    onValidChangeRef.current?.(isValid);
  }, [isValid]);

  const suggestions = useMemo(() => {
    if (!value || value.length < 2) return [];
    const q = value.toUpperCase();
    return allCusips
      .filter(
        (c) =>
          c.cusip.includes(q) ||
          c.ticker.toUpperCase().includes(q) ||
          c.company.toUpperCase().includes(q),
      )
      .sort((a, b) => {
        const aStarts = a.cusip.startsWith(q) ? 0 : 1;
        const bStarts = b.cusip.startsWith(q) ? 0 : 1;
        if (aStarts !== bStarts) return aStarts - bStarts;
        return a.cusip.localeCompare(b.cusip);
      })
      .slice(0, 8);
  }, [value, allCusips]);

  // Reset highlight whenever the suggestion list changes.
  // React-idiomatic "adjusting state on prop change" pattern; safe to call setState
  // during render — React re-runs immediately without painting.
  // See https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const suggestionsKey = suggestions.map((s) => s.cusip).join("|");
  const [lastSuggestionsKey, setLastSuggestionsKey] = useState(suggestionsKey);
  if (lastSuggestionsKey !== suggestionsKey) {
    setLastSuggestionsKey(suggestionsKey);
    setHighlightIdx(-1);
  }

  const selectCusip = (cusip: string) => {
    onChange(cusip);
    setOpen(false);
  };

  const expanded = open && suggestions.length > 0;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (
      e.key === "Enter" &&
      !e.nativeEvent.isComposing &&
      expanded &&
      highlightIdx >= 0 &&
      suggestions[highlightIdx]
    ) {
      e.preventDefault();
      selectCusip(suggestions[highlightIdx].cusip);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showError = value.length >= 3 && !isValid && !open;
  const errorId = `${listboxId}-error`;

  return (
    <div className="relative">
      <Input
        id={id}
        role="combobox"
        aria-expanded={expanded}
        aria-controls={expanded ? listboxId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={
          expanded && highlightIdx >= 0 ? `${listboxId}-${highlightIdx}` : undefined
        }
        aria-invalid={showError || undefined}
        aria-describedby={showError ? errorId : undefined}
        autoComplete="off"
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        value={value}
        onChange={(e) => {
          onChange(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => value.length >= 2 && setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        size={9}
        className={`${className} font-mono uppercase ${showError ? "border-destructive" : ""}`}
      />
      {showError && (
        <p id={errorId} role="alert" className="text-[11px] text-destructive mt-0.5 absolute">
          CUSIP not found
        </p>
      )}
      {expanded && (
        <div
          id={listboxId}
          role="listbox"
          aria-label="CUSIP suggestions"
          className="absolute z-50 mt-1 w-72 overflow-hidden rounded-md border border-border bg-popover shadow-md"
        >
          {suggestions.map((item, idx) => {
            const isHighlighted = idx === highlightIdx;
            return (
              <div
                key={item.cusip}
                id={`${listboxId}-${idx}`}
                role="option"
                aria-selected={isHighlighted}
                tabIndex={-1}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer transition-colors ${
                  isHighlighted ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                }`}
                // Keeps focus in the input so the blur-close does not swallow the pick.
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectCusip(item.cusip);
                }}
                onMouseEnter={() => setHighlightIdx(idx)}
              >
                <span className="font-mono font-medium w-24 shrink-0 text-xs">{item.cusip}</span>
                <span className="font-mono w-12 shrink-0 text-xs">{item.ticker}</span>
                <span
                  className={`truncate text-xs ${isHighlighted ? "text-primary-foreground/70" : "text-muted-foreground"}`}
                >
                  {item.company}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
