import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { Loader2, Search } from "lucide-react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { FundLogo } from "@/components/FundLogo";
import { MAX_PER_GROUP, type SearchHit, score } from "@/components/globalSearchUtils";
import { getHedgeFunds, getStocks } from "@/lib/dataService";
import { stockPath, fundPath } from "@/lib/routes";

const IS_MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

/**
 * One combobox over tickers, CUSIPs, companies, funds, CIKs and managers;
 * results are a listbox walked with the arrow keys, and Ctrl/⌘ K focuses it.
 */
export default function GlobalSearch({
  focusOnMount = false,
  onNavigate,
}: {
  /** Focus the input on mount — used when the search lives inside a mobile sheet. */
  focusOnMount?: boolean;
  /** Fired after navigating to a hit — lets a wrapping mobile sheet close itself. */
  onNavigate?: () => void;
} = {}) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const { data: stocks = [], isLoading: stocksLoading } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
  });
  const { data: funds = [], isLoading: fundsLoading } = useQuery({
    queryKey: ["hedge_funds"],
    queryFn: getHedgeFunds,
  });

  const grouped = useMemo(() => {
    const q = query.trim();
    if (!q || q.length < 1) return null;

    const tickerHits: { hit: SearchHit; rank: number }[] = [];
    const companyHits: { hit: SearchHit; rank: number }[] = [];
    // stocks.csv is keyed by CUSIP, so a ticker can appear multiple times after
    // a CUSIP renumber. Keep only the best-scoring row per ticker in each group.
    const bestByTicker = new Map<string, number>();
    const bestByCompany = new Map<string, number>();
    for (const s of stocks) {
      if (!s.ticker) continue;
      const tickerScore = score(q, s.ticker);
      const cusipScore = s.cusip ? score(q, s.cusip) : -1;
      const bestStockScore =
        tickerScore >= 0 && cusipScore >= 0
          ? Math.min(tickerScore, cusipScore)
          : tickerScore >= 0
            ? tickerScore
            : cusipScore;
      if (bestStockScore >= 0) {
        const prev = bestByTicker.get(s.ticker);
        if (prev === undefined || bestStockScore < prev) {
          bestByTicker.set(s.ticker, bestStockScore);
        }
      }
      const companyScore = s.company ? score(q, s.company) : -1;
      if (companyScore >= 0) {
        const prev = bestByCompany.get(s.ticker);
        if (prev === undefined || companyScore < prev) {
          bestByCompany.set(s.ticker, companyScore);
        }
      }
    }
    const tickerToCompany = new Map(stocks.map((s) => [s.ticker, s.company]));
    for (const [ticker, rank] of bestByTicker) {
      tickerHits.push({
        hit: { kind: "ticker", ticker, company: tickerToCompany.get(ticker) ?? "" },
        rank,
      });
    }
    for (const [ticker, rank] of bestByCompany) {
      companyHits.push({
        hit: { kind: "company", ticker, company: tickerToCompany.get(ticker) ?? "" },
        rank,
      });
    }

    const fundHits: { hit: SearchHit; rank: number }[] = [];
    const managerHits: { hit: SearchHit; rank: number }[] = [];
    for (const f of funds) {
      const fundScore = score(q, f.fund);
      const cikScore = f.cik ? score(q, f.cik) : -1;
      const bestFundScore =
        fundScore >= 0 && cikScore >= 0
          ? Math.min(fundScore, cikScore)
          : fundScore >= 0
            ? fundScore
            : cikScore;
      if (bestFundScore >= 0) {
        fundHits.push({
          hit: { kind: "fund", fund: f.fund, manager: f.manager, url: f.url },
          rank: bestFundScore,
        });
      }
      const managerScore = f.manager ? score(q, f.manager) : -1;
      if (managerScore >= 0) {
        managerHits.push({
          hit: { kind: "manager", fund: f.fund, manager: f.manager, url: f.url },
          rank: managerScore,
        });
      }
    }

    const cap = (arr: { hit: SearchHit; rank: number }[]) =>
      arr
        .sort((a, b) => a.rank - b.rank)
        .slice(0, MAX_PER_GROUP)
        .map((x) => x.hit);

    return {
      tickers: cap(tickerHits),
      companies: cap(companyHits),
      funds: cap(fundHits),
      managers: cap(managerHits),
    };
  }, [query, stocks, funds]);

  const flatHits = useMemo<SearchHit[]>(() => {
    if (!grouped) return [];
    return [...grouped.tickers, ...grouped.companies, ...grouped.funds, ...grouped.managers];
  }, [grouped]);

  useEffect(() => {
    if (focusOnMount) inputRef.current?.focus();
  }, [focusOnMount]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, []);

  const navigateToHit = (hit: SearchHit) => {
    if (hit.kind === "ticker" || hit.kind === "company") {
      void navigate(stockPath(hit.ticker));
    } else {
      void navigate(fundPath(hit.fund));
    }
    setOpen(false);
    setQuery("");
    onNavigate?.();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(flatHits.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const hit = flatHits[activeIndex];
      if (hit) navigateToHit(hit);
    } else if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  const isLoading = stocksLoading || fundsLoading;
  const hasResults = flatHits.length > 0;
  const expanded = open && query.trim().length > 0;

  const offsets = grouped
    ? {
        tickers: 0,
        companies: grouped.tickers.length,
        funds: grouped.tickers.length + grouped.companies.length,
        managers: grouped.tickers.length + grouped.companies.length + grouped.funds.length,
      }
    : { tickers: 0, companies: 0, funds: 0, managers: 0 };

  const optionId = (i: number) => `${listId}-opt-${i}`;
  const groupCount = grouped
    ? [grouped.tickers, grouped.companies, grouped.funds, grouped.managers].filter((g) => g.length)
        .length
    : 0;

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative flex items-center h-9 rounded-md border border-input bg-background transition-colors duration-[120ms] focus-within:border-primary">
        <Search aria-hidden="true" className="ml-2.5 mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-label="Search ticker, CUSIP, company, fund, CIK or manager"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={expanded && hasResults ? optionId(activeIndex) : undefined}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="ticker, cusip, fund, manager"
          // No `focus:outline-none`: Tailwind emits it into the `utilities`
          // layer, which beats the `@layer base` :focus-visible ring in
          // index.css, leaving a 1px border tint as the only indicator.
          className="w-full h-full bg-transparent pr-16 text-[13px] text-foreground placeholder:text-muted-foreground"
        />
        <kbd className="hidden sm:inline-block absolute right-2 top-1/2 -translate-y-1/2 rounded-sm border border-border px-1.5 py-0.5 font-sans text-[11px] text-muted-foreground">
          {IS_MAC ? "⌘K" : "Ctrl K"}
        </kbd>
      </div>

      <div aria-live="polite" className="sr-only">
        {expanded && !isLoading
          ? hasResults
            ? `${flatHits.length} results in ${groupCount} groups`
            : "No matches"
          : ""}
      </div>

      <ul
        id={listId}
        role="listbox"
        aria-label="Search results"
        hidden={!expanded}
        className="absolute left-0 right-0 mt-1 max-h-96 overflow-auto rounded-md border border-border bg-popover shadow-md z-50 text-[13px]"
      >
        {expanded && isLoading && (
          <li className="flex items-center gap-2 px-3 py-3 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading index…
          </li>
        )}
        {expanded && !isLoading && !hasResults && (
          <li className="px-3 py-4">
            <div className="text-foreground">
              No match for <span className="font-medium">&ldquo;{query.trim()}&rdquo;</span>
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Try a ticker, company name, fund or manager.
            </div>
          </li>
        )}
        {expanded && !isLoading && hasResults && grouped && (
          <>
            <Group label="Tickers" hits={grouped.tickers} />
            {grouped.tickers.map((hit, i) => (
              <Row
                key={`t-${hit.kind === "ticker" ? hit.ticker : ""}`}
                id={optionId(offsets.tickers + i)}
                hit={hit}
                active={activeIndex === offsets.tickers + i}
                onClick={() => navigateToHit(hit)}
                onMouseEnter={() => setActiveIndex(offsets.tickers + i)}
              />
            ))}
            <Group label="Companies" hits={grouped.companies} />
            {grouped.companies.map((hit, i) => (
              <Row
                key={`c-${hit.kind === "company" ? hit.ticker : ""}`}
                id={optionId(offsets.companies + i)}
                hit={hit}
                active={activeIndex === offsets.companies + i}
                onClick={() => navigateToHit(hit)}
                onMouseEnter={() => setActiveIndex(offsets.companies + i)}
              />
            ))}
            <Group label="Funds" hits={grouped.funds} />
            {grouped.funds.map((hit, i) => (
              <Row
                key={`f-${hit.kind === "fund" ? hit.fund : ""}`}
                id={optionId(offsets.funds + i)}
                hit={hit}
                active={activeIndex === offsets.funds + i}
                onClick={() => navigateToHit(hit)}
                onMouseEnter={() => setActiveIndex(offsets.funds + i)}
              />
            ))}
            <Group label="Managers" hits={grouped.managers} />
            {grouped.managers.map((hit, i) => (
              <Row
                key={`m-${hit.kind === "manager" ? hit.fund : ""}`}
                id={optionId(offsets.managers + i)}
                hit={hit}
                active={activeIndex === offsets.managers + i}
                onClick={() => navigateToHit(hit)}
                onMouseEnter={() => setActiveIndex(offsets.managers + i)}
              />
            ))}
          </>
        )}
      </ul>
    </div>
  );
}

/** A group label inside the listbox. Presentational. */
function Group({ label, hits }: { label: string; hits: SearchHit[] }) {
  if (hits.length === 0) return null;
  return (
    <li role="presentation" className="px-3 pt-2 pb-1 text-[11px] text-muted-foreground">
      {label}
    </li>
  );
}

function Row({
  id,
  hit,
  active,
  onClick,
  onMouseEnter,
}: {
  id: string;
  hit: SearchHit;
  active: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}) {
  const primary =
    hit.kind === "ticker"
      ? hit.ticker
      : hit.kind === "company"
        ? hit.company
        : hit.kind === "fund"
          ? hit.fund
          : hit.manager;
  const secondary =
    hit.kind === "ticker"
      ? hit.company
      : hit.kind === "company"
        ? hit.ticker
        : hit.kind === "fund"
          ? hit.manager
          : hit.fund;

  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      onMouseEnter={onMouseEnter}
      onMouseDown={(event) => {
        // mouseDown so the click registers before the input blur closes the list.
        event.preventDefault();
        onClick();
      }}
      className={`flex items-center gap-3 px-3 py-1.5 cursor-pointer ${
        active ? "bg-muted text-foreground" : ""
      }`}
    >
      {(hit.kind === "ticker" || hit.kind === "company") && (
        <CompanyLogo ticker={hit.ticker} size={20} />
      )}
      {(hit.kind === "fund" || hit.kind === "manager") && (
        <FundLogo fundName={hit.fund} url={hit.url} size={20} />
      )}
      <div className="min-w-0 flex-1 flex items-baseline gap-3">
        <span className="truncate font-medium">{primary}</span>
        <span className="truncate text-xs text-muted-foreground">{secondary}</span>
      </div>
    </li>
  );
}
