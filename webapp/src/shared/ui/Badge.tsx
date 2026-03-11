import React from 'react'
import { cn } from './cn'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', className, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        'inline-block px-2.5 py-1 rounded-full text-xs font-medium',
        {
          'bg-topo/40 text-gray-300': variant === 'default',
          'bg-canopy/20 text-canopy': variant === 'success',
          'bg-orange/20 text-orange': variant === 'warning',
          'bg-diamond-red/20 text-diamond-red': variant === 'error',
          'bg-collie-blue/20 text-collie-blue': variant === 'info',
        },
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
)

Badge.displayName = 'Badge'
