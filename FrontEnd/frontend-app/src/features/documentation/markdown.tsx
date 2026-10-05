import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { docs, errorMessage, saveBlob } from "./api";
import { searchRanges } from "./search-text";

type HtmlNode = {type: string; value?: string; tagName?: string; properties?: Record<string, unknown>; children?: HtmlNode[]};
function searchMatches(query: string) {
  return () => (tree: HtmlNode) => {
    const walk = (node: HtmlNode) => {
      if (!node.children) return;
      node.children = node.children.flatMap(child => {
        if (child.type !== "text" || !child.value) {walk(child); return [child];}
        const ranges = searchRanges(child.value,query); let end = 0; const result: HtmlNode[] = [];
        for (const range of ranges) {
          result.push({type:"text",value:child.value.slice(end,range.start)}, {type:"element",tagName:"mark",properties:{"data-search-hit":true},children:[{type:"text",value:child.value.slice(range.start,range.end)}]});
          end = range.end;
        }
        result.push({type:"text",value:child.value.slice(end)}); return result;
      });
    }; walk(tree);
  };
}

export function ProtectedImage({ src, alt = "Imagen del artículo" }: { src?: string; alt?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(false);
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) setVisible(true); }, { rootMargin: "150px" });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!visible || !src || !/^\/documentacion\/\d+\/adjuntos\/\d+$/.test(src)) return;
    let active = true; let objectUrl = "";
    docs.blob(src).then(blob => { if (!active) return; if (!blob.type.startsWith("image/")) throw Error(); objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [src, visible]);
  return <span ref={ref} data-doc-image={src} className="block min-h-12">{url ? <img src={url} alt={alt} loading="lazy" className="max-h-[600px] max-w-full rounded-lg object-contain" /> : <span className="text-xs text-muted-foreground">{failed ? "Imagen no disponible" : "Imagen: " + alt}</span>}</span>;
}

type MdNode = { type: string; value?: string; children?: MdNode[]; position?: {start: {line: number}}; data?: {hName?: string; hProperties?: Record<string, string>} };
function enhancements() {
  return (tree: MdNode) => {
    const walk = (node: MdNode) => {
      if (node.type === "heading") node.data = {hProperties: {id: `seccion-${node.position?.start.line}`}};
      if (!node.children || node.type === "code" || node.type === "inlineCode") return;
      node.children = node.children.flatMap(child => {
        if (child.type !== "text" || !child.value?.includes("==")) { walk(child); return [child]; }
        return child.value.split(/(==[^=\n]+==)/g).filter(Boolean).map(part => part.startsWith("==") && part.endsWith("==")
          ? {type: "highlight", data: {hName: "mark"}, children: [{type: "text", value: part.slice(2, -2)}]} : {type: "text", value: part});
      });
    }; walk(tree);
  };
}

export function Markdown({ content, articleId, search = "" }: { content: string; articleId: number; search?: string }) {
  const navigate = useNavigate();
  return <ReactMarkdown skipHtml remarkPlugins={[remarkGfm, enhancements]} rehypePlugins={search.trim() ? [searchMatches(search)] : []} components={{
    img: ({src, alt}) => <ProtectedImage key={src} src={src} alt={alt} />,
    a: ({href, children}) => <a href={href} target={href?.startsWith("https://") ? "_blank" : undefined} rel="noopener noreferrer" onClick={event => {
      if (!href) return;
      if (/^\/documentacion\/\d+\/adjuntos\/\d+$/.test(href)) {
        event.preventDefault(); void docs.blob(href).then(blob => saveBlob(blob, `adjunto-${href.split("/").pop()}`)).catch(error => toast.error(errorMessage(error)));
      } else if (!/^(?:[a-z]+:|\/\/)/i.test(href) && /\.(png|jpe?g|webp)(?:#.*)?$/i.test(href)) {
        event.preventDefault();
        const path = decodeURIComponent(href.split("#")[0]);
        void docs.blob(`/documentacion/${articleId}/recurso?ruta=${encodeURIComponent(path)}`).then(blob => saveBlob(blob,path.split("/").pop() || "imagen")).catch(error => toast.error(errorMessage(error)));
      } else if (/\.md(?:#.*)?$/i.test(href)) {
        event.preventDefault(); void docs.resolve(articleId, href.split("#")[0]).then(row => navigate(`?articulo=${row.id}`)).catch(() => toast.error("El documento enlazado no está disponible para tu acceso."));
      }
    }}>{children}</a>,
  }}>{content}</ReactMarkdown>;
}
