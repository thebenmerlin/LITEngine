import { FileQuestion } from 'lucide-react'

export default function EmptyState({ title, message, icon: Icon, action }) {
  const IconComponent = Icon || FileQuestion

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 rounded-full bg-gray-100 p-4 dark:bg-gray-800">
        <IconComponent className="h-8 w-8 text-gray-400 dark:text-gray-500" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
        {title}
      </h3>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {message}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
