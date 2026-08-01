// Shared motion. Every animation in BidProof starts here, so the product moves
// at one speed instead of at each screen's guess.
//
// The easing curve and the 0.55s duration are not new — they are lifted from
// `screens/Landing.tsx`, which had them right. Extracting rather than
// reinventing means the app and the landing page feel like one thing.
//
// Two rules hold everywhere:
//
// 1. **Motion says something or it does not happen.** Content arriving,
//    a number counting to its value, a proof box landing on a clause. Never
//    decoration for its own sake — this product sells certainty.
// 2. **Reduced motion is honoured in JS, not only CSS.** The
//    `prefers-reduced-motion` block in index.css cannot reach framer-motion's
//    inline transforms, so every component here checks `useReducedMotion` and
//    renders the final state directly.
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";

/** The product's easing curve: a confident start, a soft landing. */
export const EASE = [0.22, 0.61, 0.36, 1] as const;
export const DURATION = 0.55;

/** "Has this entered the viewport" — with a deadline.
 *
 *  Every reveal in this file starts at `opacity: 0` and waits for an
 *  IntersectionObserver. That is fine until the observer never fires, and it
 *  genuinely does not fire in some contexts — a background or non-compositing
 *  tab being the one we hit while building this. The failure mode is the worst
 *  available: the landing page renders, reports no error, and shows nothing.
 *
 *  So the wait has a deadline. If the observer has not spoken within
 *  `fallbackMs`, the content is shown anyway. An animation that does not play
 *  costs nothing; a page that never appears costs everything.
 */
export function useInViewOnce(
  ref: React.RefObject<Element | null>,
  { threshold = 0.15, fallbackMs = 1200 } = {},
): boolean {
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    if (seen) return;
    const node = ref.current;

    const observer =
      node && typeof IntersectionObserver !== "undefined"
        ? new IntersectionObserver(
            (entries) => {
              if (entries.some((e) => e.isIntersecting)) setSeen(true);
            },
            { threshold },
          )
        : null;
    observer?.observe(node!);

    const deadline = window.setTimeout(() => setSeen(true), fallbackMs);
    return () => {
      observer?.disconnect();
      window.clearTimeout(deadline);
    };
  }, [ref, seen, threshold, fallbackMs]);

  return seen;
}

/** Content arriving as it enters the viewport. Fires once — a screen that
 *  re-animates on every scroll is a screen nobody can read. */
export function Reveal({
  children,
  delay = 0,
  y = 18,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const still = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInViewOnce(ref);

  if (still) return <div className={className}>{children}</div>;

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y }}
      animate={seen ? { opacity: 1, y: 0 } : { opacity: 0, y }}
      transition={{ duration: DURATION, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** A list arriving one item after another.
 *
 *  `step` stays small: with twenty rows a 0.1s step means the last row lands
 *  two seconds late, which reads as slow software rather than as polish.
 */
export function Stagger({
  children,
  step = 0.04,
  className,
  as = "div",
}: {
  children: ReactNode[];
  step?: number;
  className?: string;
  /** The element to render — both for the container and for each item's
   *  wrapper. A `div` inside a `<ul>` is invalid markup and breaks list
   *  semantics for a screen reader, so a list passes `as="ul"` and gets
   *  `motion.li` children instead. */
  as?: "div" | "ul" | "ol";
}) {
  const still = useReducedMotion();
  const Container = as === "div" ? "div" : as;
  const Item = as === "div" ? motion.div : motion.li;

  if (still) return <Container className={className}>{children}</Container>;

  return (
    <Container className={className}>
      {children.map((child, i) => (
        <Item
          key={i}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            // Cap the cascade so a long list still finishes promptly.
            delay: Math.min(i * step, 0.5),
            duration: 0.35,
            ease: EASE,
          }}
        >
          {child}
        </Item>
      ))}
    </Container>
  );
}

/** A number counting up to its value.
 *
 *  Used only for figures that carry weight — expected value in rupees, tenders
 *  found, hours saved. The final value is always rendered as real text so a
 *  screen reader and a test see the number, not an animation.
 */
export function CountUp({
  to,
  duration = 900,
  format = (n: number) => n.toLocaleString("en-IN"),
  className,
}: {
  to: number;
  duration?: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const still = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  // Shares the deadline: a headline reading "0 pages read per tender" because
  // an observer stayed quiet is worse than no animation at all.
  const inView = useInViewOnce(ref);
  const [shown, setShown] = useState(still ? to : 0);

  useEffect(() => {
    if (still || !inView) return;
    let raf = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - started) / duration, 1);
      // Ease-out cubic: fast enough to feel responsive, slow enough at the end
      // that the final digits are readable rather than a blur.
      setShown(Math.round(to * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, still, to, duration]);

  return (
    <span ref={ref} data-numeric className={className}>
      {format(still ? to : shown)}
    </span>
  );
}

/** A section that fades its whole band in — used between landing sections and
 *  around dark-register panels, where a per-child stagger would be noise. */
export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const still = useReducedMotion();
  if (still) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
