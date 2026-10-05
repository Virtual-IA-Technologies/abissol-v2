import { useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import type { Worker } from 'tesseract.js';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { saveFile } from './api';

export function PdfTextTools({pdf, url, name, isPdf, jump}: {pdf: PDFDocumentProxy | null; url: string; name: string; isPdf: boolean; jump: (page: number) => void}) {
  const [texts, setTexts] = useState<string[]>([]), [query, setQuery] = useState('');
  const [indexing, setIndexing] = useState(false), [progress, setProgress] = useState('');
  const [running, setRunning] = useState(false), [exporting, setExporting] = useState(false);
  const [error, setError] = useState(''), [language, setLanguage] = useState('spa+eng');
  const worker = useRef<Worker | null>(null), generation = useRef({value: 0});
  const loaded = useRef(false);
  useEffect(() => {
    const jobs = generation.current;
    loaded.current = true;
    return () => {loaded.current = false; jobs.value++; void worker.current?.terminate(); worker.current = null;};
  }, []);
  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    setIndexing(true); setError('');
    void (async () => {
      const result: string[] = []; let count = 0;
      for (let page = 1; page <= pdf.numPages; page++) {
        if (cancelled) return;
        const content = await (await pdf.getPage(page)).getTextContent();
        const text = content.items.map(item => 'str' in item ? item.str + (item.hasEOL ? '\n' : ' ') : '').join('');
        count += text.length;
        if (count > 5_000_000) throw Error('El texto supera 5 millones de caracteres. Divide el PDF para procesarlo completo.');
        result.push(text);
      }
      if (!cancelled) setTexts(result);
    })().catch(error => {if (!cancelled) setError(error instanceof Error ? error.message : 'No se pudo extraer el texto');}).finally(() => {if (!cancelled) setIndexing(false);});
    return () => {cancelled = true;};
  }, [pdf]);
  const stop = () => {generation.current.value++; const active = worker.current; worker.current = null; void active?.terminate(); setRunning(false); setProgress('OCR cancelado. Se conserva el texto completado.');};
  const recognize = async () => {
    if (running || indexing || (isPdf && !pdf)) return;
    const token = ++generation.current.value;
    const valid = () => loaded.current && token === generation.current.value;
    setRunning(true); setError(''); setProgress('Preparando OCR local…');
    let active: Worker | null = null;
    try {
      const { createWorker } = await import('tesseract.js');
      if (!valid()) return;
      const asset = new URL(`${import.meta.env.BASE_URL}ocr/`, window.location.origin).href;
      active = await createWorker(language, 1, {workerPath: asset + 'worker.min.js', corePath: asset, langPath: asset, workerBlobURL: false});
      if (!valid()) return;
      worker.current = active;
      const result = [...texts]; let count = 0;
      const total = pdf?.numPages || 1;
      for (let page = 1; page <= total; page++) {
        if (!valid()) return;
        setProgress(`OCR · página ${page} de ${total}`);
        let source: HTMLCanvasElement | string = url;
        let drawing: HTMLCanvasElement | undefined;
        if (pdf) {
          const sheet = await pdf.getPage(page);
          if (!valid()) return;
          const base = sheet.getViewport({scale: 1});
          const view = sheet.getViewport({scale: Math.min(2, Math.sqrt(4_000_000 / (base.width * base.height)))});
          drawing = document.createElement('canvas'); drawing.width = Math.ceil(view.width); drawing.height = Math.ceil(view.height);
          await sheet.render({canvas: drawing, viewport: view}).promise;
          source = drawing;
        } else {
          const bitmap = await createImageBitmap(await (await fetch(url)).blob());
          const scale = Math.min(1, Math.sqrt(4_000_000 / (bitmap.width * bitmap.height)));
          drawing = document.createElement('canvas'); drawing.width = Math.ceil(bitmap.width * scale); drawing.height = Math.ceil(bitmap.height * scale);
          drawing.getContext('2d')!.drawImage(bitmap, 0, 0, drawing.width, drawing.height);
          bitmap.close(); source = drawing;
        }
        if (!valid()) {if (drawing) {drawing.width = 0; drawing.height = 0;} return;}
        try {
          const {data} = await active.recognize(source);
          if (!valid()) return;
          count += data.text.length;
          if (count > 5_000_000) throw Error('El OCR supera el límite de texto. Divide el archivo para continuar.');
          result[page - 1] = data.text;
          setTexts([...result]);
        } finally {if (drawing) {drawing.width = 0; drawing.height = 0;}}
      }
      if (valid()) {setProgress('OCR completado. Revisa el texto antes de utilizarlo.'); toast.success('Texto reconocido');}
    } catch (error) {
      if (valid()) setError(error instanceof Error ? error.message : 'No se pudo ejecutar OCR');
    } finally {
      if (worker.current === active) worker.current = null;
      await active?.terminate();
      if (valid()) setRunning(false);
    }
  };
  const download = async (word: boolean) => {
    setExporting(true);
    try {
      const filename = name.replace(/\.[^.]+$/, '');
      if (!word) saveFile(new Blob(['\uFEFF' + texts.map((text, i) => `Página ${i + 1}\n${text.trim() || '[Sin texto reconocido]'}`).join('\n\n')], {type: 'text/plain;charset=utf-8'}), filename + '.txt');
      else {
        const { Document, Paragraph, TextRun, Packer } = await import('docx');
        const sections = texts.map((text, i) => ({children: [new Paragraph({children: [new TextRun({text: `Página ${i + 1}`, bold: true})]}), ...((text.trim() || '[Sin texto reconocido]').split('\n').map(line => new Paragraph(line)))]}));
        saveFile(await Packer.toBlob(new Document({sections})), filename + '.docx');
      }
    } catch {toast.error('No se pudo generar la descarga');} finally {if (loaded.current) setExporting(false);}
  };
  const term = query.trim().toLocaleLowerCase();
  const matches = term ? texts.flatMap((text, index) => {const at = text.toLocaleLowerCase().indexOf(term);return at < 0 ? [] : [{page: index + 1, before: text.slice(Math.max(0, at - 45), at), hit: text.slice(at, at + term.length), after: text.slice(at + term.length, at + term.length + 90)}];}) : [];
  const hasText = texts.some(text => text.trim());
  return <div className="space-y-2 border-b bg-muted/10 p-2 text-sm">
    <div className="flex flex-wrap items-center gap-2">
      <Input className="min-w-48 flex-1" aria-label="Buscar texto dentro del PDF" placeholder={indexing ? 'Preparando búsqueda…' : 'Buscar dentro del documento…'} value={query} onChange={event => setQuery(event.target.value)} />
      <Button size="sm" variant="outline" disabled={running || indexing || exporting || (isPdf && !pdf)} onClick={() => void recognize()}>OCR</Button>
      {running && <Button size="sm" variant="outline" onClick={stop}>Cancelar OCR</Button>}
      <Button size="sm" variant="outline" disabled={!hasText || running || indexing || exporting} onClick={() => void download(false)}>Texto (.txt)</Button>
      <Button size="sm" variant="outline" disabled={!hasText || running || indexing || exporting} onClick={() => void download(true)}>Word (.docx)</Button>
      <Button size="sm" variant="ghost" disabled={running} title="Idioma del reconocimiento" onClick={() => setLanguage(value => value === 'spa+eng' ? 'spa' : 'spa+eng')}>{language === 'spa' ? 'Español' : 'Español + inglés'}</Button>
    </div>
    <p className="text-xs text-muted-foreground">{progress || 'OCR local para escaneos. Word y TXT exportan texto, sin reproducir la maquetación. El original se conserva.'}</p>
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    {term && <div className="max-h-36 overflow-auto"><p className="text-xs text-muted-foreground">{matches.length} páginas con coincidencias{indexing ? ' · Preparando texto…' : ''}</p>{matches.map(match => <button key={match.page} className="block w-full rounded p-1 text-left text-xs hover:bg-muted" onClick={() => jump(match.page)}><strong>Pág. {match.page}: </strong>{match.before}<mark>{match.hit}</mark>{match.after}</button>)}{!matches.length && !indexing && !hasText && <p className="text-xs">Este archivo no tiene texto extraído. Pulsa OCR para reconocerlo.</p>}</div>}
  </div>;
}
