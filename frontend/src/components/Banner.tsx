import type { ReactNode } from 'react'

export function Wave({ fill = '#005baa' }: { fill?: string }) {
  return (
    <svg className="wave" viewBox="0 0 1440 80" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 46C160 22 330 18 520 34s390 40 600 20 260-36 320-30v56H0z" fill={fill} opacity="0.35" />
      <path d="M0 58c210-28 420-30 640-12s420 30 560 14 200-24 240-22v42H0z" fill={fill} />
    </svg>
  )
}

export function Banner({
  children,
  compact = false,
  waveFill,
}: {
  children: ReactNode
  compact?: boolean
  waveFill?: string
}) {
  return (
    <section className={`banner${compact ? ' banner--compact' : ''}`}>
      {!compact && (
        <div className="banner-bg-wrapper" aria-hidden="true">
          <img
            src="/hero-terraces.jpg"
            alt=""
            className="banner-bg-img"
            loading="eager"
          />
        </div>
      )}
      <div className="container banner-inner">{children}</div>
      {!compact && <Wave fill={waveFill} />}
    </section>
  )
}

/** Backward compatibility alias */
export const Skyline = () => null
