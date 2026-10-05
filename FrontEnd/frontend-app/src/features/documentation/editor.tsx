import { useRef, useState } from "react";
import { EditorContent, NodeViewWrapper, ReactNodeViewRenderer, useEditor, type NodeViewProps } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import Highlight from "@tiptap/extension-highlight";
import { TableKit } from "@tiptap/extension-table";
import { Markdown } from "@tiptap/markdown";
import { Bold, Heading2, Highlighter, ImagePlus, Italic, Link2, List, Table, Code } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { docs, attachmentPath, errorMessage } from "./api";
import { ProtectedImage } from "./markdown";

function ImageView({ node }: NodeViewProps) { return <NodeViewWrapper><ProtectedImage src={node.attrs.src} alt={node.attrs.alt} /></NodeViewWrapper>; }
const PrivateImage = Image.extend({ addNodeView() { return ReactNodeViewRenderer(ImageView); } });

export default function ArticleEditor({ content, articleId, onChange, onBusy }: { content: string; articleId: number | null; onChange: (value: string) => void; onBusy: (busy: boolean) => void }) {
  const picker = useRef<HTMLInputElement>(null);
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const callbacks = useRef({onChange, onBusy}); callbacks.current = {onChange, onBusy};
  const editor = useEditor({
    extensions: [StarterKit.configure({link: {openOnClick: false}, underline: false}), PrivateImage, Highlight, TableKit, Markdown],
    content, contentType: "markdown", immediatelyRender: false,
    editorProps: { attributes: {class: "doc-prose min-h-72 px-4 py-4 outline-none", "aria-label": "Contenido del artículo"},
      handlePaste: (_view, event) => {
        const image = Array.from(event.clipboardData?.files ?? []).find(f => f.type.startsWith("image/"));
        if (!image) return false; event.preventDefault(); void upload(image); return true;
      },
    },
    onUpdate: ({editor}) => callbacks.current.onChange(editor.getMarkdown()),
  });
  const upload = async (file: File) => {
    if (!articleId) { toast.info("Guarda primero el borrador para agregar imágenes."); return; }
    if (busy) return;
    setBusy(true); callbacks.current.onBusy(true);
    try { const image = await docs.upload(articleId, file, "articulo"); editor?.chain().focus().setImage({src: attachmentPath(image), alt: file.name}).run(); }
    catch (error) { toast.error(errorMessage(error)); }
    finally { setBusy(false); callbacks.current.onBusy(false); }
  };
  if (!editor) return <p className="p-4 text-sm">Cargando editor…</p>;
  const actions = [
    {label: "Negrita", Icon: Bold, run: () => editor.chain().focus().toggleBold().run()},
    {label: "Cursiva", Icon: Italic, run: () => editor.chain().focus().toggleItalic().run()},
    {label: "Subtítulo", Icon: Heading2, run: () => editor.chain().focus().toggleHeading({level: 2}).run()},
    {label: "Resaltar", Icon: Highlighter, run: () => editor.chain().focus().toggleHighlight().run()},
    {label: "Lista", Icon: List, run: () => editor.chain().focus().toggleBulletList().run()},
    {label: "Código", Icon: Code, run: () => editor.chain().focus().toggleCodeBlock().run()},
    {label: "Tabla", Icon: Table, run: () => editor.chain().focus().insertTable({rows: 3, cols: 3, withHeaderRow: true}).run()},
    {label: "Enlace", Icon: Link2, run: () => setLink(editor.getAttributes("link").href || "")},
    {label: "Imagen o captura", Icon: ImagePlus, run: () => picker.current?.click()},
  ];
  return <div className="overflow-hidden rounded-lg border">
    <div className="flex flex-wrap gap-1 border-b bg-muted/30 p-1.5">{actions.map(({label, Icon, run}) => <Button key={label} type="button" size="icon" variant="ghost" title={label} aria-label={label} disabled={busy} onClick={run}><Icon className="size-4" /></Button>)}</div>
    {link !== null && <div className="flex gap-2 border-b p-2"><Input aria-label="Dirección del enlace" placeholder="https://…" value={link} onChange={e => setLink(e.target.value)} /><Button type="button" size="sm" onClick={() => { if (!link) editor.chain().focus().unsetLink().run(); else if (/^(https?:\/\/|mailto:|#)/i.test(link)) editor.chain().focus().setLink({href: link}).run(); else { toast.error("Usa un enlace http, https, correo o sección."); return; } setLink(null); }}>Aplicar</Button><Button type="button" variant="ghost" onClick={() => setLink(null)}>Cerrar</Button></div>}
    <input ref={picker} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e => { const file = e.target.files?.[0]; if (file) void upload(file); e.target.value = ""; }} />
    <EditorContent editor={editor} />
    <p className="border-t px-3 py-2 text-xs text-muted-foreground">{busy ? "Subiendo imagen…" : "Puedes pegar una captura directamente. Usa Tab para avanzar entre celdas."}</p>
  </div>;
}
