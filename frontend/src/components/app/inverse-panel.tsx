import { Fragment, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function InversePanel({
  className,
  children,
  as: Tag = 'div',
}: {
  className?: string
  children: ReactNode
  as?: 'div' | 'section' | 'aside'
}) {
  return (
    <Tag className={cn('bg-inverse text-inverse-foreground', className)}>{children}</Tag>
  )
}

export function FlowChain({ steps, invert }: { steps: string[]; invert?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {steps.map((step, i) => (
        <Fragment key={step}>
          <span
            className={cn(
              'rounded-none border px-3 py-1',
              invert
                ? cn(
                    'border-inverse-border',
                    i === steps.length - 1 && 'bg-inverse-foreground text-inverse',
                  )
                : cn(
                    'border-border',
                    i === steps.length - 1 && 'bg-primary text-primary-foreground',
                  ),
            )}
          >
            {step}
          </span>
          {i < steps.length - 1 && (
            <span
              aria-hidden="true"
              className={cn('h-px w-6', invert ? 'bg-inverse-foreground/50' : 'bg-foreground/40')}
            />
          )}
        </Fragment>
      ))}
    </div>
  )
}
