'use client';

import { useEffect, type ReactNode } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import { FileCode2, FlaskConical, FolderKanban, Globe, Home, Sparkles } from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { ScrollToBottomButton } from './ScrollToBottomButton';
import styles from './PremiumShell.module.css';

const navigation = [
  { href: '/test-case-generation', label: 'Create', icon: Sparkles, exact: true },
  { href: '/test-case-generation/results', label: 'Results', icon: FileCode2 },
  { href: '/test-case-generation/url-crawler', label: 'URL Crawler', icon: Globe },
];

export function FeatureShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
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

      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/test-case-generation" className={styles.brand} aria-label="Test Case Generation home">
            <span className={styles.brandMark}><FlaskConical className="h-4 w-4" /></span>
            <Image src="/images_and_videos/logo.png" alt="BA Accelerator" width={112} height={30} priority className="h-6 w-auto dark:invert dark:brightness-200" />
            <span className="hidden h-6 w-px bg-border lg:block" />
            <span className={`${styles.brandTitle} hidden lg:block`}>Test Intelligence</span>
          </Link>

          <div className="flex items-center gap-2">
            <nav className={styles.nav} aria-label="Test generation navigation">
              {navigation.map(({ href, label, icon: Icon, exact }) => {
                const active = exact ? pathname === href : pathname.startsWith(href);
                return <Link key={href} href={href} aria-current={active ? 'page' : undefined} className={`${styles.navLink} ${active ? styles.navActive : ''}`}><Icon className="h-4 w-4" /><span>{label}</span></Link>;
              })}
              <Link href="/dashboard" className={styles.navLink} aria-label="View all projects"><FolderKanban className="h-4 w-4" /><span>Projects</span></Link>
              <Link href="/" className={styles.navLink} aria-label="Main application home"><Home className="h-4 w-4" /><span>Home</span></Link>
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className={styles.main}>
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
