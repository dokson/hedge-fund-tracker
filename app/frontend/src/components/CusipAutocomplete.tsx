import { useState, useRef, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { Input } from "@/components/ui/input";

interface CusipAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onValidChange?: (valid: boolean) => void;
  className?: string;
  placeholder?: string;
}

export default function CusipAutocomplete({
  value,
  onChange,
  onValidChange,
  className = "",
  placeholder = "e.g. 594918104",
}: CusipAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const allCusips = useMemo(
    () => stocks.map((s) => ({ cusip: s.cusip, ticker: s.ticker, company: s.company })),
    [stocks]
  );

  const isValid = useMemo(
    () => allCusips.some((c) => c.cusip === value),
    [allCusips, value]
  );

  useEffect(() => {
    onValidChange?.(isValid);
  }, [isValid, onValidChange]);

  const suggestions = useMemo(() => {
    if (!value || value.length < 2) return [];
    const q = value.toUpperCase();
    return allCusips
      .filter((c) => c.cusip.includes(q) || c.ticker.toUpperCase().includes(q) || c.company.toUpperCase().includes(q))
      .sort((a, b) => {
        const aStarts = a.cusip.startsWith(q) ? 0 : 1;
        const bStarts = b.cusip.startsWith(q) ? 0 : 1;
        if (aStarts !== bStarts) return aStarts - bStarts;
        return a.cusip.localeCompare(b.cusip);
      })
      .slice(0, 8);
  }, [value, allCusips]);

  useEffect(() => { setHighlightIdx(-1); }, [suggestions]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectCusip = (cusip: string) => { onChange(cusip); setOpen(false); };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setHighlightIdx((i) => Math.min(i + 1, suggestions.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHighlightIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && highlightIdx >= 0 && suggestions[highlightIdx]) { selectCusip(suggestions[highlightIdx].cusip); }
    else if (e.key === "Escape") { setOpen(false); }
  };

  const showError = value.length >= 3 && !isValid && !open;

  return (
    <div ref={wrapperRef} className="relative">
      <Input
        value={value}
        onChange={(e) => { onChange(e.target.value.toUpperCase()); setOpen(true); }}
        onFocus={() => value.length >= 2 && setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        size={9}
        className={`${className} font-mono uppercase ${showError ? "border-destructive focus-visible:ring-destructive" : ""}`}
      />
      {showError && <p className="text-[10px] text-destructive mt-0.5 absolute">CUSIP not found</p>}
      {open && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-72 rounded-md border border-border bg-popover shadow-md overflow-hidden">
          {suggestions.map((item, idx) => {
            const isHighlighted = idx === highlightIdx;
            return (
              <div
                key={item.cusip}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer transition-colors ${
                  isHighlighted ? "bg-primary text-primary-foreground" : "hover:bg-accent/50"
                }`}
                onMouseDown={() => selectCusip(item.cusip)}
                onMouseEnter={() => setHighlightIdx(idx)}
              >
                <span className="font-mono font-medium w-24 shrink-0 text-xs">{item.cusip}</span>
                <span className="font-mono w-12 shrink-0 text-xs">{item.ticker}</span>
                <span className={`truncate text-xs ${isHighlighted ? "text-primary-foreground/70" : "text-muted-foreground"}`}>{item.company}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
