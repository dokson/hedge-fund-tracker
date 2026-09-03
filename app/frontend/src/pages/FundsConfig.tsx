import { useState, useMemo } from "react";
import { useNavigate } from "react-router";
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
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { matchesQuery } from "@/lib/utils";
import { fundPath, ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import {
  Settings2,
  ExternalLink,
  Trash2,
  AlertTriangle,
  Undo2,
  Plus,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { SearchInput } from "@/components/ui/SearchInput";
import { ColumnHeader } from "@/components/ui/ColumnHeader";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/LoadingState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const SEC_CIK_URL = (cik: string) => `https://www.sec.gov/edgar/browse/?CIK=${cik}`;

const EDIT_FIELDS = [
  ["fund", "Fund"],
  ["manager", "Manager"],
  ["denomination", "Denomination"],
  ["cik", "CIK"],
  ["ciks", "CIKs"],
  ["url", "Website"],
] as const;

const FIELD_LABEL: Record<string, string> = Object.fromEntries(EDIT_FIELDS);

function InlineInput({
  value,
  field,
  draft,
  setDraft,
  className = "",
  id,
}: {
  value: string;
  field: string;
  draft: Record<string, string>;
  setDraft: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  className?: string;
  id?: string;
}) {
  return (
    <Input
      id={id}
      aria-label={id ? undefined : FIELD_LABEL[field]}
      value={draft[field] ?? value}
      onChange={(e) => {
        let val = e.target.value;
        if (field === "cik") val = val.replace(/[^0-9]/g, "");
        if (field === "ciks") val = val.replace(/[^0-9,]/g, "");
        setDraft((prev) => ({ ...prev, [field]: val }));
      }}
      className={`h-7 text-xs ${className}`}
    />
  );
}

const CikLink = ({ cik }: { cik: string }) => (
  <a
    href={SEC_CIK_URL(cik)}
    target="_blank"
    rel="noopener noreferrer"
    className="font-mono text-xs text-primary-text hover:underline inline-flex items-center gap-1"
  >
    {cik} <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
  </a>
);

type FundRow = {
  fund: string;
  manager: string;
  denomination: string;
  cik: string;
  ciks: string;
  url: string;
};

/**
 * Mobile card for one funds-config row, shared by the Active and Excluded tabs.
 * The 8-column admin table can't fit a phone, so below `md` each fund collapses
 * to a frame row. Inline editing reuses the same draft state, stacked vertically.
 */
function FundConfigCard({
  f,
  rank,
  mode,
  readOnly,
  isEditing,
  draft,
  setDraft,
  isDraftValid,
  onStartEdit,
  onSave,
  onCancel,
  onSecondary,
  onOpen,
}: {
  f: FundRow;
  rank: number;
  mode: "active" | "excluded";
  readOnly: boolean;
  isEditing: boolean;
  draft: Record<string, string>;
  setDraft: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  isDraftValid: boolean;
  onStartEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onSecondary: () => void;
  onOpen?: () => void;
}) {
  if (isEditing) {
    return (
      <div className="border-b border-border py-3 space-y-2.5">
        {EDIT_FIELDS.map(([field, label]) => (
          <div key={field} className="space-y-1">
            <Label htmlFor={`edit-${f.cik}-${field}`} className="control-label !text-[11px]">
              {label}
            </Label>
            <InlineInput
              id={`edit-${f.cik}-${field}`}
              value={f[field]}
              field={field}
              draft={draft}
              setDraft={setDraft}
              className={field === "cik" || field === "ciks" ? "font-mono w-full" : "w-full"}
            />
          </div>
        ))}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" onClick={onSave} disabled={!isDraftValid}>
            <Check className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Save
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-border py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {onOpen ? (
            <button
              type="button"
              onClick={onOpen}
              className="font-medium fund-link text-left truncate max-w-full block"
            >
              {f.fund}
            </button>
          ) : (
            <p className="font-medium truncate">{f.fund}</p>
          )}
          <p className="text-xs text-muted-foreground truncate">{f.manager}</p>
        </div>
        <span className="font-mono text-xs text-muted-foreground shrink-0">#{rank}</span>
      </div>
      {f.denomination && (
        <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{f.denomination}</p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <CikLink cik={f.cik} />
        {f.url && (
          <a
            href={f.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-text hover:underline inline-flex items-center gap-1 min-w-0 max-w-[200px] truncate"
          >
            {f.url.replace(/^https?:\/\/(www\.)?/, "")}
            <ExternalLink className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
          </a>
        )}
      </div>
      {!readOnly && (
        <div className="mt-3 flex gap-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={onStartEdit}>
            <Pencil className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Edit
          </Button>
          {mode === "active" ? (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-negative hover:text-negative"
              onClick={onSecondary}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Delete
            </Button>
          ) : (
            <Button variant="outline" size="sm" className="flex-1" onClick={onSecondary}>
              <Undo2 className="h-3.5 w-3.5 mr-1" aria-hidden="true" /> Restore
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export default function FundsConfig() {
  usePageMeta({
    title: pageTitle("Funds Configuration"),
    description:
      "Local configuration of the tracked hedge fund roster: add, exclude and restore the funds whose SEC filings are ingested.",
    canonical: canonicalUrl(ROUTES.fundsConfig),
  });

  const navigate = useNavigate();
  const [fundSearch, setFundSearch] = useState("");
  const [excludedSearch, setExcludedSearch] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [fundToDelete, setFundToDelete] = useState<HedgeFund | null>(null);
  const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
  const [fundToRestore, setFundToRestore] = useState<ExcludedHedgeFund | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newCik, setNewCik] = useState("");
  const [newFundName, setNewFundName] = useState("");
  const [newManager, setNewManager] = useState("");
  const [newDenomination, setNewDenomination] = useState("");
  const [newCiks, setNewCiks] = useState("");
  const [newUrl, setNewUrl] = useState("");

  const [editingCik, setEditingCik] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Record<string, string>>({});
  const [editingExcludedCik, setEditingExcludedCik] = useState<string | null>(null);
  const [editExcludedDraft, setEditExcludedDraft] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<"active" | "excluded">("active");

  const queryClient = useQueryClient();

  const { data: funds = [], isLoading: fundsLoading } = useQuery({
    queryKey: ["hedgeFunds"],
    queryFn: getHedgeFunds,
  });
  const { data: excludedFunds = [], isLoading: excludedLoading } = useQuery({
    queryKey: ["excludedHedgeFunds"],
    queryFn: getExcludedHedgeFunds,
  });

  const filteredFunds = useMemo(
    () =>
      funds.filter((f) =>
        matchesQuery(fundSearch, f.fund, f.manager, f.denomination, f.cik, f.url),
      ),
    [funds, fundSearch],
  );

  const filteredExcluded = useMemo(
    () =>
      excludedFunds.filter((f) =>
        matchesQuery(excludedSearch, f.fund, f.manager, f.denomination, f.cik, f.url),
      ),
    [excludedFunds, excludedSearch],
  );

  const invalidateAll = () => {
    clearCache("hedge_funds");
    clearCache("excluded_hedge_funds");
    void queryClient.invalidateQueries({ queryKey: ["hedgeFunds"] });
    void queryClient.invalidateQueries({ queryKey: ["excludedHedgeFunds"] });
  };

  const isValidUrl = (url: string) => url.trim().startsWith("https://");

  // ── Active fund inline edit ──
  const startEdit = (f: HedgeFund) => {
    setEditingCik(f.cik);
    setEditDraft({
      fund: f.fund,
      manager: f.manager,
      denomination: f.denomination,
      cik: f.cik,
      ciks: f.ciks,
      url: f.url,
    });
  };
  const cancelEdit = () => {
    setEditingCik(null);
    setEditDraft({});
  };
  const isEditDraftValid = () =>
    !!(
      editDraft.fund?.trim() &&
      editDraft.manager?.trim() &&
      editDraft.denomination?.trim() &&
      editDraft.cik?.trim()
    );
  const saveEdit = async () => {
    if (!editingCik || !isEditDraftValid()) return;
    if (editDraft.url && !isValidUrl(editDraft.url)) {
      toast.error("Website URL must start with https://");
      return;
    }
    const updated = funds.map((f) =>
      f.cik === editingCik
        ? {
            ...f,
            fund: editDraft.fund,
            manager: editDraft.manager,
            denomination: editDraft.denomination,
            cik: editDraft.cik,
            ciks: editDraft.ciks,
            url: editDraft.url || "",
          }
        : f,
    );
    const csv = generateHedgeFundsCSV(updated);
    try {
      await saveFileToDisk(csv, "hedge_funds.csv");
      toast.success("Fund updated");
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setEditingCik(null);
    setEditDraft({});
  };

  // ── Excluded fund inline edit ──
  const startExcludedEdit = (f: ExcludedHedgeFund) => {
    setEditingExcludedCik(f.cik);
    setEditExcludedDraft({
      fund: f.fund,
      manager: f.manager,
      denomination: f.denomination,
      cik: f.cik,
      ciks: f.ciks,
      url: f.url,
    });
  };
  const cancelExcludedEdit = () => {
    setEditingExcludedCik(null);
    setEditExcludedDraft({});
  };
  const isExcludedDraftValid = () =>
    !!(
      editExcludedDraft.fund?.trim() &&
      editExcludedDraft.manager?.trim() &&
      editExcludedDraft.denomination?.trim() &&
      editExcludedDraft.cik?.trim()
    );
  const saveExcludedEdit = async () => {
    if (!editingExcludedCik || !isExcludedDraftValid()) return;
    if (editExcludedDraft.url && !isValidUrl(editExcludedDraft.url)) {
      toast.error("Website URL must start with https://");
      return;
    }
    const updated = excludedFunds.map((f) =>
      f.cik === editingExcludedCik
        ? {
            ...f,
            fund: editExcludedDraft.fund,
            manager: editExcludedDraft.manager,
            denomination: editExcludedDraft.denomination,
            cik: editExcludedDraft.cik,
            ciks: editExcludedDraft.ciks,
            url: editExcludedDraft.url,
          }
        : f,
    );
    const csv = generateExcludedFundsCSV(updated);
    try {
      await saveFileToDisk(csv, "excluded_hedge_funds.csv");
      toast.success("Excluded fund updated");
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setEditingExcludedCik(null);
    setEditExcludedDraft({});
  };

  const handleConfirmDelete = async () => {
    if (!fundToDelete) return;
    const { hedgeFundsCSV, excludedCSV } = generateDeleteFundCSVs(
      funds,
      excludedFunds,
      fundToDelete,
    );
    try {
      await saveFileToDisk(hedgeFundsCSV, "hedge_funds.csv");
      await saveFileToDisk(excludedCSV, "excluded_hedge_funds.csv");
      toast.success(`"${fundToDelete.fund}" moved to excluded`);
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setDeleteDialogOpen(false);
    setFundToDelete(null);
  };

  const handleConfirmRestore = async () => {
    if (!fundToRestore) return;
    const { hedgeFundsCSV, excludedCSV } = generateRestoreFundCSVs(
      funds,
      excludedFunds,
      fundToRestore,
    );
    try {
      await saveFileToDisk(hedgeFundsCSV, "hedge_funds.csv");
      await saveFileToDisk(excludedCSV, "excluded_hedge_funds.csv");
      toast.success(`"${fundToRestore.fund}" restored to active`);
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setRestoreDialogOpen(false);
    setFundToRestore(null);
  };

  const resetAddForm = () => {
    setNewCik("");
    setNewFundName("");
    setNewManager("");
    setNewDenomination("");
    setNewCiks("");
    setNewUrl("");
  };

  const handleAddFund = async () => {
    if (!newCik.trim() || !newFundName.trim() || !newManager.trim()) return;
    if (newUrl.trim() && !isValidUrl(newUrl)) {
      toast.error("Website URL must start with https://");
      return;
    }
    const newFund: HedgeFund = {
      cik: newCik.trim(),
      fund: newFundName.trim(),
      manager: newManager.trim(),
      denomination: newDenomination.trim(),
      ciks: newCiks.trim() || newCik.trim(),
      url: newUrl.trim(),
    };
    const csv = generateAddFundCSV(funds, newFund);
    try {
      await saveFileToDisk(csv, "hedge_funds.csv");
      toast.success(`"${newFundName.trim()}" added`);
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setAddDialogOpen(false);
    resetAddForm();
  };

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <Settings2 className="h-5 w-5 text-muted-foreground" aria-hidden="true" /> Hedge Funds
          Configuration
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          {IS_GH_PAGES_MODE
            ? "View the monitored hedge funds. This is a read-only view of the bundled data."
            : "Manage the monitored hedge funds. Click the edit icon to modify a fund inline."}
        </p>
      </div>

      {IS_GH_PAGES_MODE && (
        <p className="text-sm text-muted-foreground" role="note">
          Read-only mode. To modify the hedge funds list, run the application locally.
        </p>
      )}

      {/* Underline tabs: active gets the primary rule and the text colour. */}
      <div role="tablist" className="flex items-stretch gap-1 border-b border-border">
        {(
          [
            ["active", "Active Funds", funds.length],
            ["excluded", "Excluded", excludedFunds.length],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            onClick={() => setActiveTab(id)}
            className={`h-9 px-3 -mb-px border-b-2 text-[13px] transition-colors duration-[120ms] cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring ${
              activeTab === id
                ? "border-primary text-foreground font-medium"
                : "border-transparent text-muted-foreground font-normal hover:text-foreground"
            }`}
          >
            {label} <span className="ml-1 text-muted-foreground tabular-nums">{count}</span>
          </button>
        ))}
      </div>

      {activeTab === "active" ? (
        /* ── Active Funds ── */
        <div className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <SearchInput
              label="Search fund, manager, CIK"
              size="sm"
              value={fundSearch}
              onChange={(e) => setFundSearch(e.target.value)}
              wrapperClassName="flex-1 min-w-0 sm:max-w-sm"
            />
            <span className="text-xs text-muted-foreground">
              {filteredFunds.length} / {funds.length} funds
            </span>
            {!IS_GH_PAGES_MODE && (
              <Button
                size="sm"
                className="gap-1.5 ml-auto"
                onClick={() => {
                  resetAddForm();
                  setAddDialogOpen(true);
                }}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add Fund
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Source: <code className="font-mono bg-muted px-1 py-0.5">database/hedge_funds.csv</code>
          </p>

          {fundsLoading ? (
            <LoadingState message="Loading…" size="sm" />
          ) : (
            <>
              {/* Mobile: card list */}
              <div className="md:hidden border-t border-border">
                {filteredFunds.map((f, idx) => (
                  <FundConfigCard
                    key={f.cik}
                    f={f}
                    rank={idx + 1}
                    mode="active"
                    readOnly={IS_GH_PAGES_MODE}
                    isEditing={editingCik === f.cik}
                    draft={editDraft}
                    setDraft={setEditDraft}
                    isDraftValid={isEditDraftValid()}
                    onStartEdit={() => startEdit(f)}
                    onSave={saveEdit}
                    onCancel={cancelEdit}
                    onSecondary={() => {
                      setFundToDelete(f);
                      setDeleteDialogOpen(true);
                    }}
                    onOpen={() => navigate(fundPath(f.fund))}
                  />
                ))}
              </div>

              {/* Desktop: full table */}
              <div className="frame hidden md:block">
                <div className="overflow-auto max-h-[60vh]">
                  <table className="w-full text-sm" aria-label="Active funds">
                    <thead className="sticky top-0 bg-card z-10">
                      <tr className="text-xs">
                        <th scope="col" className="text-right p-3 w-12">
                          #
                        </th>
                        <ColumnHeader
                          label="Fund"
                          tooltip="Short name used to generate quarterly file names."
                        />
                        <ColumnHeader
                          label="Manager"
                          tooltip="Portfolio manager as listed in official fund filings."
                        />
                        <ColumnHeader
                          label="Denomination"
                          tooltip="Full legal name as it appears in SEC filings. Used to identify positions in non-quarterly filings that may contain multiple institutional entities."
                        />
                        <ColumnHeader
                          label="CIK"
                          tooltip="Central Index Key — unique SEC identifier for filing entities."
                        />
                        <ColumnHeader
                          label="CIKs"
                          tooltip="Comma-separated list of additional CIKs associated with this fund (e.g. for related filing entities)."
                        />
                        <ColumnHeader
                          label="Website"
                          tooltip="Official fund website. Optional, must start with https://."
                        />
                        {!IS_GH_PAGES_MODE && (
                          <th scope="col" className="text-right p-3 w-24">
                            <span className="sr-only">Actions</span>
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredFunds.map((f, idx) => {
                        const isEditing = editingCik === f.cik;
                        return (
                          <tr key={f.cik} className="data-table-row group">
                            <td className="p-3 text-right text-muted-foreground font-mono text-xs">
                              {idx + 1}
                            </td>
                            {isEditing ? (
                              <>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.fund}
                                    field="fund"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.manager}
                                    field="manager"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.denomination}
                                    field="denomination"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.cik}
                                    field="cik"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.ciks}
                                    field="ciks"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.url}
                                    field="url"
                                    draft={editDraft}
                                    setDraft={setEditDraft}
                                  />
                                </td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-positive hover:text-positive hover:bg-positive/10"
                                    onClick={saveEdit}
                                    title="Save"
                                    aria-label="Save fund"
                                    disabled={!isEditDraftValid()}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                    onClick={cancelEdit}
                                    title="Cancel"
                                    aria-label="Cancel edit"
                                  >
                                    <X className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="p-3">
                                  <button
                                    type="button"
                                    className="fund-link text-left"
                                    onClick={() => navigate(fundPath(f.fund))}
                                  >
                                    {f.fund}
                                  </button>
                                </td>
                                <td
                                  className="p-3 text-muted-foreground fund-link cursor-pointer"
                                  onClick={() => navigate(fundPath(f.fund))}
                                >
                                  {f.manager}
                                </td>
                                <td
                                  className="p-3 text-muted-foreground text-xs max-w-[250px] truncate fund-link cursor-pointer"
                                  onClick={() => navigate(fundPath(f.fund))}
                                >
                                  {f.denomination}
                                </td>
                                <td className="p-3">
                                  <CikLink cik={f.cik} />
                                </td>
                                <td className="p-3 font-mono text-xs text-muted-foreground max-w-[150px] truncate">
                                  {f.ciks || "—"}
                                </td>
                                <td className="p-3">
                                  {f.url ? (
                                    <a
                                      href={f.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-primary-text hover:underline inline-flex items-center gap-1 max-w-[180px] truncate"
                                    >
                                      {f.url.replace(/^https?:\/\/(www\.)?/, "")}{" "}
                                      <ExternalLink
                                        className="h-2.5 w-2.5 shrink-0"
                                        aria-hidden="true"
                                      />
                                    </a>
                                  ) : (
                                    <span className="text-xs text-muted-foreground">—</span>
                                  )}
                                </td>
                                {!IS_GH_PAGES_MODE && (
                                  <td className="p-3 text-right whitespace-nowrap">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 group-focus-within:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                                      onClick={() => startEdit(f)}
                                      title="Edit fund"
                                      aria-label={`Edit ${f.fund}`}
                                    >
                                      <Pencil className="h-3.5 w-3.5" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 group-focus-within:opacity-100 transition-opacity text-negative hover:text-negative hover:bg-negative/10"
                                      onClick={() => {
                                        setFundToDelete(f);
                                        setDeleteDialogOpen(true);
                                      }}
                                      title="Delete fund"
                                      aria-label={`Delete ${f.fund}`}
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </Button>
                                  </td>
                                )}
                              </>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      ) : activeTab === "excluded" ? (
        /* ── Excluded Funds ── */
        <div className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <SearchInput
              label="Search excluded fund, manager, URL"
              size="sm"
              value={excludedSearch}
              onChange={(e) => setExcludedSearch(e.target.value)}
              wrapperClassName="flex-1 min-w-0 sm:max-w-sm"
            />
            <span className="text-xs text-muted-foreground">
              {filteredExcluded.length} / {excludedFunds.length} excluded
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            Source:{" "}
            <code className="font-mono bg-muted px-1 py-0.5">
              database/excluded_hedge_funds.csv
            </code>
          </p>

          {excludedLoading ? (
            <LoadingState message="Loading…" size="sm" />
          ) : filteredExcluded.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              No excluded funds found.
            </div>
          ) : (
            <>
              {/* Mobile: card list */}
              <div className="md:hidden border-t border-border">
                {filteredExcluded.map((f, idx) => (
                  <FundConfigCard
                    key={f.cik}
                    f={f}
                    rank={idx + 1}
                    mode="excluded"
                    readOnly={IS_GH_PAGES_MODE}
                    isEditing={editingExcludedCik === f.cik}
                    draft={editExcludedDraft}
                    setDraft={setEditExcludedDraft}
                    isDraftValid={isExcludedDraftValid()}
                    onStartEdit={() => startExcludedEdit(f)}
                    onSave={saveExcludedEdit}
                    onCancel={cancelExcludedEdit}
                    onSecondary={() => {
                      setFundToRestore(f);
                      setRestoreDialogOpen(true);
                    }}
                  />
                ))}
              </div>

              {/* Desktop: full table */}
              <div className="frame hidden md:block">
                <div className="overflow-auto max-h-[60vh]">
                  <table className="w-full text-sm" aria-label="Excluded funds">
                    <thead className="sticky top-0 bg-card z-10">
                      <tr className="text-xs">
                        <th scope="col" className="text-right p-3 w-12">
                          #
                        </th>
                        <ColumnHeader
                          label="Fund"
                          tooltip="Short name used to generate quarterly file names."
                        />
                        <ColumnHeader
                          label="Manager"
                          tooltip="Portfolio manager as listed in official fund filings."
                        />
                        <ColumnHeader
                          label="Denomination"
                          tooltip="Full legal name as it appears in SEC filings. Used to identify positions in non-quarterly filings that may contain multiple institutional entities."
                        />
                        <ColumnHeader
                          label="CIK"
                          tooltip="Central Index Key — unique SEC identifier for filing entities."
                        />
                        <ColumnHeader
                          label="CIKs"
                          tooltip="Comma-separated list of additional CIKs associated with this fund."
                        />
                        <ColumnHeader
                          label="Website"
                          tooltip="Official website URL of the excluded fund. Must start with https://."
                        />
                        {!IS_GH_PAGES_MODE && (
                          <th scope="col" className="text-right p-3 w-24">
                            <span className="sr-only">Actions</span>
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredExcluded.map((f, idx) => {
                        const isEditing = editingExcludedCik === f.cik;
                        return (
                          <tr key={f.cik} className="data-table-row group">
                            <td className="p-3 text-right text-muted-foreground font-mono text-xs">
                              {idx + 1}
                            </td>
                            {isEditing ? (
                              <>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.fund}
                                    field="fund"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.manager}
                                    field="manager"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.denomination}
                                    field="denomination"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.cik}
                                    field="cik"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.ciks}
                                    field="ciks"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.url}
                                    field="url"
                                    draft={editExcludedDraft}
                                    setDraft={setEditExcludedDraft}
                                  />
                                </td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-positive hover:text-positive hover:bg-positive/10"
                                    onClick={saveExcludedEdit}
                                    title="Save"
                                    aria-label="Save fund"
                                    disabled={!isExcludedDraftValid()}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                    onClick={cancelExcludedEdit}
                                    title="Cancel"
                                    aria-label="Cancel edit"
                                  >
                                    <X className="h-3.5 w-3.5" />
                                  </Button>
                                </td>
                              </>
                            ) : (
                              <>
                                <td className="p-3 font-medium">{f.fund}</td>
                                <td className="p-3 text-muted-foreground">{f.manager}</td>
                                <td className="p-3 text-muted-foreground text-xs max-w-[200px] truncate">
                                  {f.denomination}
                                </td>
                                <td className="p-3">
                                  <CikLink cik={f.cik} />
                                </td>
                                <td className="p-3 font-mono text-xs text-muted-foreground max-w-[150px] truncate">
                                  {f.ciks || "—"}
                                </td>
                                <td className="p-3">
                                  {f.url ? (
                                    <a
                                      href={f.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-primary-text hover:underline inline-flex items-center gap-1 max-w-[180px] truncate"
                                    >
                                      {f.url.replace(/^https?:\/\/(www\.)?/, "")}{" "}
                                      <ExternalLink
                                        className="h-2.5 w-2.5 shrink-0"
                                        aria-hidden="true"
                                      />
                                    </a>
                                  ) : (
                                    <span className="text-xs text-muted-foreground">—</span>
                                  )}
                                </td>
                                {!IS_GH_PAGES_MODE && (
                                  <td className="p-3 text-right whitespace-nowrap">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 group-focus-within:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                                      onClick={() => startExcludedEdit(f)}
                                      title="Edit fund"
                                      aria-label={`Edit ${f.fund}`}
                                    >
                                      <Pencil className="h-3.5 w-3.5" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 group-focus-within:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                                      onClick={() => {
                                        setFundToRestore(f);
                                        setRestoreDialogOpen(true);
                                      }}
                                      title="Restore fund"
                                      aria-label={`Restore ${f.fund}`}
                                    >
                                      <Undo2 className="h-3.5 w-3.5" />
                                    </Button>
                                  </td>
                                )}
                              </>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      ) : null}

      {!IS_GH_PAGES_MODE && (
        <>
          {/* ── Delete Dialog ── */}
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-destructive">
                  <AlertTriangle className="h-5 w-5" aria-hidden="true" /> Delete Hedge Fund
                </DialogTitle>
                <DialogDescription>
                  This will move <strong>{fundToDelete?.fund}</strong> to the excluded list.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="rounded-md border border-border bg-card p-3 space-y-1 text-sm">
                  <div>
                    <span className="text-muted-foreground">Fund:</span> {fundToDelete?.fund}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Manager:</span> {fundToDelete?.manager}
                  </div>
                  <div>
                    <span className="text-muted-foreground">CIK:</span>{" "}
                    <span className="font-mono text-xs">{fundToDelete?.cik}</span>
                  </div>
                  {fundToDelete?.url && (
                    <div>
                      <span className="text-muted-foreground">Website:</span>{" "}
                      <span className="text-xs">{fundToDelete.url}</span>
                    </div>
                  )}
                </div>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleConfirmDelete}>
                  Confirm Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* ── Restore Dialog ── */}
          <Dialog open={restoreDialogOpen} onOpenChange={setRestoreDialogOpen}>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Undo2 className="h-5 w-5" aria-hidden="true" /> Restore Hedge Fund
                </DialogTitle>
                <DialogDescription>
                  This will move <strong>{fundToRestore?.fund}</strong> back to the active list.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="rounded-md border border-border bg-card p-3 space-y-1 text-sm">
                  <div>
                    <span className="text-muted-foreground">Fund:</span> {fundToRestore?.fund}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Manager:</span> {fundToRestore?.manager}
                  </div>
                  <div>
                    <span className="text-muted-foreground">CIK:</span>{" "}
                    <span className="font-mono text-xs">{fundToRestore?.cik}</span>
                  </div>
                  {fundToRestore?.url && (
                    <div>
                      <span className="text-muted-foreground">Website:</span>{" "}
                      <span className="text-xs">{fundToRestore.url}</span>
                    </div>
                  )}
                </div>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => setRestoreDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleConfirmRestore}>Confirm Restore</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* ── Add Fund Dialog ── */}
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Plus className="h-5 w-5" aria-hidden="true" /> Add Hedge Fund
                </DialogTitle>
                <DialogDescription>Add a new fund to the monitored list.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="space-y-2">
                  <Label htmlFor="new-cik">CIK</Label>
                  <Input
                    id="new-cik"
                    placeholder="e.g. 0001067983"
                    value={newCik}
                    onChange={(e) => setNewCik(e.target.value.replace(/[^0-9]/g, ""))}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    Central Index Key: the unique SEC identifier for filing entities.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-fund">Fund Name</Label>
                  <Input
                    id="new-fund"
                    placeholder="e.g. Berkshire Hathaway"
                    value={newFundName}
                    onChange={(e) => setNewFundName(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Short name used to generate quarterly file names.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-manager">Manager</Label>
                  <Input
                    id="new-manager"
                    placeholder="e.g. Warren Buffett"
                    value={newManager}
                    onChange={(e) => setNewManager(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Portfolio manager as listed in official fund filings.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-denomination">Denomination</Label>
                  <Input
                    id="new-denomination"
                    placeholder="e.g. Berkshire Hathaway Inc."
                    value={newDenomination}
                    onChange={(e) => setNewDenomination(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Full legal name from SEC filings. Used to identify positions in non-quarterly
                    filings containing multiple institutional entities.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-ciks">CIKs (optional)</Label>
                  <Input
                    id="new-ciks"
                    placeholder="Defaults to CIK if empty"
                    value={newCiks}
                    onChange={(e) => setNewCiks(e.target.value.replace(/[^0-9,]/g, ""))}
                    className="font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    Comma-separated list of related CIKs, if different from primary.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-url">Website (optional)</Label>
                  <Input
                    id="new-url"
                    placeholder="https://www.example.com"
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Official fund website. Must start with <code>https://</code> if provided.
                  </p>
                </div>
              </div>
              <DialogFooter className="gap-2 sm:gap-0">
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  disabled={!newCik.trim() || !newFundName.trim() || !newManager.trim()}
                  onClick={handleAddFund}
                >
                  Add Fund
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  );
}
