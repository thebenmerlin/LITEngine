/**
 * SVG semicircular gauge for judicial outcome prediction.
 *
 * Props:
 *   value    – probability 0-1
 *   size     – overall SVG dimensions (default 180)
 */
export default function SimulationGauge({ value, size = 180 }) {
  const pct = Math.min(1, Math.max(0, value ?? 0))
  const display = Math.round(pct * 100)

  // Color mapping
  let color
  if (pct >= 0.7) color = '#22C55E'       // green
  else if (pct >= 0.5) color = '#F59E0B'   // amber
  else color = '#EF4444'                     // red

  // Arc geometry
  const cx = size / 2
  const cy = size / 2 + 10
  const r = size / 2 - 20

  // Semicircle: 180° sweep from left (-x) to right (+x)
  // Start point (left end of arc)
  const startX = cx - r
  const startY = cy
  // End point (right end of arc)
  const endX = cx + r
  const endY = cy

  // Track arc path (full semicircle)
  const trackPath = `M ${startX} ${startY} A ${r} ${r} 0 0 1 ${endX} ${endY}`

  // Fill arc — compute end point at pct of 180°
  // Angle from center: π * (1 - pct) measured from +x axis going CCW
  // At pct=0 → angle=π (left point), at pct=1 → angle=0 (right point)
  const angle = Math.PI * (1 - pct)
  const fillEndX = cx + r * Math.cos(angle)
  const fillEndY = cy - r * Math.sin(angle)

  // large-arc-flag: sweep > 180° → 1, else 0
  const largeArc = pct > 0.5 ? 1 : 0

  const fillPath = `M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${fillEndX} ${fillEndY}`

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size - 10} viewBox={`0 0 ${size} ${size - 10}`}>
        {/* Track arc */}
        <path
          d={trackPath}
          fill="none"
          className="text-gray-200 dark:text-[#374151]"
          strokeWidth={12}
          strokeLinecap="round"
        />
        {/* Fill arc */}
        {pct > 0.001 && (
          <path
            d={fillPath}
            fill="none"
            stroke={color}
            strokeWidth={12}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        )}
        {/* Center text */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-gray-900 dark:fill-gray-100"
          fontSize={36}
          fontWeight={700}
          fontFamily="Inter, system-ui, sans-serif"
        >
          {display}%
        </text>
        <text
          x={cx}
          y={cy + 18}
          textAnchor="middle"
          className="fill-gray-400 dark:fill-gray-500"
          fontSize={11}
          fontFamily="Inter, system-ui, sans-serif"
        >
          Win Probability
        </text>
      </svg>
    </div>
  )
}
