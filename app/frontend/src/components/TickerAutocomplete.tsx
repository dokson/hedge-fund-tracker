import { useState, useRef, useEffect, useMemo, useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { Input } from "@/components/ui/input";

interface TickerAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  onValidChange?: (valid: boolean) => void;
  className?: string;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  title?: string;
}

export default function TickerAutocomplete({
  value,
  onChange,
  onSubmit,
  onValidChange,
  className = "",
  id,
  placeholder = "NVDA",
  disabled = false,
  title,
}: TickerAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const listboxId = useId();

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const allTickers = useMemo(
    () => [...new Map(stocks.map((s) => [s.ticker, s.company])).entries()],
    [stocks],
  );

  const isValid = useMemo(() => allTickers.some(([t]) => t === value), [allTickers, value]);

  const onValidChangeRef = useRef(onValidChange);
  useEffect(() => {
    onValidChangeRef.current = onValidChange;
  });

  useEffect(() => {
    onValidChangeRef.current?.(isValid);
  }, [isValid]);

  const suggestions = useMemo(() => {
    if (!value || value.length < 1) return [];
    const q = value.toUpperCase();
    return allTickers
      .filter(([t, c]) => t.includes(q) || c.toUpperCase().includes(q))
      .sort((a, b) => {
        // Exact start match first
        const aStarts = a[0].startsWith(q) ? 0 : 1;
        const bStarts = b[0].startsWith(q) ? 0 : 1;
        if (aStarts !== bStarts) return aStarts - bStarts;
        return a[0].localeCompare(b[0]);
      })
      .slice(0, 8);
  }, [value, allTickers]);

  // Reset highlight on suggestion change (render-time state adjustment pattern)
  const suggestionsKey = suggestions.map((s) => s[0]).join("|");
  const [lastSuggestionsKey, setLastSuggestionsKey] = useState(suggestionsKey);
  if (lastSuggestionsKey !== suggestionsKey) {
    setLastSuggestionsKey(suggestionsKey);
    setHighlightIdx(-1);
  }

  const selectTicker = (ticker: string) => {
    onChange(ticker);
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
    } else if (e.key === "Enter") {
      // Enter confirms an IME candidate; it is not a submit.
      if (e.nativeEvent.isComposing) return;
      if (expanded && highlightIdx >= 0 && suggestions[highlightIdx]) {
        e.preventDefault();
        selectTicker(suggestions[highlightIdx][0]);
      } else if (onSubmit) {
        onSubmit();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showError = value.length >= 2 && !isValid && !open;
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
        onFocus={() => value.length >= 1 && setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        title={title}
        className={`w-24 ${className} font-mono uppercase placeholder:normal-case placeholder:font-sans ${
          showError ? "border-destructive" : ""
        }`}
      />
      {showError && (
        <p id={errorId} role="alert" className="text-[11px] text-destructive mt-0.5 absolute">
          Ticker not found
        </p>
      )}
      {expanded && (
        <div
          id={listboxId}
          role="listbox"
          aria-label="Ticker suggestions"
          className="absolute z-50 mt-1 w-64 overflow-hidden rounded-md border border-border bg-popover shadow-md"
        >
          {suggestions.map(([ticker, company], idx) => {
            const isHighlighted = idx === highlightIdx;
            return (
              <div
                key={ticker}
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
                  selectTicker(ticker);
                }}
                onMouseEnter={() => setHighlightIdx(idx)}
              >
                <span className="font-mono font-medium min-w-14 shrink-0">{ticker}</span>
                <span
                  className={`truncate text-xs ${isHighlighted ? "text-primary-foreground/70" : "text-muted-foreground"}`}
                >
                  {company}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
