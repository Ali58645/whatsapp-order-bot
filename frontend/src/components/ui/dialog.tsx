import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "../../lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export function DialogContent({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-[20%] z-50 w-[calc(100%-2rem)] -translate-x-1/2 rounded-2xl border border-border bg-popover shadow-elevated focus:outline-none sm:top-[15%]",
          className
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/** Visually hidden title for dialogs that already show a visible heading. */
export function DialogSrTitle({ children }: { children: React.ReactNode }) {
  return (
    <DialogPrimitive.Title className="sr-only">{children}</DialogPrimitive.Title>
  );
}
