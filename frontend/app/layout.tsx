import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from '@/components/theme-provider';
import { ConnectionToast } from '@/components/common/ConnectionToast';

export const metadata: Metadata = {
  title: 'Test Case Generator - AI SaaS Platform',
  description: 'AI-powered test scenario, test case generation, and Playwright test automation engine.',
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
