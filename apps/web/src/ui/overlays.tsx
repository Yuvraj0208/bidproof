// Overlays: Toast, Modal, Tooltip.
// Motion is 150–250ms and never bounces — an enterprise tool should feel
// quick and certain, not springy (SPEC §17: calm, confident).
import { AnimatePresence, motion } from "framer-motion";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Button } from "./primitives";

/* ------------------------------- Toast ---------------------------------- */

export interface ToastMessage {
  id: number;
  text: string;
  tone: "info" | "success" | "warning" | "danger";
}

const ToastContext = createContext<{
  push: (text: string, tone?: ToastMessage["tone"]) => void;
}>({ push: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastHost({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastMessage[]>([]);

  const push = useCallback(
    (text: string, tone: ToastMessage["tone"] = "info") => {
      const id = Date.now() + Math.random();
      setItems((current) => [...current, { id, text, tone }]);
      window.setTimeout(
        () => setItems((current) => current.filter((t) => t.id !== id)),
        4500,
      );
    },
    [],
  );

  const value = useMemo(() => ({ push }), [push]);
  const tones: Record<string, string> = {
    info: "border-hairline bg-white text-ink",
    success: "border-success/25 bg-success-tint text-success",
    warning: "border-warning/25 bg-warning-tint text-warning",
    danger: "border-danger/25 bg-danger-tint text-danger",
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2"
        role="status"
        aria-live="polite"
      >
        <AnimatePresence>
          {items.map((item) => (
            <motion.div
              key={item.id}
              data-testid="toast"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className={`pointer-events-auto max-w-sm rounded-[12px] border px-3 py-2 text-sm shadow-overlay ${tones[item.tone]}`}
            >
              {item.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

/* ------------------------------- Modal ---------------------------------- */

export function Modal({
  open,
  title,
  children,
  onClose,
  footer,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
        >
          <div
            className="absolute inset-0 bg-ink/35 backdrop-blur-[2px]"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            data-testid="modal"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, scale: 0.985, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.99, y: 4 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-10 w-full max-w-lg rounded-[16px] border border-hairline bg-white shadow-modal"
          >
            <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">{title}</h2>
              <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
                ✕
              </Button>
            </div>
            <div className="px-4 py-4 text-sm text-ink">{children}</div>
            {footer && (
              <div className="flex justify-end gap-2 border-t border-hairline px-4 py-3">
                {footer}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------ Tooltip --------------------------------- */

/** CSS-only hover/focus tooltip — no portal, no positioning library, and it
 *  works for keyboard users because it triggers on focus-within too. */
export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <span className="group relative inline-flex focus-within:z-20">
      {children}
      <span
        role="tooltip"
        data-testid="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded-[8px] border border-hairline bg-white px-2 py-1 text-xs text-ink shadow-overlay group-hover:block group-focus-within:block"
      >
        {label}
      </span>
    </span>
  );
}
