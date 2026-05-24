import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Building2, ChartCandlestick, Loader2, Search, SearchX, User } from "lucide-react";

import { CompanyLogo } from "@/components/CompanyLogo";
import { FundLogo } from "@/components/FundLogo";
import { MAX_PER_GROUP, type SearchHit, score } from "@/components/globalSearchUtils";
import { getHedgeFunds, getStocks } from "@/lib/dataService";

export default function GlobalSearch() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
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

  // Group hits by kind so we can display section headers
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
      // Ticker + CUSIP both surface in the Tickers group: typing a CUSIP
      // jumps to the corresponding stock the same way a ticker does. A row
      // can have multiple legacy CUSIPs — bestByTicker keeps the best score.
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
      // Fund CIKs (10-digit zero-padded) also surface in the Funds group so an
      // analyst pasting a CIK from SEC EDGAR lands on the right fund.
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

  // Flat list for keyboard navigation
  const flatHits = useMemo<SearchHit[]>(() => {
    if (!grouped) return [];
    return [...grouped.tickers, ...grouped.companies, ...grouped.funds, ...grouped.managers];
  }, [grouped]);

  // Cmd+K / Ctrl+K to focus the input
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

  // Click outside closes the dropdown
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
      navigate(`/stock/${encodeURIComponent(hit.ticker)}`);
    } else {
      navigate(`/funds/${encodeURIComponent(hit.fund)}`);
    }
    setOpen(false);
    setQuery("");
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
  const hasResults = Boolean(
    grouped &&
    (grouped.tickers.length ||
      grouped.companies.length ||
      grouped.funds.length ||
      grouped.managers.length),
  );

  // Offsets of each group's first item in the flat list — used to align the
  // keyboard-navigated activeIndex with the visually highlighted row.
  const offsets = grouped
    ? {
        tickers: 0,
        companies: grouped.tickers.length,
        funds: grouped.tickers.length + grouped.companies.length,
        managers: grouped.tickers.length + grouped.companies.length + grouped.funds.length,
      }
    : { tickers: 0, companies: 0, funds: 0, managers: 0 };

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search ticker, CUSIP, company, fund, CIK or manager…"
          className="w-full h-9 pl-9 pr-12 rounded-md border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <kbd className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
          ⌘K
        </kbd>
      </div>

      {open && query.trim() && (
        <div className="absolute left-0 right-0 mt-1 max-h-96 overflow-auto rounded-md border border-border bg-popover shadow-md z-50 text-sm">
          {isLoading && (
            <div className="flex items-center gap-2 px-3 py-3 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading index…
            </div>
          )}
          {!isLoading && !hasResults && (
            <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
              <SearchX className="h-6 w-6 text-muted-foreground/60" aria-hidden="true" />
              <div className="text-sm text-foreground">
                No matches for{" "}
                <span className="font-mono font-semibold">&ldquo;{query.trim()}&rdquo;</span>
              </div>
              <div className="text-xs text-muted-foreground">
                Try a ticker, company name, fund or manager.
              </div>
            </div>
          )}
          {!isLoading && hasResults && grouped && (
            <>
              {grouped.tickers.length > 0 && (
                <Group label="Tickers" icon={<ChartCandlestick className="h-3.5 w-3.5" />}>
                  {grouped.tickers.map((hit, i) => (
                    <Row
                      key={`t-${hit.kind === "ticker" ? hit.ticker : ""}`}
                      hit={hit}
                      active={activeIndex === offsets.tickers + i}
                      onClick={() => navigateToHit(hit)}
                      onMouseEnter={() => setActiveIndex(offsets.tickers + i)}
                    />
                  ))}
                </Group>
              )}
              {grouped.companies.length > 0 && (
                <Group label="Companies" icon={<Building2 className="h-3.5 w-3.5" />}>
                  {grouped.companies.map((hit, i) => (
                    <Row
                      key={`c-${hit.kind === "company" ? hit.ticker : ""}`}
                      hit={hit}
                      active={activeIndex === offsets.companies + i}
                      onClick={() => navigateToHit(hit)}
                      onMouseEnter={() => setActiveIndex(offsets.companies + i)}
                    />
                  ))}
                </Group>
              )}
              {grouped.funds.length > 0 && (
                <Group label="Funds" icon={<Building2 className="h-3.5 w-3.5" />}>
                  {grouped.funds.map((hit, i) => (
                    <Row
                      key={`f-${hit.kind === "fund" ? hit.fund : ""}`}
                      hit={hit}
                      active={activeIndex === offsets.funds + i}
                      onClick={() => navigateToHit(hit)}
                      onMouseEnter={() => setActiveIndex(offsets.funds + i)}
                    />
                  ))}
                </Group>
              )}
              {grouped.managers.length > 0 && (
                <Group label="Managers" icon={<User className="h-3.5 w-3.5" />}>
                  {grouped.managers.map((hit, i) => (
                    <Row
                      key={`m-${hit.kind === "manager" ? hit.fund : ""}`}
                      hit={hit}
                      active={activeIndex === offsets.managers + i}
                      onClick={() => navigateToHit(hit)}
                      onMouseEnter={() => setActiveIndex(offsets.managers + i)}
                    />
                  ))}
                </Group>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Group({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border bg-muted/30">
        {icon}
        {label}
      </div>
      <ul>{children}</ul>
    </div>
  );
}

function Row({
  hit,
  active,
  onClick,
  onMouseEnter,
}: {
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
      role="option"
      aria-selected={active}
      onMouseEnter={onMouseEnter}
      onMouseDown={(event) => {
        // Use mouseDown so the click registers before the input blur closes the dropdown.
        event.preventDefault();
        onClick();
      }}
      className={`flex items-center gap-3 px-3 py-2 cursor-pointer ${
        active ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"
      }`}
    >
      {(hit.kind === "ticker" || hit.kind === "company") && (
        <CompanyLogo ticker={hit.ticker} size={22} />
      )}
      {(hit.kind === "fund" || hit.kind === "manager") && (
        <FundLogo fundName={hit.fund} url={hit.url} size={22} className="rounded" />
      )}
      <div className="min-w-0 flex-1">
        <div className={`truncate font-medium ${active ? "" : "text-foreground"}`}>{primary}</div>
        <div className={`truncate text-xs ${active ? "opacity-80" : "text-muted-foreground"}`}>
          {secondary}
        </div>
      </div>
    </li>
  );
}
