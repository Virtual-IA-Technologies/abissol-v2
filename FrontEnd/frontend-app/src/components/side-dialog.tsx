import type { ComponentProps } from 'react';
import { cn } from '@/lib/utils';
import { SheetContent, SheetHeader } from '@/components/ui/sheet';
export { Sheet as Dialog, SheetTitle as DialogTitle, SheetDescription as DialogDescription } from '@/components/ui/sheet';

export function DialogContent({className,...props}:ComponentProps<typeof SheetContent>) {
  return <SheetContent {...props} side="right" className={cn('w-full gap-4 overflow-y-auto p-6 sm:max-w-2xl',className,'h-dvh max-h-none')} />;
}
export function DialogHeader({className,...props}:ComponentProps<typeof SheetHeader>) {
  return <SheetHeader {...props} className={cn('px-0 pt-0 pb-5 pr-10 sm:px-0 sm:pt-0 sm:pb-5 sm:pr-10',className)} />;
}
