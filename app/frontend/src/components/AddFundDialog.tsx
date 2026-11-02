import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/Field";
import { isValidFundUrl } from "@/hooks/useInlineFundEdit";
import type { HedgeFund } from "@/lib/dataService";

const EMPTY_FORM: HedgeFund = {
  cik: "",
  fund: "",
  manager: "",
  denomination: "",
  ciks: "",
  url: "",
};

/**
 * "Add Hedge Fund" dialog. The form lives inside the dialog content, which
 * unmounts on close, so every opening starts from an empty form.
 */
export function AddFundDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Receives the trimmed fund; the dialog closes once it settles. */
  onAdd: (fund: HedgeFund) => Promise<void>;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto sm:max-w-md [&_button]:min-h-10 [&_input]:min-h-10">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" aria-hidden="true" /> Add Hedge Fund
          </DialogTitle>
          <DialogDescription>Add a new fund to the monitored list.</DialogDescription>
        </DialogHeader>
        <AddFundForm
          onCancel={() => onOpenChange(false)}
          onAdd={onAdd}
          onDone={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function AddFundForm({
  onCancel,
  onAdd,
  onDone,
}: {
  onCancel: () => void;
  onAdd: (fund: HedgeFund) => Promise<void>;
  onDone: () => void;
}) {
  const [form, setForm] = useState<HedgeFund>(EMPTY_FORM);
  const update = (field: keyof HedgeFund, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));
  const canSubmit = Boolean(form.cik.trim() && form.fund.trim() && form.manager.trim());

  const submit = async () => {
    if (!canSubmit) return;
    if (form.url.trim() && !isValidFundUrl(form.url)) {
      toast.error("Website URL must start with https://");
      return;
    }
    await onAdd({
      cik: form.cik.trim(),
      fund: form.fund.trim(),
      manager: form.manager.trim(),
      denomination: form.denomination.trim(),
      ciks: form.ciks.trim() || form.cik.trim(),
      url: form.url.trim(),
    });
    onDone();
  };

  return (
    <>
      <div className="space-y-4 py-2">
        <Field htmlFor="new-cik" label="CIK">
          <Input
            id="new-cik"
            placeholder="e.g. 0001067983"
            value={form.cik}
            onChange={(e) => update("cik", e.target.value.replace(/[^0-9]/g, ""))}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Central Index Key: the unique SEC identifier for filing entities.
          </p>
        </Field>
        <Field htmlFor="new-fund" label="Fund Name">
          <Input
            id="new-fund"
            placeholder="e.g. Berkshire Hathaway"
            value={form.fund}
            onChange={(e) => update("fund", e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Short name used to generate quarterly file names.
          </p>
        </Field>
        <Field htmlFor="new-manager" label="Manager">
          <Input
            id="new-manager"
            placeholder="e.g. Warren Buffett"
            value={form.manager}
            onChange={(e) => update("manager", e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Portfolio manager as listed in official fund filings.
          </p>
        </Field>
        <Field htmlFor="new-denomination" label="Denomination">
          <Input
            id="new-denomination"
            placeholder="e.g. Berkshire Hathaway Inc."
            value={form.denomination}
            onChange={(e) => update("denomination", e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Full legal name from SEC filings. Used to identify positions in non-quarterly filings
            containing multiple institutional entities.
          </p>
        </Field>
        <Field htmlFor="new-ciks" label="CIKs (optional)">
          <Input
            id="new-ciks"
            placeholder="Defaults to CIK if empty"
            value={form.ciks}
            onChange={(e) => update("ciks", e.target.value.replace(/[^0-9,]/g, ""))}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Comma-separated list of related CIKs, if different from primary.
          </p>
        </Field>
        <Field htmlFor="new-url" label="Website (optional)">
          <Input
            id="new-url"
            placeholder="https://www.example.com"
            value={form.url}
            onChange={(e) => update("url", e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Official fund website. Must start with <code>https://</code> if provided.
          </p>
        </Field>
      </div>
      <DialogFooter className="gap-2 sm:gap-0">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button disabled={!canSubmit} onClick={submit}>
          Add Fund
        </Button>
      </DialogFooter>
    </>
  );
}
