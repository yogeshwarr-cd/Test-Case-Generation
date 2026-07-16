'use client';

import React from 'react';
import Link from 'next/link';

export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-background transition-colors flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl p-8 shadow-2xl space-y-6 text-center">
        <h2 className="text-2xl font-bold text-slate-950">Create Account</h2>
        <p className="text-xs text-slate-500">Sign up features are currently mocked.</p>
        <Link href="/login" className="text-xs text-[#6366f1] underline block">
          Back to Login
        </Link>
      </div>
    </div>
  );
}
