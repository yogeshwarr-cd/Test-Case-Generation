'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import {
  Code2,
  FileCheck2,
  FolderKanban,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Sparkles,
  X
} from 'lucide-react';
import { ThemeToggle } from '@/components/theme-toggle';
import { NewProjectModal } from '@/components/projects/NewProjectModal';
import { ScrollToBottomButton } from './ScrollToBottomButton';
import styles from './PremiumShell.module.css';

const navigation = [
  { href: '/dashboard', label: 'Dashboard', icon: FolderKanban, exact: true },
  { href: '/test-case-generation', label: 'New Generator', icon: Plus, exact: true },
  { href: '/test-case-generation/results', label: 'Generated Tests', icon: FileCheck2, exact: false },
  { href: '/test-case-generation/automation', label: 'Playwright Studio', icon: Code2, exact: false },
  { href: '/test-case-generation/url-crawler', label: 'App Crawler', icon: Sparkles, exact: false },
];

export function FeatureShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [globalQuery, setGlobalQuery] = useState('');

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

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (globalQuery.trim()) {
      router.push(`/dashboard?q=${encodeURIComponent(globalQuery.trim())}`);
    }
  };

  return (
    <div className={styles.experience}>
      <div className={styles.ambient} aria-hidden="true">
        <div className={styles.grid} />
        <motion.div className={styles.orb} style={reducedMotion ? undefined : { x, y }} />
        <div className={styles.ring} />
      </div>

      <button type="button" className={styles.mobileMenuButton} onClick={() => setMobileOpen(true)} aria-label="Open navigation" aria-expanded={mobileOpen}>
        <Menu className="h-5 w-5" />
      </button>

      {mobileOpen && <button type="button" className={styles.sidebarBackdrop} onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}

      {/* STORYFORGE AI INSPIRED DARK SLATE SIDEBAR */}
      <aside className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''} ${mobileOpen ? styles.sidebarOpen : ''}`} aria-label="Primary navigation">
        <div className={styles.sidebarBrand}>
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-orange-500 via-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-500/30 shrink-0">
            <Sparkles className="h-5 w-5" />
          </span>
          <div className={styles.brandCopy}>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold tracking-tight text-white text-base">TestCase Engine</span>
              <span className="rounded-md bg-purple-500/20 px-1.5 py-0.5 text-[10px] font-bold text-purple-300">AI</span>
            </div>
            <span className="text-[11px] text-slate-400 font-medium">Test Script Generator</span>
          </div>
          <button type="button" className={styles.mobileClose} onClick={() => setMobileOpen(false)} aria-label="Close navigation">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className={styles.sidebarDivider} />
        <p className={styles.sidebarLabel}>Test Automation Workspace</p>

        <nav className={styles.sidebarNav}>
          {navigation.map(({ href, label, icon: Icon, exact }) => {
            const active = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                title={collapsed ? label : undefined}
                aria-current={active ? 'page' : undefined}
                className={`${styles.sidebarLink} ${active ? styles.sidebarActive : ''}`}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className={styles.sidebarFooter}>
          <button
            type="button"
            className={styles.collapseButton}
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : undefined}
          >
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
            <span>{collapsed ? 'Expand' : 'Collapse'}</span>
          </button>
        </div>
      </aside>

      {/* TOP NAVIGATION BAR & CONTENT WRAPPER */}
      <div className={`flex flex-col min-h-screen transition-all duration-300 ${collapsed ? 'lg:pl-20' : 'lg:pl-[280px]'}`}>
        {/* Top Navbar */}
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-border/60 bg-background/80 px-6 backdrop-blur-md transition-colors">
          <form onSubmit={handleGlobalSearch} className="relative w-full max-w-md hidden sm:block">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={globalQuery}
              onChange={(e) => setGlobalQuery(e.target.value)}
              placeholder="Search projects, user stories, Playwright scripts..."
              className="h-10 w-full rounded-full border border-border/70 bg-card/60 pl-10 pr-12 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition"
            />
            <span className="absolute right-3.5 top-1/2 -translate-y-1/2 rounded border border-border/80 bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">⌘K</span>
          </form>

          <div className="flex items-center gap-3 ml-auto">
            {/* Quick Create Action */}
            <button
              onClick={() => setShowNewProjectModal(true)}
              className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-orange-500 to-purple-600 px-4 py-2 text-xs font-bold text-white shadow-md shadow-orange-500/15 hover:opacity-95 transition"
            >
              <Plus className="h-3.5 w-3.5" /> New Project
            </button>



            <ThemeToggle />

            {/* Profile Avatar Section */}
            <div className="flex items-center gap-2.5 pl-2 border-l border-border/60">
              <div className="h-9 w-9 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 p-0.5 shadow-sm">
                <img
                  src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=120"
                  alt="Sarah Jenkins"
                  className="h-full w-full rounded-full object-cover"
                />
              </div>
              <div className="hidden lg:flex flex-col text-left">
                <span className="text-xs font-bold text-foreground leading-tight">Sarah Jenkins</span>
                <span className="text-[10px] font-medium text-muted-foreground">Lead QA Automation Engineer</span>
              </div>
            </div>
          </div>
        </header>

        {/* Route Content Container */}
        <main className="flex-1 p-4 md:p-8">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={pathname}
              className={styles.route}
              initial={reducedMotion ? false : { opacity: 0, y: 16, filter: 'blur(6px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={reducedMotion ? undefined : { opacity: 0, y: -10, filter: 'blur(4px)' }}
              transition={{ duration: reducedMotion ? 0 : 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      <ScrollToBottomButton />
      <NewProjectModal isOpen={showNewProjectModal} onClose={() => setShowNewProjectModal(false)} />
    </div>
  );
}
