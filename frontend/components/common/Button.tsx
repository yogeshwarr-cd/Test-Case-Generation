'use client';

import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, className = '', variant = 'primary', size = 'md', loading = false, disabled, type = 'button', ...props }, ref) => {
    const baseStyle = 'inline-flex min-h-10 items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[.98] disabled:pointer-events-none disabled:opacity-50';
    
    const variants = {
      primary: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90',
      secondary: 'border border-border bg-background text-foreground shadow-sm hover:bg-muted',
      danger: 'bg-red-600 text-white shadow-sm hover:bg-red-700',
      ghost: 'bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground'
    };

    const sizes = {
      sm: 'min-h-8 px-3 py-1.5 text-xs',
      md: 'px-4 py-2 text-sm',
      lg: 'min-h-12 px-5 py-2.5 text-base'
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />}
        <span>{children}</span>
      </button>
    );
  }
);

Button.displayName = 'Button';
