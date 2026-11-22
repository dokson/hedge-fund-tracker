import * as React from "react";
import {
  Dialog as AlertDialog, DialogTrigger as AlertDialogTrigger,
  DialogPortal as AlertDialogPortal, DialogOverlay as AlertDialogOverlay,
  DialogContent, DialogHeader as AlertDialogHeader, DialogFooter as AlertDialogFooter,
  DialogTitle as AlertDialogTitle, DialogDescription as AlertDialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DIALOG_AUTOFOCUS } from "@/lib/dialog";

/** Confirmation modal keeps outside clicks from dismissing an unanswered prompt; `alertdialog` tells assistive tech it is a warning. */
const AlertDialogContent = React.forwardRef<HTMLDialogElement, React.ComponentPropsWithoutRef<typeof DialogContent>>(
  (props, ref) => <DialogContent ref={ref} role="alertdialog" closedBy="closerequest" showCloseButton={false} {...props} />,
);
AlertDialogContent.displayName = "AlertDialogContent";

const AlertDialogAction = React.forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<typeof DialogClose>>(
  ({ className, ...props }, ref) => <DialogClose ref={ref} className={cn(buttonVariants(), className)} {...props} />,
);
AlertDialogAction.displayName = "AlertDialogAction";
const AlertDialogCancel = React.forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<typeof DialogClose>>(
  ({ className, ...props }, ref) => <DialogClose ref={ref} {...DIALOG_AUTOFOCUS} className={cn(buttonVariants({ variant: "outline" }), "mt-2 sm:mt-0", className)} {...props} />,
);
AlertDialogCancel.displayName = "AlertDialogCancel";

export { AlertDialog, AlertDialogPortal, AlertDialogOverlay, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel };
