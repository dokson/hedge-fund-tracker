import { useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DIALOG_AUTOFOCUS } from "@/lib/dialog";
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
import { IDENTIFIER_INPUT } from "@/lib/forms";

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

const REQUIRED_TEXT = String.raw`.*\S.*`;

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
  const [pending, setPending] = useState(false);
  const [urlError, setUrlError] = useState(false);
  const urlRef = useRef<HTMLInputElement>(null);
  const update = (field: keyof HedgeFund, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const submit = async (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (pending) return;
    if (form.url.trim() && !isValidFundUrl(form.url)) {
      flushSync(() => setUrlError(true));
      urlRef.current?.focus();
      return;
    }
    setPending(true);
    try {
      await onAdd({
        cik: form.cik.trim(),
        fund: form.fund.trim(),
        manager: form.manager.trim(),
        denomination: form.denomination.trim(),
        ciks: form.ciks.trim() || form.cik.trim(),
        url: form.url.trim(),
      });
      onDone();
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit}>
      <div className="space-y-4 py-2">
        <Field htmlFor="new-cik" label="CIK">
          <Input
            {...DIALOG_AUTOFOCUS}
            id="new-cik"
            name="cik"
            {...IDENTIFIER_INPUT}
            required
            inputMode="numeric"
            aria-describedby="new-cik-hint"
            placeholder="e.g. 0001067983"
            value={form.cik}
            onChange={(e) => update("cik", e.target.value.replace(/[^0-9]/g, ""))}
            className="font-mono text-sm"
          />
          <p id="new-cik-hint" className="text-xs text-muted-foreground">
            Central Index Key: the unique SEC identifier for filing entities.
          </p>
        </Field>
        <Field htmlFor="new-fund" label="Fund Name">
          <Input
            id="new-fund"
            name="fund"
            required
            pattern={REQUIRED_TEXT}
            autoComplete="off"
            aria-describedby="new-fund-hint"
            placeholder="e.g. Berkshire Hathaway"
            value={form.fund}
            onChange={(e) => update("fund", e.target.value)}
          />
          <p id="new-fund-hint" className="text-xs text-muted-foreground">
            Short name used to generate quarterly file names.
          </p>
        </Field>
        <Field htmlFor="new-manager" label="Manager">
          <Input
            id="new-manager"
            name="manager"
            required
            pattern={REQUIRED_TEXT}
            autoComplete="off"
            aria-describedby="new-manager-hint"
            placeholder="e.g. Warren Buffett"
            value={form.manager}
            onChange={(e) => update("manager", e.target.value)}
          />
          <p id="new-manager-hint" className="text-xs text-muted-foreground">
            Portfolio manager as listed in official fund filings.
          </p>
        </Field>
        <Field htmlFor="new-denomination" label="Denomination">
          <Input
            id="new-denomination"
            name="denomination"
            autoComplete="off"
            aria-describedby="new-denomination-hint"
            placeholder="e.g. Berkshire Hathaway Inc."
            value={form.denomination}
            onChange={(e) => update("denomination", e.target.value)}
          />
          <p id="new-denomination-hint" className="text-xs text-muted-foreground">
            Full legal name from SEC filings. Used to identify positions in non-quarterly filings
            containing multiple institutional entities.
          </p>
        </Field>
        <Field htmlFor="new-ciks" label="CIKs (optional)">
          <Input
            id="new-ciks"
            name="ciks"
            {...IDENTIFIER_INPUT}
            aria-describedby="new-ciks-hint"
            placeholder="Defaults to CIK if empty"
            value={form.ciks}
            onChange={(e) => update("ciks", e.target.value.replace(/[^0-9,]/g, ""))}
            className="font-mono text-sm"
          />
          <p id="new-ciks-hint" className="text-xs text-muted-foreground">
            Comma-separated list of related CIKs, if different from primary.
          </p>
        </Field>
        <Field htmlFor="new-url" label="Website (optional)">
          <Input
            ref={urlRef}
            id="new-url"
            name="url"
            {...IDENTIFIER_INPUT}
            inputMode="url"
            aria-invalid={urlError || undefined}
            aria-describedby={urlError ? "new-url-hint new-url-error" : "new-url-hint"}
            placeholder="https://www.example.com"
            value={form.url}
            onChange={(e) => {
              const value = e.target.value;
              update("url", value);
              if (!value.trim() || isValidFundUrl(value)) setUrlError(false);
            }}
          />
          <p id="new-url-hint" className="text-xs text-muted-foreground">
            Official fund website. Must start with <code>https://</code> if provided.
          </p>
          {urlError && (
            <p id="new-url-error" className="text-xs text-negative">
              Website URL must start with https://
            </p>
          )}
        </Field>
      </div>
      <DialogFooter className="gap-2 sm:gap-0">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          Add Fund
        </Button>
      </DialogFooter>
    </form>
  );
}
