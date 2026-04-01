import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getStocks } from "@/lib/dataService";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Play, Loader2, CheckCircle2, XCircle, RefreshCw,
  ArrowRightLeft, Terminal
} from "lucide-react";
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
  icon: React.ReactNode;
  endpoint: string;
  streamable?: boolean;
}

const operations: Operation[] = [
  {
    id: "update-all",
    title: "Generate All 13F Reports",
    description: "Fetches and generates the latest quarterly 13F comparison reports for all monitored hedge funds.",
    icon: <RefreshCw className="h-5 w-5" />,
    endpoint: "/update-all",
    streamable: true,
  },
  {
    id: "fetch-nq",
    title: "Fetch Non-Quarterly Filings",
    description: "Fetches the latest 13D/G and Form 4 filings for all monitored hedge funds.",
    icon: <RefreshCw className="h-5 w-5" />,
    endpoint: "/fetch-nq",
    streamable: true,
  },
  {
    id: "update-ticker",
    title: "Update Ticker",
    description: "Replaces an old ticker symbol with a new one across stocks.csv and all filings.",
    icon: <ArrowRightLeft className="h-5 w-5" />,
    endpoint: "/update-ticker",
  },
  {
    id: "update-cusip-ticker",
    title: "Update CUSIP Ticker",
    description: "Updates the ticker for a single CUSIP across stocks.csv and all filings.",
    icon: <ArrowRightLeft className="h-5 w-5" />,
    endpoint: "/update-cusip-ticker",
  },
];

function StatusBadge({ status }: { status: JobStatus }) {
  switch (status) {
    case "running":
      return <Badge variant="secondary" className="gap-1 text-xs"><Loader2 className="h-3 w-3 animate-spin" /> Running</Badge>;
    case "success":
      return <Badge className="gap-1 text-xs bg-[hsl(var(--positive))] text-[hsl(var(--positive-foreground))]"><CheckCircle2 className="h-3 w-3" /> Done</Badge>;
    case "error":
      return <Badge variant="destructive" className="gap-1 text-xs"><XCircle className="h-3 w-3" /> Error</Badge>;
    default:
      return null;
  }
}

export default function DatabaseOperations() {
  const [states, setStates] = useState<Record<string, OperationState>>({});
  const [fieldValues, setFieldValues] = useState<Record<string, Record<string, string>>>({});
  const [logs, setLogs] = useState<Record<string, string[]>>({});
  const [fieldValid, setFieldValid] = useState<Record<string, boolean>>({});
  const [confirmOp, setConfirmOp] = useState<Operation | null>(null);
  const [activeOp, setActiveOp] = useState<Operation | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

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

    try {
      if (op.streamable) {
        const res = await fetch(`${API_BASE}${op.endpoint}/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader = res.body!.getReader();
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
            const event = JSON.parse(line.slice(6));
            if (event.type === "log") addLog(event.text);
            else if (event.type === "result") { finalMessage = event.data ?? finalMessage; break; }
            else if (event.type === "error") throw new Error(event.message);
          }
        }

        setStates((prev) => ({ ...prev, [op.id]: { status: "success", message: finalMessage } }));
        toast.success(`${op.title} completed`);
      } else {
        const res = await fetch(`${API_BASE}${op.endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(params),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setStates((prev) => ({ ...prev, [op.id]: { status: "success", message: data.message } }));
        addLog(`✅ ${data.message || "Completed successfully"}`);
        toast.success(`${op.title} completed`);
      }
    } catch (err: any) {
      const msg = err.message?.includes("Failed to fetch")
        ? "Cannot connect to server. Make sure it's running."
        : err.message;
      setStates((prev) => ({ ...prev, [op.id]: { status: "error", message: msg } }));
      addLog(`❌ ${msg}`);
      toast.error(`${op.title} failed`, { description: msg });
    }
  }, []);

  const handleRun = (op: Operation) => {
    const params = fieldValues[op.id] || {};

    if (op.id === "update-ticker") {
      if (!params.old_ticker?.trim()) { toast.error('"Old Ticker" is required'); return; }
      if (!params.new_ticker?.trim()) { toast.error('"New Ticker" is required'); return; }
    }
    if (op.id === "update-cusip-ticker") {
      if (!params.cusip?.trim()) { toast.error('"CUSIP" is required'); return; }
      if (!params.new_ticker?.trim()) { toast.error('"New Ticker" is required'); return; }
    }

    setConfirmOp(op);
  };

  const handleConfirm = () => {
    if (!confirmOp) return;
    const params = fieldValues[confirmOp.id] || {};
    runOperation(confirmOp, params);
    setConfirmOp(null);
  };

  const activeState = activeOp ? (states[activeOp.id] || { status: "idle" }) : null;
  const activeIsRunning = activeState?.status === "running";
  const activeLogs = activeOp ? (logs[activeOp.id] || []) : [];

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
        <div className="space-y-2">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Old Ticker</Label>
            <div className="flex items-center gap-2">
              <div className="shrink-0">
                <TickerAutocomplete
                  value={fieldValues[op.id]?.old_ticker || ""}
                  onChange={(v) => setField(op.id, "old_ticker", v)}
                  onValidChange={(v) => setFieldValid((prev) => ({ ...prev, old_ticker: v }))}
                  placeholder="e.g. FB"
                  className="h-8 text-xs placeholder:normal-case placeholder:font-sans"
                />
              </div>
              {oldTickerInfo && fieldValid["old_ticker"] && (
                <span className="text-xs text-muted-foreground truncate">
                  {oldTickerInfo.company}
                </span>
              )}
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">New Ticker</Label>
            <Input
              placeholder="e.g. META"
              value={fieldValues[op.id]?.new_ticker || ""}
              onChange={(e) => setField(op.id, "new_ticker", e.target.value.toUpperCase())}
              className="h-8 text-xs bg-background border-border font-mono uppercase placeholder:normal-case placeholder:font-sans w-24"
              disabled={isRunning}
            />
          </div>
        </div>
      );
    }

    if (op.id === "update-cusip-ticker") {
      return (
        <div className="space-y-2">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">CUSIP</Label>
            <div className="flex items-center gap-2">
              <div className="w-32 shrink-0">
                <CusipAutocomplete
                  value={fieldValues[op.id]?.cusip || ""}
                  onChange={(v) => setField(op.id, "cusip", v)}
                  onValidChange={(v) => setFieldValid((prev) => ({ ...prev, cusip: v }))}
                  placeholder="e.g. 594918104"
                  className="h-8 text-xs placeholder:normal-case placeholder:font-sans"
                />
              </div>
              {cusipInfo && fieldValid["cusip"] && (
                <span className="text-xs text-muted-foreground truncate">
                  <span className="font-mono font-medium text-foreground">{cusipInfo.ticker}</span> · {cusipInfo.company}
                </span>
              )}
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">New Ticker</Label>
            <Input
              placeholder="e.g. MSFT"
              value={fieldValues[op.id]?.new_ticker || ""}
              onChange={(e) => setField(op.id, "new_ticker", e.target.value.toUpperCase())}
              className="h-8 text-xs bg-background border-border font-mono uppercase placeholder:normal-case placeholder:font-sans w-24"
              disabled={isRunning}
            />
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        <Terminal className="h-4 w-4 shrink-0 mt-0.5" />
        <div>
          <p>These operations invoke local Python commands from <code className="font-mono bg-muted px-1 py-0.5 rounded">database/updater.py</code>.</p>
          <p className="mt-1">Each button triggers the corresponding updater function via a local bridge.</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {operations.map((op) => {
          const state = states[op.id] || { status: "idle" };
          const isRunning = state.status === "running";

          return (
            <Card key={op.id} className="transition-all">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-md bg-primary/10 text-primary">
                      {op.icon}
                    </div>
                    <div>
                      <CardTitle className="text-sm font-semibold">{op.title}</CardTitle>
                      <CardDescription className="text-xs mt-0.5 min-h-[2.5rem]">{op.description}</CardDescription>
                    </div>
                  </div>
                  <StatusBadge status={state.status} />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {renderFields(op, isRunning)}

                <Button
                  size="sm"
                  className="w-full gap-1.5"
                  disabled={isRunDisabled(op, isRunning) || IS_GH_PAGES_MODE}
                  onClick={() => handleRun(op)}
                >
                  {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  {IS_GH_PAGES_MODE ? "Disabled in Demo" : isRunning ? "Running…" : "Run"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Confirmation Dialog */}
      <AlertDialog open={!!confirmOp} onOpenChange={(open) => !open && setConfirmOp(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm: {confirmOp?.title}</AlertDialogTitle>
            <AlertDialogDescription>
              ⚠️ This will start a process that modifies actual data on disk. Once started, the operation window cannot be closed until it completes. Are you sure you want to proceed?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirm}>Confirm</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Execution Log Dialog (blocking while running) */}
      <Dialog open={!!activeOp} onOpenChange={(open) => { if (!open && !activeIsRunning) setActiveOp(null); }}>
        <DialogContent
          className={`sm:max-w-3xl ${activeIsRunning ? "[&>button]:hidden" : ""}`}
          onPointerDownOutside={(e) => { if (activeIsRunning) e.preventDefault(); }}
          onEscapeKeyDown={(e) => { if (activeIsRunning) e.preventDefault(); }}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              {activeIsRunning && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              {activeState?.status === "success" && <CheckCircle2 className="h-4 w-4 text-[hsl(var(--positive))]" />}
              {activeState?.status === "error" && <XCircle className="h-4 w-4 text-destructive" />}
              {activeOp?.title}
            </DialogTitle>
            <DialogDescription>
              {activeIsRunning
                ? "⚠️ Operation in progress — closing is disabled until it completes."
                : "Operation completed. You can close this dialog."}
            </DialogDescription>
          </DialogHeader>

          {activeOp?.streamable ? (
            <TerminalOutput lines={activeLogs} running={activeIsRunning} />
          ) : (
            <div className="rounded-md bg-background border border-border p-3 max-h-64 overflow-y-auto font-mono text-xs">
              {activeLogs.map((log, i) => (
                <p key={i} className="text-muted-foreground leading-relaxed whitespace-pre-wrap">{log}</p>
              ))}
              <div ref={logEndRef} />
            </div>
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
