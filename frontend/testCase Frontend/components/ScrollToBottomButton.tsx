'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';

const BOTTOM_THRESHOLD = 72;

function canScroll(element: HTMLElement) {
  if (element.scrollHeight - element.clientHeight <= BOTTOM_THRESHOLD) return false;
  if (element === document.scrollingElement) return true;
  const overflow = window.getComputedStyle(element).overflowY;
  return overflow === 'auto' || overflow === 'scroll';
}

function findScrollContainer(source?: EventTarget | null): HTMLElement {
  const documentScroller = document.scrollingElement as HTMLElement;
  if (source instanceof HTMLElement) {
    let current: HTMLElement | null = source;
    while (current && current !== document.body) {
      if (canScroll(current)) return current;
      current = current.parentElement;
    }
  }

  const candidates = Array.from(document.querySelectorAll<HTMLElement>('*'))
    .filter((element) => canScroll(element) && element.getClientRects().length > 0)
    .sort((left, right) => {
      const leftScore = (left.scrollHeight - left.clientHeight) * Math.max(left.clientWidth, 1);
      const rightScore = (right.scrollHeight - right.clientHeight) * Math.max(right.clientWidth, 1);
      return rightScore - leftScore;
    });

  if (canScroll(documentScroller)) return documentScroller;
  return candidates[0] ?? documentScroller;
}

function isDocumentScrollSource(source?: EventTarget | null) {
  return source === document
    || source === window
    || source === document.documentElement
    || source === document.body;
}

export function ScrollToBottomButton() {
  const reducedMotion = useReducedMotion();
  const targetRef = useRef<HTMLElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const [visible, setVisible] = useState(false);

  const update = useCallback((source?: EventTarget | null) => {
    const current = targetRef.current;
    const target = isDocumentScrollSource(source)
      ? document.scrollingElement as HTMLElement
      : source instanceof HTMLElement
      ? findScrollContainer(source)
      : current && canScroll(current) ? current : findScrollContainer(source);
    targetRef.current = target;
    const scrollTop = target === document.scrollingElement ? window.scrollY : target.scrollTop;
    const remaining = target.scrollHeight - target.clientHeight - scrollTop;
    setVisible(target.scrollHeight > target.clientHeight + BOTTOM_THRESHOLD && remaining > BOTTOM_THRESHOLD);
  }, []);

  useEffect(() => {
    const scheduleUpdate = (event?: Event) => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      frameRef.current = requestAnimationFrame(() => {
        frameRef.current = null;
        update(event?.target);
      });
    };
    const observer = new ResizeObserver(() => scheduleUpdate());
    observer.observe(document.documentElement);
    window.addEventListener('resize', scheduleUpdate, { passive: true });
    document.addEventListener('scroll', scheduleUpdate, { passive: true, capture: true });
    scheduleUpdate();
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', scheduleUpdate);
      document.removeEventListener('scroll', scheduleUpdate, true);
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [update]);

  const scrollToBottom = () => {
    const target = targetRef.current ?? findScrollContainer();
    const behavior = reducedMotion ? 'auto' : 'smooth';
    if (target === document.scrollingElement) {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior });
    } else {
      target.scrollTo({ top: target.scrollHeight, behavior });
    }
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          type="button"
          aria-label="Scroll to bottom"
          title="Scroll to bottom"
          onClick={scrollToBottom}
          initial={reducedMotion ? false : { opacity: 0, scale: 0.82, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.82, y: 8 }}
          whileHover={reducedMotion ? undefined : { scale: 1.08, y: -2 }}
          whileTap={reducedMotion ? undefined : { scale: 0.94 }}
          transition={{ duration: reducedMotion ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-[max(1.25rem,env(safe-area-inset-bottom))] left-1/2 z-[80] -ml-5 flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-slate-950/80 text-white shadow-[0_10px_35px_rgba(2,6,23,.35)] backdrop-blur-xl hover:border-primary/50 hover:bg-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:bottom-7"
        >
          <ArrowDown className="h-4 w-4" strokeWidth={2.25} aria-hidden="true" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
