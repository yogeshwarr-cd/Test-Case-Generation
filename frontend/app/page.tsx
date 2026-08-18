'use client';

import React, { useEffect, useRef, useState } from 'react';
import Lenis from 'lenis';
import { motion } from 'framer-motion';
import Image from 'next/image';
import Link from 'next/link';
import {
  Upload,
  Search,
  BrainCircuit,
  ShieldCheck,
  FileText,
  ChevronDown,
  ArrowRight,
  Shield,
  Users,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles
} from 'lucide-react';
import { useInView } from 'react-intersection-observer';
import { ThemeToggle } from '@/components/theme-toggle';
import { useTheme } from 'next-themes';

const wordVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 }
};

export default function LandingPage() {
  const vantaRef = useRef<{ destroy: () => void; setOptions: (opts: Record<string, unknown>) => void } | null>(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      wheelMultiplier: 1,
      touchMultiplier: 2,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    const loadScript = (src: string) => {
      return new Promise<void>((resolve, reject) => {
        if (document.querySelector(`script[src="${src}"]`)) {
          resolve();
          return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.onload = () => resolve();
        script.onerror = reject;
        document.body.appendChild(script);
      });
    };

    const initVanta = async () => {
      try {
        await loadScript("https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js");
        await loadScript("https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.fog.min.js");
        /* eslint-disable @typescript-eslint/no-explicit-any */
        if ((window as any).VANTA && !vantaRef.current) {
          const isDark = resolvedTheme === 'dark';
          vantaRef.current = (window as any).VANTA.FOG({
            el: "#vanta-bg",
            mouseControls: true,
            touchControls: true,
            gyroControls: false,
            minHeight: 200.00,
            minWidth: 200.00,
            highlightColor: isDark ? 0x3b82f6 : 0xc8de,
            midtoneColor: isDark ? 0x1e293b : 0x137bea,
            lowlightColor: isDark ? 0x0f172a : 0xc0f7,
            baseColor: isDark ? 0x0b1121 : 0xffffff,
            speed: 2.00
          });
        }
        /* eslint-enable @typescript-eslint/no-explicit-any */
      } catch (err) {
        console.error("Vanta load error", err);
      }
    };
    initVanta();

    return () => {
      lenis.destroy();
      if (vantaRef.current) {
        vantaRef.current.destroy();
        vantaRef.current = null;
      }
    };
  }, [resolvedTheme]);

  const headlineText = "AI-Powered Test Case & Script Generation";
  const headlineWords = headlineText.split(" ");

  const howItWorksSteps = [
    { num: 1, icon: Upload, title: "Upload SRS", desc: "Upload PRD & requirements" },
    { num: 2, icon: Search, title: "Analyze", desc: "AI extracts features & epics" },
    { num: 3, icon: BrainCircuit, title: "Validate", desc: "INVEST criteria check" },
    { num: 4, icon: ShieldCheck, title: "Generate", desc: "User stories & test cases" },
    { num: 5, icon: FileText, title: "Automate", desc: "Executable Playwright code" }
  ];

  const benefits = [
    { icon: BrainCircuit, title: "AI-Powered Intelligence", desc: "Advanced AI understands context and extracts key requirements." },
    { icon: ShieldCheck, title: "Quality You Can Trust", desc: "Built-in INVEST validation ensures accuracy and completeness." },
    { icon: Users, title: "Human-in-the-Loop Control", desc: "Review and refine stories and test scripts at every step." },
    { icon: Clock, title: "Save 80% BA & QA Time", desc: "Accelerate software delivery with automated Playwright suites." }
  ];

  const [refHowItWorks, inViewHowItWorks] = useInView({ triggerOnce: true, threshold: 0.1 });
  const [refBenefits, inViewBenefits] = useInView({ triggerOnce: true, threshold: 0.1 });

  return (
    <div className="min-h-screen font-sans bg-transparent text-foreground selection:bg-primary/30 transition-colors duration-300 relative">
      <div id="vanta-bg" className="fixed inset-0 z-[-1] w-full h-full" />
      
      {/* NAVBAR */}
      <nav className="fixed top-0 left-0 w-full h-[72px] bg-background/80 backdrop-blur-md z-50 flex items-center justify-between px-8 md:px-12 border-b border-border transition-colors">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-orange-500 via-purple-600 to-indigo-600 text-white shadow-md">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="font-extrabold text-lg tracking-tight text-foreground">Test Case Generator <span className="text-primary text-xs">AI</span></span>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />
        </div>
      </nav>

      {/* HERO SECTION */}
      <section className="relative w-full min-h-[90vh] flex flex-col items-center justify-center pt-32 pb-20 px-8 md:px-12 mt-16 overflow-hidden">
        <div className="relative z-10 max-w-6xl mx-auto w-full flex flex-col items-start min-h-[calc(90vh-220px)]">
          <div className="flex flex-col items-start max-w-2xl">
            <span className="inline-flex items-center gap-2 rounded-full bg-purple-500/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-purple-500 border border-purple-500/20 mb-4">
              <Sparkles className="h-3.5 w-3.5" /> Next-Gen AI Test Case & Script Engine
            </span>
            <motion.h1 
              className="text-foreground font-extrabold text-4xl sm:text-5xl lg:text-6xl leading-tight text-left tracking-tight"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.04 } } }}
            >
              {headlineWords.map((word, i) => (
                <motion.span key={i} className="inline-block mr-3" variants={wordVariants}>
                  {word}
                </motion.span>
              ))}
            </motion.h1>
            
            <p className="text-muted-foreground text-base leading-relaxed text-left mt-6">
              Transform software requirement specifications into comprehensive test scenarios, functional test cases, and executable Playwright automation test scripts in seconds.
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-4 mt-10">
            <Link href="/dashboard" className="inline-flex items-center gap-2.5 bg-gradient-to-r from-orange-500 via-purple-600 to-indigo-600 text-white px-7 py-3.5 rounded-2xl font-bold text-sm shadow-xl shadow-purple-500/25 hover:scale-[1.02] transition-all">
              Launch Workspace <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/test-case-generation" className="inline-flex items-center gap-2 border border-border bg-card/80 backdrop-blur-md px-6 py-3.5 rounded-2xl font-bold text-sm hover:bg-muted transition">
              New Test Generator
            </Link>
          </div>

          {/* HOW IT WORKS CARDS */}
          <div ref={refHowItWorks} className="w-full mt-20 grid grid-cols-2 md:grid-cols-5 gap-4">
            {howItWorksSteps.map((step, idx) => {
              const Icon = step.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20 }}
                  animate={inViewHowItWorks ? { opacity: 1, y: 0 } : {}}
                  transition={{ delay: idx * 0.1 }}
                  className="rounded-2xl border border-border/70 bg-card/70 p-4 backdrop-blur-sm shadow-sm flex flex-col justify-between"
                >
                  <div className="flex justify-between items-center mb-3">
                    <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-xs">
                      {step.num}
                    </span>
                    <Icon className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-foreground">{step.title}</h3>
                    <p className="text-[11px] text-muted-foreground mt-0.5">{step.desc}</p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}
