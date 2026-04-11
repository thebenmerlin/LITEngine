import { useEffect, useRef } from 'react'

export default function LoadingScreen({ onDone }) {
  const barRef = useRef(null)

  useEffect(() => {
    // Simulate a short load window — the real health check
    // in App.jsx will call onDone() as soon as it completes.
    // This component just provides a visual placeholder.
    const t = setTimeout(() => {
      if (barRef.current) {
        barRef.current.style.transform = 'translateX(0)'
        barRef.current.style.opacity = '1'
      }
    }, 100)
    return () => clearTimeout(t)
  }, [])

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-white transition-opacity duration-300"
      style={{ opacity: 1 }}
    >
      {/* LIT wordmark */}
      <div className="mb-1 text-3xl font-bold tracking-tight text-navy-700">
        LIT
      </div>
      <div className="text-xs tracking-wide text-gray-400">
        Legal Intelligence Terminal
      </div>

      {/* Animated progress bar at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-[2px] overflow-hidden bg-gray-100">
        <div
          ref={barRef}
          className="h-full w-2/5 origin-left bg-navy-700 transition-transform duration-[1500ms] ease-out"
          style={{ transform: 'translateX(-100%)', opacity: 0 }}
        />
      </div>
    </div>
  )
}