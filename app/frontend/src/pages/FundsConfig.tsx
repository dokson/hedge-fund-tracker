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
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { Field } from "@/components/ui/Field";
import { ResponsiveTable } from "@/components/ui/ResponsiveTable";
import { TextLink } from "@/components/ui/TextLink";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AddFundDialog } from "@/components/AddFundDialog";
import { useInlineFundEdit, type FundDraft } from "@/hooks/useInlineFundEdit";
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
  draft: FundDraft;
  setDraft: React.Dispatch<React.SetStateAction<FundDraft>>;
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
      className={`h-10 text-xs md:h-7 ${className}`}
    />
  );
}

const CikLink = ({ cik }: { cik: string }) => (
  <TextLink href={SEC_CIK_URL(cik)} className="min-h-10 font-mono text-xs tabular-nums md:min-h-0">
    {cik} <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
  </TextLink>
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
  draft: FundDraft;
  setDraft: React.Dispatch<React.SetStateAction<FundDraft>>;
  isDraftValid: boolean;
  onStartEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onSecondary: () => void;
  onOpen?: () => void;
}) {
  if (isEditing) {
    return (
      <div className="border-b border-border py-3 space-y-2.5 last:border-b-0">
        {EDIT_FIELDS.map(([field, label]) => (
          <Field key={field} label={label} htmlFor={`edit-${f.cik}-${field}`}>
            <InlineInput
              id={`edit-${f.cik}-${field}`}
              value={f[field]}
              field={field}
              draft={draft}
              setDraft={setDraft}
              className={field === "cik" || field === "ciks" ? "font-mono w-full" : "w-full"}
            />
          </Field>
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
    <div className="border-b border-border py-3 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {onOpen ? (
            <button
              type="button"
              onClick={onOpen}
              className="block max-w-full break-words text-left font-medium fund-link"
            >
              {f.fund}
            </button>
          ) : (
            <p className="break-words font-medium">{f.fund}</p>
          )}
          <p className="break-words text-xs text-muted-foreground">{f.manager}</p>
        </div>
        <span className="text-xs text-muted-foreground tabular-nums shrink-0">#{rank}</span>
      </div>
      {f.denomination && (
        <p className="mt-2 break-words text-xs text-muted-foreground">{f.denomination}</p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <CikLink cik={f.cik} />
        {f.url && (
          <TextLink href={f.url} className="min-h-10 max-w-full text-xs">
            <span className="min-w-0 truncate">{f.url.replace(/^https?:\/\/(www\.)?/, "")}</span>
            <ExternalLink className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
          </TextLink>
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

  // Every write to a funds CSV reports the same way: a toast, then a refresh on success.
  const persist = async (writes: readonly (readonly [string, string])[], message: string) => {
    try {
      for (const [csv, file] of writes) await saveFileToDisk(csv, file);
      toast.success(message);
      invalidateAll();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  };

  const activeEdit = useInlineFundEdit({
    funds,
    save: (updated) => saveFileToDisk(generateHedgeFundsCSV(updated), "hedge_funds.csv"),
    successMessage: "Fund updated",
    onSaved: invalidateAll,
  });
  const excludedEdit = useInlineFundEdit({
    funds: excludedFunds,
    save: (updated) =>
      saveFileToDisk(generateExcludedFundsCSV(updated), "excluded_hedge_funds.csv"),
    successMessage: "Excluded fund updated",
    onSaved: invalidateAll,
  });

  // Delete and restore both move a fund between the two lists, rewriting both files.
  const moveFund = (
    { hedgeFundsCSV, excludedCSV }: { hedgeFundsCSV: string; excludedCSV: string },
    message: string,
  ) =>
    persist(
      [
        [hedgeFundsCSV, "hedge_funds.csv"],
        [excludedCSV, "excluded_hedge_funds.csv"],
      ],
      message,
    );

  const handleConfirmDelete = async () => {
    if (!fundToDelete) return;
    await moveFund(
      generateDeleteFundCSVs(funds, excludedFunds, fundToDelete),
      `"${fundToDelete.fund}" moved to excluded`,
    );
    setDeleteDialogOpen(false);
    setFundToDelete(null);
  };

  const handleConfirmRestore = async () => {
    if (!fundToRestore) return;
    await moveFund(
      generateRestoreFundCSVs(funds, excludedFunds, fundToRestore),
      `"${fundToRestore.fund}" restored to active`,
    );
    setRestoreDialogOpen(false);
    setFundToRestore(null);
  };

  const handleAddFund = (newFund: HedgeFund) =>
    persist([[generateAddFundCSV(funds, newFund), "hedge_funds.csv"]], `"${newFund.fund}" added`);

  return (
    <div className="min-w-0 space-y-6 max-w-screen-2xl [&_button]:min-h-10 md:[&_button]:min-h-0 [&_input]:min-h-10 md:[&_input]:min-h-0">
      <PageHeader
        title="Hedge Funds Configuration"
        icon={Settings2}
        description={
          IS_GH_PAGES_MODE
            ? "View the monitored hedge funds. This is a read-only view of the bundled data."
            : "Manage the funds monitored for quarterly and ownership filings."
        }
      />

      {IS_GH_PAGES_MODE && (
        <p className="text-sm text-muted-foreground" role="note">
          Read-only mode. To modify the hedge funds list, run the application locally.
        </p>
      )}

      <Tabs defaultValue="active">
        <TabsList>
          <TabsTrigger value="active">
            Active Funds{" "}
            <span className="ml-1 text-muted-foreground tabular-nums">{funds.length}</span>
          </TabsTrigger>
          <TabsTrigger value="excluded">
            Excluded{" "}
            <span className="ml-1 text-muted-foreground tabular-nums">{excludedFunds.length}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active" className="mt-6 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <SearchInput
              label="Search fund, manager, CIK"
              size="sm"
              value={fundSearch}
              onChange={(e) => setFundSearch(e.target.value)}
              wrapperClassName="flex-1 basis-full min-w-0 sm:basis-auto sm:max-w-sm"
            />
            <span className="text-xs text-muted-foreground tabular-nums">
              {filteredFunds.length} / {funds.length} funds
            </span>
            {!IS_GH_PAGES_MODE && (
              <Button size="sm" className="gap-1.5 ml-auto" onClick={() => setAddDialogOpen(true)}>
                <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add Fund
              </Button>
            )}
          </div>
          <p className="break-all text-xs text-muted-foreground">
            Source: <code className="font-mono bg-muted px-1 py-0.5">database/hedge_funds.csv</code>
          </p>

          {fundsLoading ? (
            <LoadingState message="Loading…" size="sm" />
          ) : filteredFunds.length === 0 ? (
            <EmptyState padding="sm" title="No active funds match your search." />
          ) : (
            <Panel
              title="Active funds"
              aside={<span className="tabular-nums">{filteredFunds.length} funds</span>}
            >
              <ResponsiveTable
                label="Active funds"
                tableClassName="max-h-[60vh] overflow-auto"
                cards={
                  <div className="px-3">
                    {filteredFunds.map((f, idx) => (
                      <FundConfigCard
                        key={f.cik}
                        f={f}
                        rank={idx + 1}
                        mode="active"
                        readOnly={IS_GH_PAGES_MODE}
                        isEditing={activeEdit.editingCik === f.cik}
                        draft={activeEdit.draft}
                        setDraft={activeEdit.setDraft}
                        isDraftValid={activeEdit.isDraftValid}
                        onStartEdit={() => activeEdit.startEdit(f)}
                        onSave={activeEdit.saveEdit}
                        onCancel={activeEdit.cancelEdit}
                        onSecondary={() => {
                          setFundToDelete(f);
                          setDeleteDialogOpen(true);
                        }}
                        onOpen={() => navigate(fundPath(f.fund))}
                      />
                    ))}
                  </div>
                }
                table={
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
                    <tbody className="tabular-nums">
                      {filteredFunds.map((f, idx) => {
                        const isEditing = activeEdit.editingCik === f.cik;
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
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.manager}
                                    field="manager"
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.denomination}
                                    field="denomination"
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.cik}
                                    field="cik"
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.ciks}
                                    field="ciks"
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.url}
                                    field="url"
                                    draft={activeEdit.draft}
                                    setDraft={activeEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-positive hover:text-positive hover:bg-positive/10"
                                    onClick={activeEdit.saveEdit}
                                    title="Save"
                                    aria-label="Save fund"
                                    disabled={!activeEdit.isDraftValid}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                    onClick={activeEdit.cancelEdit}
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
                                  className="p-3 text-muted-foreground cursor-pointer"
                                  onClick={() => navigate(fundPath(f.fund))}
                                >
                                  {f.manager}
                                </td>
                                <td
                                  className="p-3 text-muted-foreground text-xs max-w-[250px] truncate cursor-pointer"
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
                                    <TextLink
                                      href={f.url}
                                      className="text-xs max-w-[180px] truncate"
                                    >
                                      {f.url.replace(/^https?:\/\/(www\.)?/, "")}{" "}
                                      <ExternalLink
                                        className="h-2.5 w-2.5 shrink-0"
                                        aria-hidden="true"
                                      />
                                    </TextLink>
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
                                      onClick={() => activeEdit.startEdit(f)}
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
                }
              />
            </Panel>
          )}
        </TabsContent>

        <TabsContent value="excluded" className="mt-6 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <SearchInput
              label="Search excluded fund, manager, URL"
              size="sm"
              value={excludedSearch}
              onChange={(e) => setExcludedSearch(e.target.value)}
              wrapperClassName="flex-1 basis-full min-w-0 sm:basis-auto sm:max-w-sm"
            />
            <span className="text-xs text-muted-foreground tabular-nums">
              {filteredExcluded.length} / {excludedFunds.length} excluded
            </span>
          </div>

          <p className="break-all text-xs text-muted-foreground">
            Source:{" "}
            <code className="font-mono bg-muted px-1 py-0.5">
              database/excluded_hedge_funds.csv
            </code>
          </p>

          {excludedLoading ? (
            <LoadingState message="Loading…" size="sm" />
          ) : filteredExcluded.length === 0 ? (
            <EmptyState padding="sm" title="No excluded funds found." />
          ) : (
            <Panel
              title="Excluded funds"
              aside={<span className="tabular-nums">{filteredExcluded.length} funds</span>}
            >
              <ResponsiveTable
                label="Excluded funds"
                tableClassName="max-h-[60vh] overflow-auto"
                cards={
                  <div className="px-3">
                    {filteredExcluded.map((f, idx) => (
                      <FundConfigCard
                        key={f.cik}
                        f={f}
                        rank={idx + 1}
                        mode="excluded"
                        readOnly={IS_GH_PAGES_MODE}
                        isEditing={excludedEdit.editingCik === f.cik}
                        draft={excludedEdit.draft}
                        setDraft={excludedEdit.setDraft}
                        isDraftValid={excludedEdit.isDraftValid}
                        onStartEdit={() => excludedEdit.startEdit(f)}
                        onSave={excludedEdit.saveEdit}
                        onCancel={excludedEdit.cancelEdit}
                        onSecondary={() => {
                          setFundToRestore(f);
                          setRestoreDialogOpen(true);
                        }}
                      />
                    ))}
                  </div>
                }
                table={
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
                    <tbody className="tabular-nums">
                      {filteredExcluded.map((f, idx) => {
                        const isEditing = excludedEdit.editingCik === f.cik;
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
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.manager}
                                    field="manager"
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.denomination}
                                    field="denomination"
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.cik}
                                    field="cik"
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.ciks}
                                    field="ciks"
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                    className="font-mono"
                                  />
                                </td>
                                <td className="p-2">
                                  <InlineInput
                                    value={f.url}
                                    field="url"
                                    draft={excludedEdit.draft}
                                    setDraft={excludedEdit.setDraft}
                                  />
                                </td>
                                <td className="p-2 text-right whitespace-nowrap">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-positive hover:text-positive hover:bg-positive/10"
                                    onClick={excludedEdit.saveEdit}
                                    title="Save"
                                    aria-label="Save fund"
                                    disabled={!excludedEdit.isDraftValid}
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                                    onClick={excludedEdit.cancelEdit}
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
                                    <TextLink
                                      href={f.url}
                                      className="text-xs max-w-[180px] truncate"
                                    >
                                      {f.url.replace(/^https?:\/\/(www\.)?/, "")}{" "}
                                      <ExternalLink
                                        className="h-2.5 w-2.5 shrink-0"
                                        aria-hidden="true"
                                      />
                                    </TextLink>
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
                                      onClick={() => excludedEdit.startEdit(f)}
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
                }
              />
            </Panel>
          )}
        </TabsContent>
      </Tabs>

      {!IS_GH_PAGES_MODE && (
        <>
          {/* ── Delete Dialog ── */}
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto break-words sm:max-w-md [&_button]:min-h-10">
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
                    <span className="font-mono text-xs tabular-nums">{fundToDelete?.cik}</span>
                  </div>
                  {fundToDelete?.url && (
                    <div>
                      <span className="text-muted-foreground">Website:</span>{" "}
                      <span className="break-all text-xs">{fundToDelete.url}</span>
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
            <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto break-words sm:max-w-md [&_button]:min-h-10">
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
                    <span className="font-mono text-xs tabular-nums">{fundToRestore?.cik}</span>
                  </div>
                  {fundToRestore?.url && (
                    <div>
                      <span className="text-muted-foreground">Website:</span>{" "}
                      <span className="break-all text-xs">{fundToRestore.url}</span>
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

          <AddFundDialog
            open={addDialogOpen}
            onOpenChange={setAddDialogOpen}
            onAdd={handleAddFund}
          />
        </>
      )}
    </div>
  );
}
