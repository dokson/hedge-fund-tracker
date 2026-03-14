import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { Input } from "@/components/ui/input";

interface TickerAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  onValidChange?: (valid: boolean) => void;
  className?: string;
  placeholder?: string;
}

export default function TickerAutocomplete({
  value,
  onChange,
  onSubmit,
  onValidChange,
  className = "",
  placeholder = "NVDA",
}: TickerAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const allTickers = useMemo(
    () => [...new Map(stocks.map((s) => [s.ticker, s.company])).entries()],
    [stocks]
  );

  const isValid = useMemo(
    () => allTickers.some(([t]) => t === value),
    [allTickers, value]
  );

  const onValidChangeRef = useRef(onValidChange);
  onValidChangeRef.current = onValidChange;

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

  useEffect(() => {
    setHighlightIdx(-1);
  }, [suggestions]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectTicker = (ticker: string) => {
    onChange(ticker);
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (highlightIdx >= 0 && suggestions[highlightIdx]) {
        selectTicker(suggestions[highlightIdx][0]);
      } else if (onSubmit) {
        onSubmit();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showError = value.length >= 2 && !isValid && !open;

  return (
    <div ref={wrapperRef} className="relative">
      <Input
        value={value}
        onChange={(e) => {
          onChange(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => value.length >= 1 && setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={`w-24 ${className} font-mono uppercase placeholder:normal-case placeholder:font-sans ${
          showError ? "border-destructive focus-visible:ring-destructive" : ""
        }`}
      />
      {showError && (
        <p className="text-[10px] text-destructive mt-0.5 absolute">Ticker not found</p>
      )}
      {open && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-64 rounded-md border border-border bg-popover shadow-md overflow-hidden">
          {suggestions.map(([ticker, company], idx) => {
            const isHighlighted = idx === highlightIdx;
            return (
              <div
                key={ticker}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer transition-colors ${
                  isHighlighted ? "bg-primary text-primary-foreground" : "hover:bg-accent/50"
                }`}
                onMouseDown={() => selectTicker(ticker)}
                onMouseEnter={() => setHighlightIdx(idx)}
              >
                <span className="font-mono font-medium w-14 shrink-0">{ticker}</span>
                <span className={`truncate text-xs ${isHighlighted ? "text-primary-foreground/70" : "text-muted-foreground"}`}>{company}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
