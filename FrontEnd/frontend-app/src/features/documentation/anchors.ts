import type { Annotation, CommentAnchor } from "./api";

// Offsets use text nodes only. Image loading/error labels never shift a citation.
export function textIndex(root: HTMLElement) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: node => node.parentElement?.closest("[data-doc-image]") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const nodes: {node: Text; start: number; end: number}[] = [];
  let text = "";
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    nodes.push({node, start: text.length, end: text.length + node.length});
    text += node.data;
  }
  return {nodes, text};
}

export function locateOffset(text: string, annotation: Pick<Annotation, "cita" | "ancla" | "version_articulo">, version: number): CommentAnchor | null {
  if (annotation.version_articulo !== version || !annotation.cita) return null;
  const {ancla, cita} = annotation;
  if (ancla) return text.slice(ancla.inicio, ancla.fin) === cita ? ancla : null;
  const start = text.indexOf(cita);
  // Old comments have no offsets: never guess between repeated phrases.
  return start >= 0 && text.indexOf(cita, start + 1) < 0 ? {inicio: start, fin: start + cita.length} : null;
}

export function rangeFor(root: HTMLElement, anchor: CommentAnchor, index = textIndex(root)): Range | null {
  const {nodes} = index;
  const first = nodes.find(n => n.start <= anchor.inicio && n.end > anchor.inicio);
  const last = nodes.find(n => n.start < anchor.fin && n.end >= anchor.fin);
  if (!first || !last) return null;
  const range = document.createRange();
  range.setStart(first.node, anchor.inicio - first.start);
  range.setEnd(last.node, anchor.fin - last.start);
  return range;
}

export function selectedAnchor(root: HTMLElement): {cita: string; ancla: CommentAnchor; range: Range} | null {
  const selection = window.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed) return null;
  const selected = selection.getRangeAt(0);
  if (!root.contains(selected.startContainer) || !root.contains(selected.endContainer)) return null;
  const {nodes, text} = textIndex(root);
  let start: number | undefined; let end: number | undefined;
  for (const entry of nodes) {
    if (!selected.intersectsNode(entry.node)) continue;
    const from = entry.node === selected.startContainer ? selected.startOffset : 0;
    const to = entry.node === selected.endContainer ? selected.endOffset : entry.node.length;
    if (from === to) continue;
    start ??= entry.start + from;
    end = entry.start + to;
  }
  if (start === undefined || end === undefined) return null;
  const raw = text.slice(start, end); const cita = raw.trim();
  if (!cita || cita.length > 2000) return null;
  start += raw.length - raw.trimStart().length;
  const ancla = {inicio: start, fin: start + cita.length};
  const range = rangeFor(root, ancla);
  return range ? {cita, ancla, range} : null;
}
