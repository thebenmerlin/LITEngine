export default function Card({ children, className = '', hoverable = false, ...props }) {
  return (
    <div
      className={`rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-all duration-200 dark:border-gray-800 dark:bg-surface-dark ${
        hoverable
          ? 'hover:-translate-y-0.5 hover:border-navy-700/30 hover:shadow-md dark:hover:border-navy-700/50'
          : ''
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
