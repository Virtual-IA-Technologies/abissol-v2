import { useEffect, type RefObject } from "react";

export function clearTextInput(input: HTMLInputElement) {
  if (input.disabled || input.readOnly || !input.value) return;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, "");
  input.dispatchEvent(new Event("input", {bubbles: true}));
  input.focus({preventScroll: true});
}

const fields = new Set<HTMLInputElement>();
function escape(event: KeyboardEvent) {
  const input = document.activeElement;
  if (event.key !== "Escape" || event.isComposing || !(input instanceof HTMLInputElement) || !fields.has(input) || input.disabled || input.readOnly || !input.value) return;
  event.preventDefault(); event.stopImmediatePropagation();
  clearTextInput(input);
}

export function useClearTextInput(ref: RefObject<HTMLInputElement | null>, enabled: boolean) {
  useEffect(() => {
    const input = ref.current; if (!enabled || !input) return;
    if (!fields.size) window.addEventListener("keydown", escape, true);
    fields.add(input);
    return () => {fields.delete(input); if (!fields.size) window.removeEventListener("keydown", escape, true);};
  }, [ref, enabled]);
}
