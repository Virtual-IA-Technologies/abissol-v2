import { useState, type ReactNode } from "react";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

export function ConfirmActionDialog({
  children, title, description, confirmLabel = "Confirmar", destructive = false, onConfirm,
}: {
  children: ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const confirm = async (event: React.MouseEvent) => {
    event.preventDefault();
    setBusy(true);
    try { await onConfirm(); setOpen(false); } finally { setBusy(false); }
  };
  return <AlertDialog open={open} onOpenChange={setOpen}><AlertDialogTrigger asChild>{children}</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{title}</AlertDialogTitle><AlertDialogDescription>{description}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={busy}>Cancelar</AlertDialogCancel><AlertDialogAction onClick={confirm} disabled={busy} className={destructive ? "bg-red-600 text-white hover:bg-red-700" : undefined}>{busy ? "Procesando…" : confirmLabel}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>;
}
