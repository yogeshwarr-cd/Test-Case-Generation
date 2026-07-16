'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Globe } from 'lucide-react';
import { useTheme } from 'next-themes';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const vantaRef = useRef<{ destroy: () => void; setOptions: (opts: Record<string, unknown>) => void } | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
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

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }
    localStorage.setItem('auth_token', 'mock_session_token');
    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen bg-transparent transition-colors flex items-center justify-center px-4 relative">
      {/* VANTA BG */}
      <div id="vanta-bg" className="fixed inset-0 z-[-1] w-full h-full" />

      <div className="w-full max-w-md bg-card/90 backdrop-blur-md border border-border rounded-xl p-8 shadow-2xl space-y-6 text-foreground">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-10 h-10 bg-slate-950 dark:bg-slate-800 rounded-lg items-center justify-center text-sm font-black text-white mb-2">BA</div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">Welcome back</h2>
          <p className="text-xs text-muted-foreground">Sign in to manage your workspaces and stories</p>
        </div>

        {error && (
          <div className="bg-red-500/10 text-red-400 text-xs p-3 rounded-lg border border-red-500/20 text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-muted-foreground">Email Address</label>
            <input
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-background border border-input rounded-lg px-3 py-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          
          <div className="space-y-1">
            <label className="text-xs font-semibold text-muted-foreground">Password</label>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-background border border-input rounded-lg px-3 py-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <button 
            type="submit" 
            className="w-full inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 py-2.5 mt-2 bg-blue-600 hover:bg-blue-700 text-white cursor-pointer border-none text-sm"
          >
            Sign In with Email
          </button>
        </form>

        <div className="relative flex items-center justify-center my-4">
          <span className="absolute w-full border-t border-border" />
          <span className="relative bg-card px-3 text-[10px] text-muted-foreground uppercase">Or continue with</span>
        </div>

        <button 
          onClick={() => {
            localStorage.setItem('auth_token', 'mock_session_token');
            router.push('/dashboard');
          }}
          className="w-full flex items-center justify-center gap-2 bg-background hover:bg-muted border border-border text-foreground text-xs font-medium py-2.5 rounded-lg transition-colors cursor-pointer"
        >
          <Globe className="w-4 h-4 text-foreground" />
          Continue with Google
        </button>
      </div>
    </div>
  );
}
