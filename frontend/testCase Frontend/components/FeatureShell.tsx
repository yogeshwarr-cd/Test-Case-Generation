'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import { FlaskConical, FolderKanban, Home, Menu, PanelLeftClose, PanelLeftOpen, Sparkles, X } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { ScrollToBottomButton } from './ScrollToBottomButton';
import styles from './PremiumShell.module.css';

const navigation = [
  { href: '/test-case-generation', label: 'Create', icon: Sparkles, exact: true },
  { href: '/dashboard', label: 'Projects', icon: FolderKanban, exact: false },
  { href: '/', label: 'Home', icon: Home, exact: true },
];

export function FeatureShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const reducedMotion = useReducedMotion();
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const x = useSpring(pointerX, { stiffness: 38, damping: 24, mass: 1.2 });
  const y = useSpring(pointerY, { stiffness: 38, damping: 24, mass: 1.2 });

  useEffect(() => {
    if (reducedMotion) return;
    const move = (event: PointerEvent) => {
      pointerX.set((event.clientX / window.innerWidth - 0.5) * 34);
      pointerY.set((event.clientY / window.innerHeight - 0.5) * 34);
    };
    window.addEventListener('pointermove', move, { passive: true });
    return () => window.removeEventListener('pointermove', move);
  }, [pointerX, pointerY, reducedMotion]);

  return (
    <div className={styles.experience}>
      <div className={styles.ambient} aria-hidden="true">
        <div className={styles.grid} />
        <motion.div className={styles.orb} style={reducedMotion ? undefined : { x, y }} />
        <div className={styles.ring} />
      </div>

      <button type="button" className={styles.mobileMenuButton} onClick={() => setMobileOpen(true)} aria-label="Open navigation" aria-expanded={mobileOpen}><Menu className="h-5 w-5" /></button>
      {mobileOpen && <button type="button" className={styles.sidebarBackdrop} onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}

      <aside className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''} ${mobileOpen ? styles.sidebarOpen : ''}`} aria-label="Primary navigation">
        <div className={styles.sidebarBrand}>
          <span className={styles.brandMark}><FlaskConical className="h-5 w-5" /></span>
          <div className={styles.brandCopy}>
            <Image src="/images_and_videos/logo.png" alt="BA Accelerator" width={128} height={34} priority className="h-7 w-auto object-contain dark:invert dark:brightness-200" />
            <span>Generate · Validate · Execute</span>
          </div>
          <button type="button" className={styles.mobileClose} onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X className="h-5 w-5" /></button>
        </div>

        <div className={styles.sidebarDivider} />
        <p className={styles.sidebarLabel}>Workspace</p>
        <nav className={styles.sidebarNav}>
          {navigation.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname.startsWith(href);
            return <Link key={href} href={href} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined} aria-current={active ? 'page' : undefined} className={`${styles.sidebarLink} ${active ? styles.sidebarActive : ''}`}><Icon className="h-5 w-5 shrink-0" /><span>{label}</span></Link>;
          })}
        </nav>

        <div className={styles.sidebarFooter}>
          <div className={styles.themeRow}><ThemeToggle /><span>Appearance</span></div>
          <button type="button" className={styles.collapseButton} onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : undefined}>
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}<span>{collapsed ? 'Expand' : 'Collapse sidebar'}</span>
          </button>
        </div>
      </aside>

      <main className={`${styles.main} ${collapsed ? styles.mainCollapsed : ''}`}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={pathname}
            className={styles.route}
            initial={reducedMotion ? false : { opacity: 0, y: 22, filter: 'blur(8px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={reducedMotion ? undefined : { opacity: 0, y: -12, filter: 'blur(5px)' }}
            transition={{ duration: reducedMotion ? 0 : 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
      <ScrollToBottomButton />
    </div>
  );
}
