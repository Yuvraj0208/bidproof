// The proof pane (US-04): renders the tender PDF with pdf.js and, when a
// rule is clicked, scrolls to its page and draws the highlight box over the
// exact element the rule cites.
//
// Two-phase load: phase 1 fetches the document, phase 2 paints pages after
// the holders exist. Every in-flight render task is cancelled on cleanup so
// StrictMode's double-mounted effects never fight over a canvas.
import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { fetchDocumentBlob } from "../api";
import { highlightRect, type BBox } from "../proofGeometry";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const SCALE = 1.35;

export interface Highlight {
  page_no: number;
  bbox: BBox;
}

export function PdfProof({
  tenderId,
  highlight,
}: {
  tenderId: string;
  highlight: Highlight | null;
}) {
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let loaded: PDFDocumentProxy | null = null;
    (async () => {
      try {
        const data = await fetchDocumentBlob(tenderId);
        const pdf = await pdfjsLib.getDocument({ data }).promise;
        loaded = pdf;
        if (cancelled) {
          pdf.destroy();
          return;
        }
        setPageCount(pdf.numPages);
        setDoc(pdf);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
      loaded?.destroy();
      setDoc(null);
      setPageCount(0);
    };
  }, [tenderId]);

  useEffect(() => {
    if (!doc) return;
    let cancelled = false;
    let task: RenderTask | null = null;
    (async () => {
      try {
        for (let n = 1; n <= doc.numPages && !cancelled; n += 1) {
          const page = await doc.getPage(n);
          const viewport = page.getViewport({ scale: SCALE });
          const holder = pageRefs.current.get(n);
          const canvas = holder?.querySelector("canvas");
          const context = canvas?.getContext("2d");
          if (!holder || !canvas || !context) continue;
          holder.style.width = `${viewport.width}px`;
          holder.style.height = `${viewport.height}px`;
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          task = page.render({ canvasContext: context, viewport });
          await task.promise;
        }
      } catch (e) {
        const name = (e as { name?: string })?.name;
        if (!cancelled && name !== "RenderingCancelledException") {
          setError(String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
      try {
        task?.cancel();
      } catch {
        // already settled
      }
    };
  }, [doc]);

  useEffect(() => {
    if (!highlight) return;
    pageRefs.current
      .get(highlight.page_no)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlight]);

  if (error)
    return <p className="p-4 text-sm text-red-600">PDF failed to load: {error}</p>;

  return (
    <div className="h-full overflow-auto bg-slate-100 p-4">
      {Array.from({ length: Math.max(pageCount, 1) }, (_, i) => i + 1).map((n) => (
        <div
          key={n}
          ref={(node) => {
            if (node) pageRefs.current.set(n, node);
          }}
          className="relative mx-auto mb-4 bg-white shadow"
          data-page={n}
        >
          <canvas />
          {highlight?.page_no === n && (
            <div
              data-testid="proof-highlight"
              className="absolute border-2 border-amber-500 bg-amber-300/30"
              style={highlightRect(highlight.bbox, SCALE)}
            />
          )}
        </div>
      ))}
    </div>
  );
}
