import React from 'react'
import { cn } from './cn'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated'
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ variant = 'default', className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-xl bg-slate-dark border border-topo/30 overflow-hidden',
        {
          'shadow-lg shadow-orange/10': variant === 'elevated',
        },
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
)

Card.displayName = 'Card'
