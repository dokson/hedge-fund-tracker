import { useState, type Dispatch, type SetStateAction } from "react";
import { toast } from "sonner";

import type { HedgeFund } from "@/lib/dataService";

export type FundDraft = Record<string, string>;

/** Optional website URLs must be https. */
export const isValidFundUrl = (url: string) => url.trim().startsWith("https://");

export interface InlineFundEdit {
  editingCik: string | null;
  draft: FundDraft;
  setDraft: Dispatch<SetStateAction<FundDraft>>;
  isDraftValid: boolean;
  startEdit: (fund: HedgeFund) => void;
  cancelEdit: () => void;
  saveEdit: () => Promise<void>;
}

/**
 * Inline row editing for a fund list (active or excluded): one fund at a time,
 * edited through a draft that is validated and written back as the whole list.
 */
export function useInlineFundEdit({
  funds,
  save,
  successMessage,
  onSaved,
}: {
  funds: readonly HedgeFund[];
  save: (updated: HedgeFund[]) => Promise<void>;
  successMessage: string;
  onSaved: () => void;
}): InlineFundEdit {
  const [editingCik, setEditingCik] = useState<string | null>(null);
  const [draft, setDraft] = useState<FundDraft>({});

  const isDraftValid = Boolean(
    draft.fund?.trim() && draft.manager?.trim() && draft.denomination?.trim() && draft.cik?.trim(),
  );

  const startEdit = (f: HedgeFund) => {
    setEditingCik(f.cik);
    setDraft({
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
    setDraft({});
  };

  const saveEdit = async () => {
    if (!editingCik || !isDraftValid) return;
    if (draft.url && !isValidFundUrl(draft.url)) {
      toast.error("Website URL must start with https://");
      return;
    }
    const updated = funds.map((f) =>
      f.cik === editingCik
        ? {
            ...f,
            fund: draft.fund,
            manager: draft.manager,
            denomination: draft.denomination,
            cik: draft.cik,
            ciks: draft.ciks,
            url: draft.url || "",
          }
        : f,
    );
    try {
      await save(updated);
      toast.success(successMessage);
      onSaved();
      cancelEdit();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  };

  return { editingCik, draft, setDraft, isDraftValid, startEdit, cancelEdit, saveEdit };
}
