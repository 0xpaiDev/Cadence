import React from 'react'
import { cn } from './cn'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading = false, children, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed',
          {
            'bg-orange text-white hover:bg-orange/90': variant === 'primary',
            'bg-slate-dark text-gray-100 hover:bg-slate-dark/80 border border-topo': variant === 'secondary',
            'bg-diamond-red text-white hover:bg-diamond-red/90': variant === 'danger',
            'bg-canopy text-white hover:bg-canopy/90': variant === 'success',
            'px-3 py-2 text-sm': size === 'sm',
            'px-4 py-2 text-base': size === 'md',
            'px-6 py-3 text-lg w-full': size === 'lg',
          },
          className
        )}
        disabled={isLoading || props.disabled}
        {...props}
      >
        {isLoading ? '...' : children}
      </button>
    )
  }
)

Button.displayName = 'Button'
