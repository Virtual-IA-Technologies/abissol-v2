import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import type { PDFDocumentProxy } from 'pdfjs-dist';

export function PdfPage({pdf, page, width, zoom, viewport, onVisible, overlay}: {
  pdf: PDFDocumentProxy; page: number; width: number; zoom: number;
  viewport: RefObject<HTMLDivElement | null>; onVisible: (page: number) => void;
  overlay: (page: number, ready: boolean) => ReactNode;
}) {
  const host = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const [near, setNear] = useState(false), [ready, setReady] = useState(false);
  const [ratio, setRatio] = useState(Math.SQRT2), [error, setError] = useState('');
  const shownWidth = Math.min(width * zoom, 2400);
  useEffect(() => {
    if (!host.current) return;
    const observer = new IntersectionObserver(([entry]) => setNear(entry.isIntersecting), {root: viewport.current, rootMargin: '700px 0px'});
    const current = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) onVisible(page); }, {root: viewport.current, rootMargin: '-15% 0px -75% 0px'});
    observer.observe(host.current); current.observe(host.current);
    return () => {observer.disconnect(); current.disconnect();};
  }, [viewport, page, onVisible]);
  useEffect(() => {
    const target = canvas.current;
    if (!target) return;
    setReady(false);
    if (!near) { target.width = 0; target.height = 0; return; }
    let cancelled = false;
    let drawing: {cancel: () => void; promise: Promise<void>} | undefined;
    void (async () => {
      const sheet = await pdf.getPage(page);
      if (cancelled) return;
      const base = sheet.getViewport({scale: 1});
      setRatio(base.height / base.width);
      const view = sheet.getViewport({scale: shownWidth / base.width});
      const pixels = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(4_000_000 / (view.width * view.height)));
      target.width = Math.ceil(view.width * pixels); target.height = Math.ceil(view.height * pixels);
      drawing = sheet.render({canvas: target, viewport: view, transform: [pixels, 0, 0, pixels, 0, 0]});
      await drawing.promise;
      if (!cancelled) {setReady(true); setError('');}
    })().catch(error => {if (!cancelled && error?.name !== 'RenderingCancelledException') setError('No se pudo mostrar esta página');});
    return () => {cancelled = true; drawing?.cancel();};
  }, [pdf, page, near, shownWidth]);
  return <div ref={host} data-pdf-page={page} className="relative mx-auto mb-5 shrink-0 bg-white shadow" style={{width: shownWidth, height: shownWidth * ratio}} aria-label={`Página ${page}`}>
    <canvas ref={canvas} style={{width: shownWidth, height: shownWidth * ratio}} />
    {!ready && <span role="status" className="absolute left-3 top-3 bg-white p-2 text-sm text-gray-700">{error || `Página ${page} · ${near ? 'Cargando…' : 'PDF'}`}</span>}
    {ready && overlay(page, ready)}
    <span className="pointer-events-none absolute bottom-1 right-2 bg-white/80 px-1 text-[10px] text-gray-500">{page}</span>
  </div>;
}
