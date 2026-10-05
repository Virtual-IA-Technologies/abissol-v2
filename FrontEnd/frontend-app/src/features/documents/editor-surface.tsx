import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import { SheetClose, SheetContent, SheetTitle, SheetDescription } from '@/components/ui/sheet';

export function EditorSurface({title,children}:{title:string;children:ReactNode}) {
  return <SheetContent showCloseButton={false} className="inset-0 h-dvh w-full max-w-none border-0 sm:max-w-none">
    <div className="flex h-9 shrink-0 items-center justify-end border-b px-1">
      <SheetTitle className="sr-only">{title}</SheetTitle>
      <SheetDescription className="sr-only">Editor de documento a pantalla completa.</SheetDescription>
      <SheetClose className="inline-flex size-8 items-center justify-center rounded hover:bg-muted focus-visible:outline-2" aria-label="Cerrar editor" title="Cerrar"><X className="size-4"/></SheetClose>
    </div>
    <div className="min-h-0 flex-1 overflow-auto">{children}</div>
  </SheetContent>;
}
