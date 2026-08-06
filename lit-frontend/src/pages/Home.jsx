import { Link } from 'react-router-dom'
import {
  Search,
  FileSearch,
  GitBranch,
  Brain,
  FlaskConical,
  ArrowRight,
  Database,
  TrendingUp,
  Network,
  Activity,
} from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useApi } from '../hooks/useApi'
import { getIndexStats, checkHealth } from '../lib/api'

/* ------------------------------------------------------------------ */
/*  Feature registry — five distinct tools, five distinct layouts     */
/* ------------------------------------------------------------------ */

const FEATURES = [
  {
    to: '/precedent-search',
    icon: Search,
    accent: 'from-navy-500 to-navy-700',
    title: 'Precedent Search',
    description:
      'Semantic search across Indian case law — FAISS vector similarity with live Kanoon fallback.',
    tag: 'Search',
  },
  {
    to: '/fact-extraction',
    icon: FileSearch,
    accent: 'from-emerald-500 to-emerald-700',
    title: 'Fact Extraction',
    description:
      'Pull parties, sections, acts, and key facts out of raw judgment or complaint text with InLegalBERT.',
    tag: 'Extract',
  },
  {
    to: '/argument-graph',
    icon: GitBranch,
    accent: 'from-amber-500 to-amber-700',
    title: 'Argument Graph',
    description:
      'Map claims, evidence, statutes, and precedents into an interactive graph — surfaces weak arguments.',
    tag: 'Visualize',
  },
  {
    to: '/simulation',
    icon: Brain,
    accent: 'from-violet-500 to-violet-700',
    title: 'Judicial Simulation',
    description:
      'Predict case outcome with a trained classifier, benchmarked against a rule-based heuristic side by side.',
    tag: 'Predict',
  },
  {
    to: '/what-if',
    icon: FlaskConical,
    accent: 'from-rose-500 to-rose-700',
    title: 'What-If Analyzer',
    description:
      'Tweak evidence, statutes, and precedent strength and watch the predicted outcome shift live.',
    tag: 'Explore',
  },
]

/* ------------------------------------------------------------------ */
/*  Real, verified stats — pulled from actual training/eval reports   */
/*  (data/outcome_dataset/model/training_report_binary.json and       */
/*  data/precedent_reranker/SUMMARY.md), not seed or mock data.       */
/* ------------------------------------------------------------------ */

const RESEARCH_STATS = [
  {
    icon: Database,
    label: 'Training corpus',
    value: '187',
    detail: 'labeled judgments, cleaned from 505 scraped',
  },
  {
    icon: TrendingUp,
    label: 'Outcome model accuracy',
    value: '71.6%',
    detail: '5-fold CV, vs. 60.4% majority-class baseline',
  },
  {
    icon: Network,
    label: 'Precedent reranker research',
    value: '38',
    detail: 'validated SC landmarks · 1,463 citation pairs',
  },
]

/* ------------------------------------------------------------------ */
/*  Live status pill — real backend health check, not a static badge  */
/* ------------------------------------------------------------------ */

function StatusPill() {
  const { data, loading, error } = useApi(checkHealth, { immediate: true })
  const ok = !loading && !error && data?.status === 'healthy'

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 dark:border-gray-800 dark:bg-surface-dark dark:text-gray-300">
      <span className="relative flex h-2 w-2">
        {ok && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
        )}
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${
            loading ? 'bg-gray-300' : ok ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
      </span>
      {loading ? 'Checking backend…' : ok ? 'Backend operational' : 'Backend unreachable'}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Home page                                                          */
/* ------------------------------------------------------------------ */

export default function Home() {
  const { data: statsData } = useApi(getIndexStats, { immediate: true })

  return (
    <div>
      {/* ── Hero ─────────────────────────────────────────────────── */}
      <div className="relative mb-10 overflow-hidden rounded-2xl border border-gray-200 bg-gradient-to-br from-navy-700 via-navy-700 to-navy-800 px-8 py-10 dark:border-gray-800">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
            backgroundSize: '22px 22px',
          }}
        />
        <div className="relative">
          <StatusPill />
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">
            Legal Intelligence Terminal
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-navy-100">
            AI-assisted research for Indian courts — precedent retrieval, fact
            extraction, argument mapping, and outcome simulation, backed by a
            classifier trained and validated on real Indian Kanoon judgments.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/precedent-search">
              <Button
                variant="primary"
                size="md"
                className="gap-2 !bg-none !bg-white !text-navy-800 shadow-sm hover:!bg-navy-50"
              >
                <Search className="h-4 w-4" />
                Start researching
              </Button>
            </Link>
            <Link to="/simulation">
              <Button
                variant="outline"
                size="md"
                className="gap-2 border-white/30 bg-white/5 text-white hover:bg-white/10"
              >
                <Brain className="h-4 w-4" />
                Run a simulation
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* ── Research & validation — real numbers ────────────────── */}
      <div className="mb-10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Research &amp; Validation
          </h3>
          <span className="text-[11px] text-gray-400 dark:text-gray-600">
            From cross-validated training reports, not seed data
          </span>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {RESEARCH_STATS.map(({ icon: Icon, label, value, detail }) => (
            <Card key={label} className="!p-5">
              <div className="flex items-center gap-2 text-gray-400 dark:text-gray-500">
                <Icon className="h-4 w-4" />
                <span className="text-xs font-medium uppercase tracking-wide">
                  {label}
                </span>
              </div>
              <p className="mt-2 text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
                {value}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-gray-500 dark:text-gray-400">
                {detail}
              </p>
            </Card>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400 dark:text-gray-600">
          <Activity className="h-3.5 w-3.5" />
          {statsData ? (
            <span>
              Live index currently holds{' '}
              <span className="font-medium text-gray-600 dark:text-gray-300">
                {statsData.total_documents}
              </span>{' '}
              document{statsData.total_documents === 1 ? '' : 's'} — live Kanoon
              fills the rest at query time.
            </span>
          ) : (
            <span>Fetching live index size…</span>
          )}
        </div>
      </div>

      {/* ── Feature grid ─────────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
          Tools
        </h3>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {FEATURES.map(({ to, icon: Icon, title, description, accent, tag }) => (
          <Card
            key={to}
            hoverable
            className="group flex flex-col justify-between overflow-hidden !p-0"
          >
            <div className={`h-1 w-full bg-gradient-to-r ${accent}`} />
            <div className="flex flex-1 flex-col justify-between p-6">
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${accent} shadow-sm transition-transform duration-200 group-hover:scale-105`}
                  >
                    <Icon className="h-5 w-5 text-white" />
                  </div>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                    {tag}
                  </span>
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
                    <ArrowRight className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5" />
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
