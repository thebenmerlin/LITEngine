import { Link } from 'react-router-dom'
import {
  Search,
  FileSearch,
  GitBranch,
  Brain,
  ArrowRight,
} from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'

const FEATURES = [
  {
    to: '/precedent-search',
    icon: Search,
    title: 'Precedent Search',
    description:
      'Semantic search across Indian case law with FAISS-powered vector similarity and Kanoon fallback.',
  },
  {
    to: '/fact-extraction',
    icon: FileSearch,
    title: 'Fact Extraction',
    description:
      'Automatically extract parties, sections, acts, and key facts from raw judgment text.',
  },
  {
    to: '/argument-graph',
    icon: GitBranch,
    title: 'Argument Graph',
    description:
      'Visualize relationships between cases, statutes, and legal arguments as an interactive graph.',
  },
  {
    to: '/simulation',
    icon: Brain,
    title: 'Judicial Simulation',
    description:
      'Simulate case outcomes, find matching precedents, and generate counter-arguments.',
  },
]

export default function Home() {
  return (
    <div>
      {/* Welcome section */}
      <div className="mb-10">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Legal Intelligence Terminal
        </h2>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          AI-powered legal research for Indian courts
        </p>
      </div>

      {/* Feature cards — 2x2 grid */}
      <div className="grid gap-5 sm:grid-cols-2">
        {FEATURES.map(({ to, icon: Icon, title, description }) => (
          <Card key={to} hoverable className="flex flex-col justify-between">
            <div>
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-navy-700/5 dark:bg-navy-700/20">
                <Icon className="h-5 w-5 text-navy-700 dark:text-navy-300" />
              </div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                {title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-gray-500 dark:text-gray-400">
                {description}
              </p>
            </div>

            <div className="mt-6">
              <Link to={to}>
                <Button variant="outline" size="sm" className="gap-2">
                  Open
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
