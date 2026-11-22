import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

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
import { cn } from "@/lib/utils";

/**
 * The confirm-before-acting dialog: icon and title, one line saying what happens,
 * an optional body (what is affected), Cancel and the confirming action. A
 * destructive one sets the title and the action in the destructive tone.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  icon: Icon,
  title,
  description,
  children,
  confirmLabel,
  onConfirm,
  destructive = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto break-words sm:max-w-md [&_button]:min-h-10">
        <DialogHeader>
          <DialogTitle className={cn("flex items-center gap-2", destructive && "text-destructive-text")}>
            <Icon className="h-5 w-5" aria-hidden="true" /> {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children && <div className="py-2">{children}</div>}
        <DialogFooter className="gap-2 sm:gap-0">
          {/* The safe action takes the focus in a destructive confirmation. */}
          <Button {...DIALOG_AUTOFOCUS} variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** The boxed "label: value" summary of what a dialog acts on. */
export function DetailList({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="space-y-1 rounded-md border border-border bg-card p-3 text-sm">
      {items.map(({ label, value }) => (
        <div key={label}>
          <dt className="inline text-muted-foreground">{label}:</dt> <dd className="inline">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
