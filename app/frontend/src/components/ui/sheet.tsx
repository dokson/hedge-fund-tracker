import * as React from "react";
import {
  Dialog as Sheet, DialogTrigger as SheetTrigger, DialogClose as SheetClose,
  DialogPortal as SheetPortal, DialogOverlay as SheetOverlay, DialogContent,
  DialogHeader as SheetHeader, DialogFooter as SheetFooter,
  DialogTitle as SheetTitle, DialogDescription as SheetDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type SheetContentProps = React.ComponentPropsWithoutRef<typeof DialogContent> & {
  side?: "top" | "bottom" | "left" | "right";
};

/** A native modal positioned against the requested viewport edge. */
const SheetContent = React.forwardRef<HTMLDialogElement, SheetContentProps>(
  ({ side = "right", className, ...props }, ref) => (
    <DialogContent
      ref={ref}
      className={cn(
        "m-0 max-h-none max-w-none rounded-none p-5",
        side === "top" && "inset-x-0 top-0 bottom-auto w-full",
        side === "bottom" && "inset-x-0 bottom-0 top-auto w-full",
        side === "left" && "inset-y-0 left-0 right-auto h-full w-3/4 sm:max-w-sm",
        side === "right" && "inset-y-0 right-0 left-auto h-full w-3/4 sm:max-w-sm",
        className,
      )}
      {...props}
    />
  ),
);
SheetContent.displayName = "SheetContent";

export { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetOverlay, SheetPortal, SheetTitle, SheetTrigger };
