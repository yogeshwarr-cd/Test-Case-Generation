import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from '@/components/theme-provider';
import { ConnectionToast } from '@/components/common/ConnectionToast';

export const metadata: Metadata = {
  title: 'BA Accelerator - Req2Plan AI SaaS Platform',
  description: 'AI-powered requirements extraction, INVEST validation, and story planning pipeline.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased transition-colors duration-300">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
          <ConnectionToast />
        </ThemeProvider>
      </body>
    </html>
  );
}
