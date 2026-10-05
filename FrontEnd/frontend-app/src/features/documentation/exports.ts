import { docs, saveBlob, type Article } from "./api";
const escape = (text: string) => text.replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]!));
export async function exportHtml(element: HTMLElement, article: Article, print = false) {
  const clone = element.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("mark[data-search-hit]").forEach(mark => mark.replaceWith(...mark.childNodes));
  for (const node of clone.querySelectorAll<HTMLElement>("[data-doc-image]")) {
    const path = node.dataset.docImage;
    if (!path || !/^\/documentacion\/\d+\/adjuntos\/\d+$/.test(path)) continue;
    const blob = await docs.blob(path);
    const source = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = reject; reader.readAsDataURL(blob); });
    const img = document.createElement("img"); img.src = source; img.alt = node.textContent || "Imagen"; node.replaceChildren(img);
  }
  const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(article.titulo)}</title><style>body{max-width:850px;margin:40px auto;padding:0 24px;font:15px/1.7 system-ui;color:#27272a}h1,h2,h3{line-height:1.3}img{max-width:100%;height:auto}table{border-collapse:collapse;max-width:100%}td,th{border:1px solid #ddd;padding:8px}pre{white-space:pre-wrap;background:#f4f4f5;padding:16px;overflow-wrap:anywhere}blockquote{border-left:3px solid #ddd;padding-left:16px}mark{background:#fef08a}a{color:#0369a1}@media print{body{margin:0}pre,tr,img{break-inside:avoid}}</style></head><body><h1>${escape(article.titulo)}</h1><p>Versión ${article.version}</p>${clone.innerHTML}</body></html>`;
  if (!print) { saveBlob(new Blob([html], {type: "text/html;charset=utf-8"}), `documento-${article.id}.html`); return; }
  const frame = document.createElement("iframe"); frame.style.cssText = "position:fixed;width:1px;height:1px;left:-9999px;border:0";
  frame.onload = async () => {
    await Promise.all(Array.from(frame.contentDocument?.images ?? []).map(img => img.decode().catch(() => undefined)));
    frame.contentWindow?.focus(); frame.contentWindow?.print(); setTimeout(() => frame.remove(), 60000);
  }; frame.srcdoc = html; document.body.appendChild(frame);
}
