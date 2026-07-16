"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="w-7 h-7 rounded-full border border-border flex items-center justify-center bg-transparent">
        <div className="w-[14px] h-[14px]" />
      </div>
    );
  }

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="relative w-7 h-7 rounded-full border border-border flex items-center justify-center bg-background hover:bg-muted text-foreground transition-colors hover:text-primary"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? (
        <Sun className="h-[14px] w-[14px] transition-all" />
      ) : (
        <Moon className="h-[14px] w-[14px] transition-all" />
      )}
      <span className="sr-only">Toggle theme</span>
    </button>
  );
}
