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
  Check,
  Calendar,
  Clock,
  Layers
} from 'lucide-react';
import { useInView } from 'react-intersection-observer';
import { ThemeToggle } from '@/components/theme-toggle';
import { useTheme } from 'next-themes';

// Reusable word animation variant for headlines
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
    // Lenis smooth scroll setup
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

    // Vanta Setup - sequential script loading
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
  // Run once on mount only
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update Vanta options when theme changes
  useEffect(() => {
    if (vantaRef.current) {
      if (resolvedTheme === 'dark') {
        vantaRef.current.setOptions({
          highlightColor: 0x3b82f6,
          midtoneColor: 0x1e293b,
          lowlightColor: 0x0f172a,
          baseColor: 0x0b1121
        });
      } else {
        vantaRef.current.setOptions({
          highlightColor: 0xc8de,
          midtoneColor: 0x137bea,
          lowlightColor: 0xc0f7,
          baseColor: 0xffffff
        });
      }
    }
  }, [resolvedTheme]);

  const headlineText = "From Requirements to Ready-to-Ship User Stories";
  const headlineWords = headlineText.split(" ");



  const howItWorksSteps = [
    { num: 1, icon: Upload, title: "Upload", desc: "Upload your PRD\ndocuments" },
    { num: 2, icon: Search, title: "Analyze", desc: "AI extracts and\nanalyzes requirements" },
    { num: 3, icon: BrainCircuit, title: "Structure", desc: "Organize and structure\nkey information" },
    { num: 4, icon: ShieldCheck, title: "Validate", desc: "AI validation ensures\nquality & completeness" },
    { num: 5, icon: FileText, title: "Generate", desc: "Generate user stories\nready for development" }
  ];

  const benefits = [
    { icon: BrainCircuit, title: "AI-Powered Intelligence", desc: "Advanced AI understands context and extracts what matters most." },
    { icon: ShieldCheck, title: "Quality You Can Trust", desc: "Built-in validation ensures accuracy, completeness, and consistency." },
    { icon: Users, title: "Human-in-the-Loop Control", desc: "Maintain full control with review and approval at every critical step." },
    { icon: Clock, title: "Save Time, Deliver Faster", desc: "Automate analysis and accelerate your delivery pipeline significantly." }
  ];

  const [refHowItWorks, inViewHowItWorks] = useInView({ triggerOnce: true, threshold: 0.1 });
  const [refBenefits, inViewBenefits] = useInView({ triggerOnce: true, threshold: 0.1 });

  return (
    <div className="min-h-screen font-sans bg-transparent text-foreground selection:bg-primary/30 transition-colors duration-300 relative">
      
      {/* VANTA BG */}
      <div id="vanta-bg" className="fixed inset-0 z-[-1] w-full h-full" />
      
      {/* SECTION 1 - NAVBAR */}
      <nav className="fixed top-0 left-0 w-full h-[72px] bg-background z-50 flex items-center justify-between px-[48px] border-b border-border transition-colors duration-300">
        <div className="flex items-center">
          <Image src="/images_and_videos/logo.png" alt="BA Accelerator Logo" width={120} height={32} className="h-8 w-auto dark:invert dark:brightness-200" priority />
        </div>
        
        <div className="hidden md:flex items-center gap-[32px]">
          {['Features', 'How It Works', 'Benefits', 'About'].map((item) => (
            <a key={item} href="#" className="relative group text-[15px] text-foreground hover:text-primary font-semibold flex items-center transition-colors">
              {item}
              <span className="absolute -bottom-1 left-0 w-full h-[2px] bg-primary origin-center scale-x-0 transition-transform duration-300 ease-out group-hover:scale-x-100"></span>
            </a>
          ))}
          <a href="#" className="relative group text-[15px] text-foreground hover:text-primary font-semibold flex items-center transition-colors">
            Resources <ChevronDown className="ml-1 w-4 h-4 text-foreground group-hover:text-primary transition-colors" />
            <span className="absolute -bottom-1 left-0 w-full h-[2px] bg-primary origin-center scale-x-0 transition-transform duration-300 ease-out group-hover:scale-x-100"></span>
          </a>
        </div>

        <div className="flex items-center gap-[12px]">
          <ThemeToggle />
          <Link href="/login" className="px-[20px] py-[10px] rounded-lg border border-border text-[15px] font-semibold text-foreground hover:bg-muted hover:text-primary transition-colors">
            Log in
          </Link>
          <Link href="/register" className="relative overflow-hidden group px-[20px] py-[10px] rounded-lg bg-primary text-primary-foreground text-[15px] font-semibold hover:scale-[1.02] transition-transform duration-150 shadow-md shadow-primary/20 block text-center">
            <span className="relative z-10">Get Started</span>
            <span className="absolute inset-0 -translate-x-full group-hover:translate-x-[200%] transition-transform duration-1000 ease-in-out bg-gradient-to-r from-transparent via-white/20 to-transparent w-1/2 skew-x-12 z-0"></span>
          </Link>
        </div>
      </nav>

      {/* SECTION 2 - HERO */}
      <section className="relative w-full min-h-[90vh] flex flex-col items-center justify-center pt-[140px] pb-[80px] px-[48px] mt-[72px] overflow-hidden">
        
        {/* Background Video with seamless fade to Vanta BG */}
        <div className="absolute inset-0 z-0 [mask-image:linear-gradient(to_bottom,white_80%,transparent_100%)]">
          {mounted && (
            <video 
              key={resolvedTheme === 'dark' ? 'dark' : 'light'}
              src={resolvedTheme === 'dark' ? "/images_and_videos/dark-theme-bg-video.mp4" : "/images_and_videos/light-theme-bg-video.mp4"}
              autoPlay 
              muted 
              loop 
              playsInline
              className="w-full h-full object-cover"
            />
          )}
          {/* Brighter overlay in light theme, consistent in dark theme */}
          <div className="absolute inset-0 bg-black/10 dark:bg-black/40"></div>
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/40 dark:to-black/80"></div>
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-[1280px] mx-auto w-full flex flex-col items-start min-h-[calc(90vh-220px)]">
          
          <div className="flex flex-col items-start">
            <motion.h1 
              className="text-white font-bold text-[36px] lg:text-[48px] leading-[1.1] max-w-[500px] text-left drop-shadow-md"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.03 } } }}
            >
              {headlineWords.map((word, i) => (
                <motion.span key={i} className="inline-block mr-[12px]" variants={wordVariants}>
                  {word}
                </motion.span>
              ))}
            </motion.h1>
            
            <motion.p 
              className="text-zinc-200 text-[16px] leading-[1.6] max-w-[450px] text-left mt-[24px]"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.6 }}
            >
              Analyze requirements, extract critical information, and generate high-quality, validated user stories in minutes.
            </motion.p>
          </div>
          
          <motion.div 
            className="flex flex-wrap items-center gap-[16px] mt-auto pb-[20px]"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7, duration: 0.6 }}
          >
            <Link href="/login" className="relative overflow-hidden group/btn bg-primary text-primary-foreground px-[24px] py-[12px] rounded-lg font-medium text-[15px] flex items-center gap-2 hover:scale-[1.02] transition-transform duration-150 shadow-lg shadow-primary/25">
              <span className="relative z-10 flex items-center gap-2">Get Started Free <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" /></span>
              <span className="absolute inset-0 -translate-x-full group-hover/btn:translate-x-[200%] transition-transform duration-1000 ease-in-out bg-gradient-to-r from-transparent via-white/20 to-transparent w-1/2 skew-x-12 z-0"></span>
            </Link>
            <Link href="/test-case-generation" className="relative overflow-hidden group/next border border-white/40 bg-white/10 text-white backdrop-blur-md px-[24px] py-[12px] rounded-lg font-medium text-[15px] flex items-center gap-2 hover:bg-white/20 hover:scale-[1.02] transition-all duration-150">
              <span className="relative z-10 flex items-center gap-2">Proceed Next <ArrowRight className="w-4 h-4 group-hover/next:translate-x-1 transition-transform" /></span>
            </Link>
          </motion.div>

          {/* TRUST BADGES */}
          <motion.div 
            className="w-full mt-[40px] flex items-center justify-start gap-[40px] flex-wrap"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5, duration: 1 }}
          >
            <div className="flex items-center gap-[8px] group">
              <Shield className="w-[16px] h-[16px] text-primary transition-colors" />
              <span className="text-[14px] text-zinc-300 group-hover:text-white transition-colors font-medium">Enterprise Ready</span>
            </div>
            <div className="flex items-center gap-[8px] group">
              <Users className="w-[16px] h-[16px] text-primary transition-colors" />
              <span className="text-[14px] text-zinc-300 group-hover:text-white transition-colors font-medium">Human-in-the-Loop</span>
            </div>
            <div className="flex items-center gap-[8px] group">
              <CheckCircle2 className="w-[16px] h-[16px] text-primary transition-colors" />
              <span className="text-[14px] text-zinc-300 group-hover:text-white transition-colors font-medium">Trusted Results</span>
            </div>
          </motion.div>

        </div>
      </section>

      {/* SECTION 3 - HOW IT WORKS */}
      <section className="bg-transparent py-[100px] px-[48px] w-full" ref={refHowItWorks}>
        <div className="max-w-[1280px] mx-auto w-full">
          <div className="flex flex-col items-center">
            <span className="text-[13px] text-primary uppercase tracking-widest font-bold text-center">How It Works</span>
            <h2 className="text-[32px] font-bold text-foreground mt-[12px] text-center">Simple. Intelligent. Effective.</h2>
          </div>
          
          <div className="mt-[64px] flex flex-row flex-wrap xl:flex-nowrap justify-center gap-[24px]">
            {howItWorksSteps.map((step, idx) => (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                animate={inViewHowItWorks ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
                transition={{ duration: 0.5, delay: idx * 0.08 }}
                whileHover={{ y: -8, transition: { duration: 0.2 } }}
                className="relative w-full max-w-[200px] bg-background/60 backdrop-blur-lg rounded-xl border border-border/50 p-[24px] flex flex-col items-center text-center shadow-sm hover:shadow-xl hover:shadow-primary/10 hover:border-primary/50 transition-all group"
              >
                <div className="absolute -top-[12px] w-[28px] h-[28px] bg-primary text-primary-foreground rounded-full flex items-center justify-center text-[13px] font-bold shadow-md shadow-primary/30 group-hover:scale-110 transition-transform">
                  {step.num}
                </div>
                <div className="w-[48px] h-[48px] rounded-full bg-primary/10 flex items-center justify-center mt-[8px] group-hover:bg-primary/20 transition-colors">
                  <step.icon className="w-[20px] h-[20px] text-primary" />
                </div>
                <h3 className="font-bold text-[16px] text-card-foreground mt-[16px] group-hover:text-primary transition-colors">{step.title}</h3>
                <p className="text-[13px] text-muted-foreground leading-[1.5] mt-[8px] whitespace-pre-line">{step.desc}</p>
                
                {idx < howItWorksSteps.length - 1 && (
                  <div className="hidden xl:flex absolute -right-[24px] top-1/2 -translate-y-1/2 w-[24px] justify-center z-10">
                    <ArrowRight className="w-[16px] h-[16px] text-muted-foreground/30 group-hover:text-primary/50 transition-colors" />
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 4 - KEY BENEFITS */}
      <section className="bg-transparent py-[100px] px-[48px] w-full" ref={refBenefits}>
        <div className="max-w-[1280px] mx-auto w-full">
          <div className="flex flex-col items-center">
            <span className="text-[13px] text-primary uppercase tracking-widest font-bold text-center">Key Benefits</span>
            <h2 className="text-[32px] font-bold text-foreground mt-[12px] text-center">Built for Modern Teams</h2>
          </div>

          <div className="mt-[64px] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-[24px]">
            {benefits.map((benefit, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={inViewBenefits ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                whileHover={{ scale: 1.03, transition: { duration: 0.2 } }}
                className="bg-background/60 backdrop-blur-lg rounded-xl border border-border/50 p-[32px] flex flex-col items-start shadow-sm hover:shadow-2xl hover:shadow-primary/20 hover:border-primary/50 transition-all group overflow-hidden relative"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="relative z-10">
                  <benefit.icon className="w-[28px] h-[28px] text-primary mb-[16px] group-hover:scale-110 transition-transform origin-left" />
                  <h3 className="font-bold text-[17px] text-card-foreground mb-[12px] group-hover:text-primary transition-colors">{benefit.title}</h3>
                  <p className="text-[14px] text-muted-foreground leading-[1.6]">{benefit.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 5 - CTA BANNER */}
      <section className="bg-transparent pb-[100px] px-[48px] w-full">
        <div className="max-w-[1280px] mx-auto w-full bg-background/60 backdrop-blur-lg border border-border/50 rounded-3xl p-[56px] flex flex-col md:flex-row items-center justify-between gap-[48px] shadow-2xl shadow-primary/5 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent opacity-50"></div>
          
          <div className="flex-1 relative z-10">
            <span className="text-[13px] text-primary uppercase tracking-widest font-bold">Ready to Accelerate?</span>
            <h2 className="text-[32px] font-bold text-foreground mt-[12px] leading-tight">Start turning requirements into results today.</h2>
            <p className="text-[15px] text-muted-foreground mt-[12px]">Join teams building better software, faster.</p>
          </div>
          
          <div className="flex flex-col items-start min-w-[320px] relative z-10">
            <div className="flex items-center gap-[12px] w-full mb-[24px]">
              <Link href="/login" className="flex-1 relative overflow-hidden group/btn bg-primary text-primary-foreground px-[20px] py-[14px] rounded-xl font-bold text-[15px] flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform duration-150 shadow-lg shadow-primary/30">
                <span className="relative z-10 flex items-center gap-2">Get Started Free <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" /></span>
                <span className="absolute inset-0 -translate-x-full group-hover/btn:translate-x-[200%] transition-transform duration-1000 ease-in-out bg-gradient-to-r from-transparent via-white/20 to-transparent w-1/2 skew-x-12 z-0"></span>
              </Link>
              <button className="flex-1 border border-border/50 bg-background/60 backdrop-blur-sm text-foreground px-[20px] py-[14px] rounded-xl font-bold text-[15px] flex items-center justify-center gap-2 hover:bg-muted/80 hover:border-primary/30 transition-all hover:scale-[1.02]">
                Schedule Demo <Calendar className="w-4 h-4 text-primary" />
              </button>
            </div>
            
            <div className="flex flex-col gap-[10px]">
              {['No credit card required', 'Free forever plan available', 'Setup in less than 2 minutes'].map((point, idx) => (
                <div key={idx} className="flex items-center gap-[10px]">
                  <div className="w-[20px] h-[20px] rounded-full bg-primary/10 flex items-center justify-center">
                    <Check className="w-[12px] h-[12px] text-primary" />
                  </div>
                  <span className="text-[14px] text-muted-foreground font-medium">{point}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 6 - FOOTER */}
      <footer className="bg-background/80 backdrop-blur-md border-t border-border py-[40px] px-[48px] w-full">
        <div className="max-w-[1280px] mx-auto w-full flex flex-col md:flex-row items-center justify-between gap-[24px]">
          <div className="flex flex-col items-center md:items-start gap-[12px]">
            <div className="flex items-center gap-3 group">
              <div className="w-8 h-8 bg-primary text-primary-foreground flex items-center justify-center rounded-[8px] group-hover:scale-110 transition-transform shadow-md shadow-primary/20">
                <Layers className="w-4 h-4" />
              </div>
              <span className="font-bold text-[16px] text-foreground">BA Accelerator</span>
            </div>
            <p className="text-[13px] text-muted-foreground">© 2024 BA Accelerator. All rights reserved.</p>
          </div>
          
          <div className="flex items-center gap-[32px]">
            <a href="#" className="text-[14px] font-medium text-muted-foreground hover:text-primary transition-colors">Privacy Policy</a>
            <a href="#" className="text-[14px] font-medium text-muted-foreground hover:text-primary transition-colors">Terms of Service</a>
            <a href="#" className="text-[14px] font-medium text-muted-foreground hover:text-primary transition-colors">Contact Us</a>
          </div>
        </div>
      </footer>

    </div>
  );
}
