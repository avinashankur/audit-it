import { cn } from '@/lib/utils'

type Size = 'sm' | 'md' | 'lg'

const sizes: Record<Size, string> = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-lg',
}

export function Num({
  value,
  size = 'sm',
  align = 'right',
  muted,
  className,
  title,
}: {
  value: string | number
  size?: Size
  align?: 'left' | 'right'
  muted?: boolean
  className?: string
  title?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        'font-mono tabular-nums',
        sizes[size],
        align === 'right' ? 'text-right' : 'text-left',
        muted && 'text-muted-foreground',
        className,
      )}
    >
      {value}
    </span>
  )
}
