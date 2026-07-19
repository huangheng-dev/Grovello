import type { CSSProperties } from 'react'

export interface IconProps {
  name: string
  size?: number
  className?: string
  style?: CSSProperties
}

export function Icon({ name, size = 20, className = '', style }: IconProps) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined icon-symbol ${className}`.trim()}
      style={{ fontSize: size, ...style }}
    >
      {name}
    </span>
  )
}
