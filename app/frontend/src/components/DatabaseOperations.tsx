import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { parseSSEEvent } from "@/lib/aiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/Field";
import { Panel } from "@/components/ui/Panel";
import { StatusChip } from "@/components/ui/StatusChip";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import TickerAutocomplete from "@/components/TickerAutocomplete";
import CusipAutocomplete from "@/components/CusipAutocomplete";
import TerminalOutput from "@/components/TerminalOutput";

import { IS_GH_PAGES_MODE } from "@/lib/config";

const API_BASE = `${window.location.origin}/api`;

type JobStatus = "idle" | "running" | "success" | "error";

interface OperationState {
  status: JobStatus;
  message?: string;
}

interface Operation {
  id: string;
  title: string;
  description: string;
  endpoint: string;
  streamable?: boolean;
  /** Read-only operations skip the destructive-action confirmation dialog. */
  readonly?: boolean;
}

const operations: Operation[] = [
  {
    id: "update-all",
    title: "Generate All 13F Reports",
    description:
      "Fetches and generates the latest quarterly 13F comparison reports for all monitored hedge funds.",
    endpoint: "/update-all",
    streamable: true,
  },
  {
    id: "fetch-nq",
    title: "Fetch Non-Quarterly Filings",
    description: "Fetches the latest 13D/G and Form 4 filings for all monitored hedge funds.",
    endpoint: "/fetch-nq",
    streamable: true,
  },
  {
    id: "funds-missing-quarters",
    title: "Show Funds With Missing Quarters",
    description:
      "Lists every tracked hedge fund that is missing 13F data for at least one available quarter.",
    endpoint: "/funds-missing-quarters",
    readonly: true,
  },
  {
    id: "apply-ticker-changes",
    title: "Auto-Apply Ticker Changes (NASDAQ)",
    description:
      "Pulls the latest symbol-change feed from NASDAQ and applies any matches against stocks.csv automatically.",
    endpoint: "/apply-ticker-changes",
  },
  {
    id: "update-ticker",
    title: "Update Ticker",
    description: "Replaces an old ticker symbol with a new one across stocks.csv and all filings.",
    endpoint: "/update-ticker",
  },
  {
    id: "update-cusip-ticker",
    title: "Update CUSIP Ticker",
    description: "Updates the ticker for a single CUSIP across stocks.csv and all filings.",
    endpoint: "/update-cusip-ticker",
  },
];

function StatusBadge({ status }: { status: JobStatus }) {
  if (status === "idle") return null;
  return (
    <StatusChip
      role="status"
      tone={status === "running" ? "warning" : status === "success" ? "positive" : "negative"}
    >
      {status === "running" && <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />}
      {status === "running" ? "Running" : status === "success" ? "Done" : "Error"}
    </StatusChip>
  );
}

export default function DatabaseOperations() {
  const [states, setStates] = useState<Record<string, OperationState>>({});
  const [fieldValues, setFieldValues] = useState<Record<string, Record<string, string>>>({});
  const [logs, setLogs] = useState<Record<string, string[]>>({});
  const [fieldValid, setFieldValid] = useState<Record<string, boolean>>({});
  const [confirmOp, setConfirmOp] = useState<Operation | null>(null);
  const [activeOp, setActiveOp] = useState<Operation | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  // Abort any in-flight stream on unmount so the FastAPI worker is released
  // when the user navigates away — otherwise subsequent CSV / API requests
  // queue behind the dangling stream and the next page appears frozen.
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const { data: stocks = [] } = useQuery({
    queryKey: ["stocks"],
    queryFn: getStocks,
    staleTime: 10 * 60 * 1000,
  });

  const oldTickerInfo = useMemo(() => {
    const tickerVal = fieldValues["update-ticker"]?.old_ticker;
    if (!tickerVal) return null;
    const stock = stocks.find((s) => s.ticker === tickerVal);
    return stock ? { company: stock.company } : null;
  }, [stocks, fieldValues]);

  const cusipInfo = useMemo(() => {
    const cusipVal = fieldValues["update-cusip-ticker"]?.cusip;
    if (!cusipVal) return null;
    const stock = stocks.find((s) => s.cusip === cusipVal);
    return stock ? { ticker: stock.ticker, company: stock.company } : null;
  }, [stocks, fieldValues]);

  const setField = (opId: string, key: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [opId]: { ...prev[opId], [key]: value } }));
  };

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, activeOp]);

  const runOperation = useCallback(async (op: Operation, params: Record<string, string> = {}) => {
    setStates((prev) => ({ ...prev, [op.id]: { status: "running" } }));
    setLogs((prev) => ({ ...prev, [op.id]: [] }));
    setActiveOp(op);

    const addLog = (line: string) =>
      setLogs((prev) => ({ ...prev, [op.id]: [...(prev[op.id] || []), line] }));

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      if (op.streamable) {
        const res = await fetch(`${API_BASE}${op.endpoint}/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
          signal: abortController.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!res.body) throw new Error("Response body is not readable");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalMessage = "Completed successfully";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const event = parseSSEEvent(line.slice(6));
            if (!event) continue;
            if (event.type === "log") addLog(event.text);
            else if (event.type === "result") {
              if (typeof event.data === "string") finalMessage = event.data;
              break;
            } else throw new Error(event.message);
          }
        }

        setStates((prev) => ({ ...prev, [op.id]: { status: "success", message: finalMessage } }));
        toast.success(`${op.title} completed`);
      } else {
        const res = await fetch(`${API_BASE}${op.endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
          signal: abortController.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: unknown = await res.json();
        const message =
          typeof data === "object" &&
          data !== null &&
          "message" in data &&
          typeof data.message === "string"
            ? data.message
            : "Completed successfully";
        setStates((prev) => ({ ...prev, [op.id]: { status: "success", message } }));
        addLog(message);
        toast.success(`${op.title} completed`);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      const msg = errMsg.includes("Failed to fetch")
        ? "Cannot connect to server. Make sure it's running."
        : errMsg;
      setStates((prev) => ({ ...prev, [op.id]: { status: "error", message: msg } }));
      addLog(msg);
      toast.error(`${op.title} failed`, { description: msg });
    }
  }, []);

  const handleRun = (op: Operation) => {
    const params = fieldValues[op.id] || {};

    if (op.id === "update-ticker") {
      if (!params.old_ticker?.trim()) {
        toast.error('"Old Ticker" is required');
        return;
      }
      if (!params.new_ticker?.trim()) {
        toast.error('"New Ticker" is required');
        return;
      }
    }
    if (op.id === "update-cusip-ticker") {
      if (!params.cusip?.trim()) {
        toast.error('"CUSIP" is required');
        return;
      }
      if (!params.new_ticker?.trim()) {
        toast.error('"New Ticker" is required');
        return;
      }
    }

    // Read-only operations don't touch the disk, so skip the destructive-action
    // confirmation dialog and run immediately.
    if (op.readonly) {
      void runOperation(op, params);
      return;
    }

    setConfirmOp(op);
  };

  const handleConfirm = () => {
    if (!confirmOp) return;
    const params = fieldValues[confirmOp.id] || {};
    void runOperation(confirmOp, params);
    setConfirmOp(null);
  };

  const activeState = activeOp ? states[activeOp.id] || { status: "idle" } : null;
  const activeIsRunning = activeState?.status === "running";
  const activeLogs = activeOp ? logs[activeOp.id] || [] : [];

  const isRunDisabled = (op: Operation, isRunning: boolean) => {
    if (isRunning) return true;
    if (op.id === "update-ticker") {
      return !fieldValid["old_ticker"] || !fieldValues[op.id]?.new_ticker?.trim();
    }
    if (op.id === "update-cusip-ticker") {
      return !fieldValid["cusip"] || !fieldValues[op.id]?.new_ticker?.trim();
    }
    return false;
  };

  const renderFields = (op: Operation, isRunning: boolean) => {
    if (op.id === "update-ticker") {
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Old Ticker" htmlFor={`${op.id}-old-ticker`}>
            <div className="min-w-0 space-y-2">
              <TickerAutocomplete
                id={`${op.id}-old-ticker`}
                value={fieldValues[op.id]?.old_ticker || ""}
                onChange={(v) => setField(op.id, "old_ticker", v)}
                onValidChange={(v) => setFieldValid((prev) => ({ ...prev, old_ticker: v }))}
                placeholder="e.g. FB"
                className="min-h-10 !w-full text-xs placeholder:normal-case placeholder:font-sans md:min-h-0"
              />
              {oldTickerInfo && fieldValid["old_ticker"] && (
                <span className="block truncate text-xs text-muted-foreground">
                  {oldTickerInfo.company}
                </span>
              )}
            </div>
          </Field>
          <Field label="New Ticker" htmlFor={`${op.id}-new-ticker`}>
            <Input
              id={`${op.id}-new-ticker`}
              placeholder="e.g. META"
              value={fieldValues[op.id]?.new_ticker || ""}
              onChange={(e) => setField(op.id, "new_ticker", e.target.value.toUpperCase())}
              className="min-h-10 text-xs font-mono uppercase placeholder:normal-case placeholder:font-sans w-full md:min-h-0"
              disabled={isRunning}
            />
          </Field>
        </div>
      );
    }

    if (op.id === "update-cusip-ticker") {
      return (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="CUSIP" htmlFor={`${op.id}-cusip`}>
            <div className="min-w-0 space-y-2">
              <CusipAutocomplete
                id={`${op.id}-cusip`}
                value={fieldValues[op.id]?.cusip || ""}
                onChange={(v) => setField(op.id, "cusip", v)}
                onValidChange={(v) => setFieldValid((prev) => ({ ...prev, cusip: v }))}
                placeholder="e.g. 594918104"
                className="min-h-10 w-full text-xs placeholder:normal-case placeholder:font-sans md:min-h-0"
              />
              {cusipInfo && fieldValid["cusip"] && (
                <span className="block truncate text-xs text-muted-foreground">
                  <span className="font-mono font-medium text-foreground">{cusipInfo.ticker}</span>{" "}
                  · {cusipInfo.company}
                </span>
              )}
            </div>
          </Field>
          <Field label="New Ticker" htmlFor={`${op.id}-new-ticker`}>
            <Input
              id={`${op.id}-new-ticker`}
              placeholder="e.g. MSFT"
              value={fieldValues[op.id]?.new_ticker || ""}
              onChange={(e) => setField(op.id, "new_ticker", e.target.value.toUpperCase())}
              className="min-h-10 text-xs font-mono uppercase placeholder:normal-case placeholder:font-sans w-full md:min-h-0"
              disabled={isRunning}
            />
          </Field>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-w-0 space-y-4 [&_button]:min-h-10 [&_[role=option]]:min-h-10 md:[&_button]:min-h-0 md:[&_[role=option]]:min-h-0">
      <Panel title="Database operations" className="overflow-visible">
        <ol className="divide-y divide-border" aria-label="Operations">
          {operations.map((op, i) => {
            const state = states[op.id] || { status: "idle" };
            const isRunning = state.status === "running";

            return (
              <li
                key={op.id}
                className="grid min-w-0 gap-4 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:p-4"
              >
                <div className="min-w-0 space-y-3">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <h3 className="text-sm font-medium">
                      <span className="mr-2 text-muted-foreground tabular-nums">{i + 1}.</span>
                      {op.title}
                    </h3>
                    <StatusBadge status={state.status} />
                  </div>
                  <p className="text-sm text-muted-foreground">{op.description}</p>
                  {renderFields(op, isRunning)}
                </div>
                <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
                  <span className="metric-label">
                    {op.readonly ? "Read only" : "Writes local data"}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    className={`min-h-10 min-w-24 md:min-h-0 ${op.id.includes("ticker") ? "text-negative hover:text-negative" : ""}`}
                    aria-label={`Run ${op.title}`}
                    disabled={isRunDisabled(op, isRunning) || IS_GH_PAGES_MODE}
                    onClick={() => handleRun(op)}
                  >
                    {isRunning && (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    )}
                    {IS_GH_PAGES_MODE ? "Disabled in Demo" : isRunning ? "Running…" : "Run"}
                  </Button>
                </div>
              </li>
            );
          })}
        </ol>
      </Panel>

      {/* Confirmation Dialog */}
      <AlertDialog open={!!confirmOp} onOpenChange={(open) => !open && setConfirmOp(null)}>
        <AlertDialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto [&_button]:min-h-10">
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm: {confirmOp?.title}</AlertDialogTitle>
            <AlertDialogDescription>
              This will start a process that modifies actual data on disk. Once started, the
              operation window cannot be closed until it completes. Are you sure you want to
              proceed?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={handleConfirm}
            >
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Execution Log Dialog (blocking while running) */}
      <Dialog
        open={!!activeOp}
        onOpenChange={(open) => {
          if (!open && !activeIsRunning) setActiveOp(null);
        }}
      >
        <DialogContent
          className={`max-h-[90dvh] w-[calc(100%_-_2rem)] min-w-0 overflow-y-auto sm:max-w-3xl [&_button]:min-h-10 ${activeIsRunning ? "[&>button]:hidden" : ""}`}
          onPointerDownOutside={(e) => {
            if (activeIsRunning) e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (activeIsRunning) e.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              {activeIsRunning && (
                <Loader2
                  className="h-4 w-4 animate-spin text-muted-foreground"
                  aria-hidden="true"
                />
              )}
              {activeState?.status === "success" && (
                <span className="text-positive" aria-hidden="true">
                  OK
                </span>
              )}
              {activeState?.status === "error" && (
                <span className="text-negative" aria-hidden="true">
                  ERR
                </span>
              )}
              {activeOp?.title}
            </DialogTitle>
            <DialogDescription>
              {activeIsRunning
                ? "Operation in progress — closing is disabled until it completes."
                : "Operation completed. You can close this dialog."}
            </DialogDescription>
          </DialogHeader>

          {activeOp?.streamable ? (
            <TerminalOutput lines={activeLogs} running={activeIsRunning} />
          ) : (
            <Panel title="Output" className="bg-background">
              <div className="p-3 max-h-64 overflow-y-auto font-mono text-xs">
                {activeLogs.map((log, i) => (
                  <p
                    // append-only log buffer; index is a stable identity
                    key={i}
                    className="break-words text-muted-foreground leading-5 whitespace-pre-wrap"
                  >
                    {log}
                  </p>
                ))}
                <div ref={logEndRef} />
              </div>
            </Panel>
          )}

          {!activeIsRunning && (
            <DialogFooter>
              <Button size="sm" variant="outline" onClick={() => setActiveOp(null)}>
                Close
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
