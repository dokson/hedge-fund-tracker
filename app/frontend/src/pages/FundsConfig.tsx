import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getHedgeFunds,
  getExcludedHedgeFunds,
  generateDeleteFundCSVs,
  generateRestoreFundCSVs,
  generateAddFundCSV,
  generateHedgeFundsCSV,
  generateExcludedFundsCSV,
  saveFileToDisk,
  clearCache,
  type HedgeFund,
  type ExcludedHedgeFund,
} from "@/lib/dataService";
import { Settings2, Users, ExternalLink, Search, Trash2, AlertTriangle, Undo2, UserX, Plus, Info, Pencil, Check, X } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const SEC_CIK_URL = (cik: string) => `https://www.sec.gov/edgar/browse/?CIK=${cik}`;

const CikLink = ({ cik }: { cik: string }) => (
  <a href={SEC_CIK_URL(cik)} target="_blank" rel="noopener noreferrer"
    className="font-mono text-xs text-primary hover:underline inline-flex items-center gap-1">
    {cik} <ExternalLink className="h-2.5 w-2.5" />
  </a>
);

const ColumnHeader = ({ label, tooltip }: { label: string; tooltip: string }) => (
  <th className="text-left p-3 font-medium">
    <span className="inline-flex items-center gap-1">{label}
      <Tooltip>
        <TooltipTrigger asChild><Info className="h-3 w-3 text-muted-foreground/60 cursor-help" /></TooltipTrigger>
        <TooltipContent side="top" className="max-w-[280px] text-xs font-normal normal-case tracking-normal"><p>{tooltip}</p></TooltipContent>
      </Tooltip>
    </span>
  </th>
);

export default function FundsConfig() {
  const navigate = useNavigate();
  const [fundSearch, setFundSearch] = useState("");
  const [excludedSearch, setExcludedSearch] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [fundToDelete, setFundToDelete] = useState<HedgeFund | null>(null);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [fundToRestore, setFundToRestore] = useState<ExcludedHedgeFund | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newCik, setNewCik] = useState("");
  const [newFundName, setNewFundName] = useState("");
  const [newManager, setNewManager] = useState("");
  const [newDenomination, setNewDenomination] = useState("");
  const [newCiks, setNewCiks] = useState("");

  const [editingCik, setEditingCik] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [editingExcludedCik, setEditingExcludedCik] = useState<string | null>(null);
  const [editExcludedDraft, setEditExcludedDraft] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<"active" | "excluded">("active");

  const queryClient = useQueryClient();

  const { data: funds = [], isLoading: fundsLoading } = useQuery({ queryKey: ["hedgeFunds"], queryFn: getHedgeFunds });
  const { data: excludedFunds = [], isLoading: excludedLoading } = useQuery({ queryKey: ["excludedHedgeFunds"], queryFn: getExcludedHedgeFunds });

  const filteredFunds = useMemo(() => {
    if (!fundSearch) return funds;
    const q = fundSearch.toLowerCase();
    return funds.filter((f) => f.fund.toLowerCase().includes(q) || f.manager.toLowerCase().includes(q) || f.denomination.toLowerCase().includes(q) || f.cik.includes(q));
  }, [funds, fundSearch]);

  const filteredExcluded = useMemo(() => {
    if (!excludedSearch) return excludedFunds;
    const q = excludedSearch.toLowerCase();
    return excludedFunds.filter((f) => f.fund.toLowerCase().includes(q) || f.manager.toLowerCase().includes(q) || f.cik.includes(q) || f.url.toLowerCase().includes(q));
  }, [excludedFunds, excludedSearch]);

  const invalidateAll = () => {
    clearCache("hedge_funds");
    clearCache("excluded_hedge_funds");
    queryClient.invalidateQueries({ queryKey: ["hedgeFunds"] });
    queryClient.invalidateQueries({ queryKey: ["excludedHedgeFunds"] });
  };

  const isValidUrl = (url: string) => url.trim().startsWith("https://");

  // ── Active fund inline edit ──
  const startEdit = (f: HedgeFund) => {
    setEditingCik(f.cik);
    setEditDraft({ fund: f.fund, manager: f.manager, denomination: f.denomination, cik: f.cik, ciks: f.ciks });
  };
  const cancelEdit = () => { setEditingCik(null); setEditDraft({}); };
  const saveEdit = async () => {
    if (!editingCik) return;
    const updated = funds.map((f) =>
      f.cik === editingCik
        ? { ...f, fund: editDraft.fund, manager: editDraft.manager, denomination: editDraft.denomination, cik: editDraft.cik, ciks: editDraft.ciks }
        : f
    );
    const csv = generateHedgeFundsCSV(updated);
    try {
      await saveFileToDisk(csv, "hedge_funds.csv");
      toast.success("Fund updated");
      invalidateAll();
    } catch (e: any) {
      toast.error(e.message);
    }
    setEditingCik(null);
    setEditDraft({});
  };

  // ── Excluded fund inline edit ──
  const startExcludedEdit = (f: ExcludedHedgeFund) => {
    setEditingExcludedCik(f.cik);
    setEditExcludedDraft({ fund: f.fund, manager: f.manager, denomination: f.denomination, cik: f.cik, ciks: f.ciks, url: f.url });
  };
  const cancelExcludedEdit = () => { setEditingExcludedCik(null); setEditExcludedDraft({}); };
  const saveExcludedEdit = async () => {
    if (!editingExcludedCik) return;
    if (editExcludedDraft.url && !isValidUrl(editExcludedDraft.url)) {
      toast.error("Website URL must start with https://");
      return;
    }
    const updated = excludedFunds.map((f) =>
      f.cik === editingExcludedCik
        ? { ...f, fund: editExcludedDraft.fund, manager: editExcludedDraft.manager, denomination: editExcludedDraft.denomination, cik: editExcludedDraft.cik, ciks: editExcludedDraft.ciks, url: editExcludedDraft.url }
        : f
    );
    const csv = generateExcludedFundsCSV(updated);
    try {
      await saveFileToDisk(csv, "excluded_hedge_funds.csv");
      toast.success("Excluded fund updated");
      invalidateAll();
    } catch (e: any) {
      toast.error(e.message);
    }
    setEditingExcludedCik(null);
    setEditExcludedDraft({});
  };

  const handleConfirmDelete = async () => {
    if (!fundToDelete || !isValidUrl(websiteUrl)) return;
    const { hedgeFundsCSV, excludedCSV } = generateDeleteFundCSVs(funds, excludedFunds, fundToDelete, websiteUrl.trim());
    try {
      await saveFileToDisk(hedgeFundsCSV, "hedge_funds.csv");
      await saveFileToDisk(excludedCSV, "excluded_hedge_funds.csv");
      toast.success(`"${fundToDelete.fund}" moved to excluded`);
      invalidateAll();
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteDialogOpen(false);
    setFundToDelete(null);
  };

  const handleConfirmRestore = async () => {
    if (!fundToRestore) return;
    const { hedgeFundsCSV, excludedCSV } = generateRestoreFundCSVs(funds, excludedFunds, fundToRestore);
    try {
      await saveFileToDisk(hedgeFundsCSV, "hedge_funds.csv");
      await saveFileToDisk(excludedCSV, "excluded_hedge_funds.csv");
      toast.success(`"${fundToRestore.fund}" restored to active`);
      invalidateAll();
    } catch (e: any) {
      toast.error(e.message);
    }
    setRestoreDialogOpen(false);
    setFundToRestore(null);
  };

  const resetAddForm = () => {
    setNewCik(""); setNewFundName(""); setNewManager(""); setNewDenomination(""); setNewCiks("");
  };

  const handleAddFund = async () => {
    if (!newCik.trim() || !newFundName.trim() || !newManager.trim()) return;
    const newFund: HedgeFund = {
      cik: newCik.trim(),
      fund: newFundName.trim(),
      manager: newManager.trim(),
      denomination: newDenomination.trim(),
      ciks: newCiks.trim() || newCik.trim(),
    };
    const csv = generateAddFundCSV(funds, newFund);
    try {
      await saveFileToDisk(csv, "hedge_funds.csv");
      toast.success(`"${newFundName.trim()}" added`);
      invalidateAll();
    } catch (e: any) {
      toast.error(e.message);
    }
    setAddDialogOpen(false);
    resetAddForm();
  };

  const InlineInput = useMemo(() => {
    const Comp = ({ value, field, draft, setDraft, className = "" }: {
      value: string; field: string; draft: Record<string, string>;
      setDraft: React.Dispatch<React.SetStateAction<Record<string, string>>>; className?: string;
    }) => (
      <Input
        value={draft[field] ?? value}
        onChange={(e) => {
          let val = e.target.value;
          if (field === "cik") val = val.replace(/[^0-9]/g, "");
          if (field === "ciks") val = val.replace(/[^0-9,]/g, "");
          setDraft((prev) => ({ ...prev, [field]: val }));
        }}
        className={`h-7 text-xs bg-background border-border ${className}`}
      />
    );
    return Comp;
  }, []);

  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Settings2 className="h-6 w-6" /> Hedge Funds Configuration
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage the monitored hedge funds. Click the edit icon to modify a fund inline.
        </p>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-border">
        <button
          onClick={() => setActiveTab("active")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "active" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Users className="h-3.5 w-3.5" /> Active Funds
          <Badge variant="secondary" className="text-[10px] ml-1">{funds.length}</Badge>
        </button>
        <button
          onClick={() => setActiveTab("excluded")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "excluded" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <UserX className="h-3.5 w-3.5" /> Excluded
          <Badge variant="secondary" className="text-[10px] ml-1">{excludedFunds.length}</Badge>
        </button>
      </div>

      {activeTab === "active" ? (
        /* ── Active Funds ── */
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input placeholder="Search fund, manager, CIK…" value={fundSearch} onChange={(e) => setFundSearch(e.target.value)} className="pl-8 bg-card border-border" />
            </div>
            <span className="text-xs text-muted-foreground">{filteredFunds.length} / {funds.length} funds</span>
            <Button size="sm" className="gap-1.5 ml-auto" onClick={() => { resetAddForm(); setAddDialogOpen(true); }}>
              <Plus className="h-3.5 w-3.5" /> Add Fund
            </Button>
          </div>
          <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            📄 Source: <code className="font-mono bg-muted px-1 py-0.5 rounded">database/hedge_funds.csv</code>
          </div>

          {fundsLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
          ) : (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="overflow-auto max-h-[60vh]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card z-10">
                    <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                      <th className="text-right p-3 font-medium w-12">#</th>
                      <ColumnHeader label="Fund" tooltip="Short name used to generate quarterly file names." />
                      <ColumnHeader label="Manager" tooltip="Portfolio manager as listed in official fund filings." />
                      <ColumnHeader label="Denomination" tooltip="Full legal name as it appears in SEC filings. Used to identify positions in non-quarterly filings that may contain multiple institutional entities." />
                      <ColumnHeader label="CIK" tooltip="Central Index Key — unique SEC identifier for filing entities." />
                      <ColumnHeader label="CIKs" tooltip="Comma-separated list of additional CIKs associated with this fund (e.g. for related filing entities)." />
                      <th className="text-right p-3 font-medium w-24"></th>
                    </tr>
                  </thead>
                    <tbody>
                      {filteredFunds.map((f, idx) => {
                        const isEditing = editingCik === f.cik;
                        return (
                          <tr key={f.cik} className="data-table-row group">
                            <td className="p-3 text-right text-muted-foreground font-mono text-xs">{idx + 1}</td>
                            {isEditing ? (
                              <>
                                <td className="p-2"><InlineInput value={f.fund} field="fund" draft={editDraft} setDraft={setEditDraft} /></td>
                                <td className="p-2"><InlineInput value={f.manager} field="manager" draft={editDraft} setDraft={setEditDraft} /></td>
                                <td className="p-2"><InlineInput value={f.denomination} field="denomination" draft={editDraft} setDraft={setEditDraft} /></td>
                                <td className="p-2"><InlineInput value={f.cik} field="cik" draft={editDraft} setDraft={setEditDraft} className="font-mono" /></td>
                                <td className="p-2"><InlineInput value={f.ciks} field="ciks" draft={editDraft} setDraft={setEditDraft} className="font-mono" /></td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button variant="ghost" size="icon" className="h-7 w-7 text-green-600 hover:text-green-700 hover:bg-green-500/10" onClick={saveEdit} title="Save">
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground" onClick={cancelEdit} title="Cancel">
                                    <X className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="p-3 font-medium fund-link cursor-pointer" onClick={() => navigate(`/funds/${encodeURIComponent(f.fund)}`)}>{f.fund}</td>
                                <td className="p-3 text-muted-foreground fund-link cursor-pointer" onClick={() => navigate(`/funds/${encodeURIComponent(f.fund)}`)}>{f.manager}</td>
                                <td className="p-3 text-muted-foreground text-xs max-w-[250px] truncate fund-link cursor-pointer" onClick={() => navigate(`/funds/${encodeURIComponent(f.fund)}`)}>{f.denomination}</td>
                                <td className="p-3"><CikLink cik={f.cik} /></td>
                                <td className="p-3 font-mono text-xs text-muted-foreground max-w-[150px] truncate">{f.ciks || "—"}</td>
                                <td className="p-3 text-right whitespace-nowrap">
                                  <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground" onClick={() => startEdit(f)} title="Edit fund">
                                    <Pencil className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10" onClick={() => { setFundToDelete(f); setWebsiteUrl(""); setDeleteDialogOpen(true); }} title="Delete fund">
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            )}
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : activeTab === "excluded" ? (
        /* ── Excluded Funds ── */
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input placeholder="Search excluded fund, manager, URL…" value={excludedSearch} onChange={(e) => setExcludedSearch(e.target.value)} className="pl-8 bg-card border-border" />
            </div>
            <span className="text-xs text-muted-foreground">{filteredExcluded.length} / {excludedFunds.length} excluded</span>
          </div>

          <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            📄 Source: <code className="font-mono bg-muted px-1 py-0.5 rounded">database/excluded_hedge_funds.csv</code>
          </div>

          {excludedLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
          ) : filteredExcluded.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">No excluded funds found.</div>
          ) : (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="overflow-auto max-h-[60vh]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card z-10">
                    <tr className="border-b border-border text-xs text-muted-foreground uppercase tracking-wider">
                      <th className="text-right p-3 font-medium w-12">#</th>
                      <ColumnHeader label="Fund" tooltip="Short name used to generate quarterly file names." />
                      <ColumnHeader label="Manager" tooltip="Portfolio manager as listed in official fund filings." />
                      <ColumnHeader label="Denomination" tooltip="Full legal name as it appears in SEC filings. Used to identify positions in non-quarterly filings that may contain multiple institutional entities." />
                      <ColumnHeader label="CIK" tooltip="Central Index Key — unique SEC identifier for filing entities." />
                      <ColumnHeader label="CIKs" tooltip="Comma-separated list of additional CIKs associated with this fund." />
                      <ColumnHeader label="Website" tooltip="Official website URL of the excluded fund. Must start with https://." />
                      <th className="text-right p-3 font-medium w-24"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredExcluded.map((f, idx) => {
                        const isEditing = editingExcludedCik === f.cik;
                        return (
                          <tr key={f.cik} className="data-table-row group">
                            <td className="p-3 text-right text-muted-foreground font-mono text-xs">{idx + 1}</td>
                            {isEditing ? (
                              <>
                                <td className="p-2"><InlineInput value={f.fund} field="fund" draft={editExcludedDraft} setDraft={setEditExcludedDraft} /></td>
                                <td className="p-2"><InlineInput value={f.manager} field="manager" draft={editExcludedDraft} setDraft={setEditExcludedDraft} /></td>
                                <td className="p-2"><InlineInput value={f.denomination} field="denomination" draft={editExcludedDraft} setDraft={setEditExcludedDraft} /></td>
                                <td className="p-2"><InlineInput value={f.cik} field="cik" draft={editExcludedDraft} setDraft={setEditExcludedDraft} className="font-mono" /></td>
                                <td className="p-2"><InlineInput value={f.ciks} field="ciks" draft={editExcludedDraft} setDraft={setEditExcludedDraft} className="font-mono" /></td>
                                <td className="p-2"><InlineInput value={f.url} field="url" draft={editExcludedDraft} setDraft={setEditExcludedDraft} /></td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button variant="ghost" size="icon" className="h-7 w-7 text-green-600 hover:text-green-700 hover:bg-green-500/10" onClick={saveExcludedEdit} title="Save">
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground" onClick={cancelExcludedEdit} title="Cancel">
                                    <X className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="p-3 font-medium">{f.fund}</td>
                                <td className="p-3 text-muted-foreground">{f.manager}</td>
                                <td className="p-3 text-muted-foreground text-xs max-w-[200px] truncate">{f.denomination}</td>
                                <td className="p-3"><CikLink cik={f.cik} /></td>
                                <td className="p-3 font-mono text-xs text-muted-foreground max-w-[150px] truncate">{f.ciks || "—"}</td>
                                <td className="p-3">
                                  {f.url ? (
                                    <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline inline-flex items-center gap-1 max-w-[180px] truncate">
                                      {f.url.replace(/^https?:\/\/(www\.)?/, "")} <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                                    </a>
                                  ) : <span className="text-xs text-muted-foreground">—</span>}
                                </td>
                                <td className="p-3 text-right whitespace-nowrap">
                                  <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground" onClick={() => startExcludedEdit(f)} title="Edit fund">
                                    <Pencil className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-primary hover:text-primary hover:bg-primary/10" onClick={() => { setFundToRestore(f); setRestoreDialogOpen(true); }} title="Restore fund">
                                    <Undo2 className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            )}
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* ── Delete Dialog ── */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive"><AlertTriangle className="h-5 w-5" /> Delete Hedge Fund</DialogTitle>
            <DialogDescription>This will move <strong>{fundToDelete?.fund}</strong> to the excluded list.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1 text-sm">
              <div><span className="text-muted-foreground">Fund:</span> {fundToDelete?.fund}</div>
              <div><span className="text-muted-foreground">Manager:</span> {fundToDelete?.manager}</div>
              <div><span className="text-muted-foreground">CIK:</span> <span className="font-mono text-xs">{fundToDelete?.cik}</span></div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="website-url">Website URL</Label>
              <Input id="website-url" placeholder="https://www.example.com" value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)} className="bg-card border-border" />
              <p className="text-xs text-muted-foreground">Must start with <code>https://</code>.</p>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={!isValidUrl(websiteUrl)} onClick={handleConfirmDelete}>Confirm Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Restore Dialog ── */}
      <Dialog open={restoreDialogOpen} onOpenChange={setRestoreDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Undo2 className="h-5 w-5" /> Restore Hedge Fund</DialogTitle>
            <DialogDescription>This will move <strong>{fundToRestore?.fund}</strong> back to the active list.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1 text-sm">
              <div><span className="text-muted-foreground">Fund:</span> {fundToRestore?.fund}</div>
              <div><span className="text-muted-foreground">Manager:</span> {fundToRestore?.manager}</div>
              <div><span className="text-muted-foreground">CIK:</span> <span className="font-mono text-xs">{fundToRestore?.cik}</span></div>
              {fundToRestore?.url && <div><span className="text-muted-foreground">Website (will be removed):</span> <span className="text-xs line-through">{fundToRestore.url}</span></div>}
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRestoreDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleConfirmRestore}>Confirm Restore</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Add Fund Dialog ── */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Plus className="h-5 w-5" /> Add Hedge Fund</DialogTitle>
            <DialogDescription>Add a new fund to the monitored list.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="new-cik">CIK</Label>
              <Input id="new-cik" placeholder="e.g. 0001067983" value={newCik} onChange={(e) => setNewCik(e.target.value.replace(/[^0-9]/g, ""))} className="bg-card border-border font-mono text-sm" />
              <p className="text-xs text-muted-foreground">Central Index Key — unique SEC identifier for filing entities.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-fund">Fund Name</Label>
              <Input id="new-fund" placeholder="e.g. Berkshire Hathaway" value={newFundName} onChange={(e) => setNewFundName(e.target.value)} className="bg-card border-border" />
              <p className="text-xs text-muted-foreground">Short name used to generate quarterly file names.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-manager">Manager</Label>
              <Input id="new-manager" placeholder="e.g. Warren Buffett" value={newManager} onChange={(e) => setNewManager(e.target.value)} className="bg-card border-border" />
              <p className="text-xs text-muted-foreground">Portfolio manager as listed in official fund filings.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-denomination">Denomination</Label>
              <Input id="new-denomination" placeholder="e.g. Berkshire Hathaway Inc." value={newDenomination} onChange={(e) => setNewDenomination(e.target.value)} className="bg-card border-border" />
              <p className="text-xs text-muted-foreground">Full legal name from SEC filings. Used to identify positions in non-quarterly filings containing multiple institutional entities.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-ciks">CIKs (optional)</Label>
              <Input id="new-ciks" placeholder="Defaults to CIK if empty" value={newCiks} onChange={(e) => setNewCiks(e.target.value.replace(/[^0-9,]/g, ""))} className="bg-card border-border font-mono text-sm" />
              <p className="text-xs text-muted-foreground">Comma-separated list of related CIKs, if different from primary.</p>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
            <Button disabled={!newCik.trim() || !newFundName.trim() || !newManager.trim()} onClick={handleAddFund}>Add Fund</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
