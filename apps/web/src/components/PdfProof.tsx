// The proof pane (US-04): renders the tender PDF with pdf.js and, when a
// rule is clicked, scrolls to its page and draws the highlight box over the
// exact element the rule cites.
import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
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
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [pageCount, setPageCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchDocumentBlob(tenderId);
        const pdf = await pdfjsLib.getDocument({ data }).promise;
        if (cancelled) return;
        setPageCount(pdf.numPages);
        for (let n = 1; n <= pdf.numPages; n += 1) {
          const page = await pdf.getPage(n);
          const viewport = page.getViewport({ scale: SCALE });
          const holder = pageRefs.current.get(n);
          if (!holder) continue;
          holder.style.width = `${viewport.width}px`;
          holder.style.height = `${viewport.height}px`;
          const canvas = holder.querySelector("canvas");
          if (!canvas) continue;
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          const context = canvas.getContext("2d");
          if (!context) continue;
          await page.render({ canvasContext: context, viewport }).promise;
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenderId, pageCount === 0]);

  useEffect(() => {
    if (!highlight) return;
    const holder = pageRefs.current.get(highlight.page_no);
    holder?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlight]);

  if (error)
    return <p className="p-4 text-sm text-red-600">PDF failed to load: {error}</p>;

  return (
    <div ref={containerRef} className="h-full overflow-auto bg-slate-100 p-4">
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
              className="absolute animate-pulse border-2 border-amber-500 bg-amber-300/30"
              style={highlightRect(highlight.bbox, SCALE)}
            />
          )}
        </div>
      ))}
    </div>
  );
}
