/* -------------------------------------------------------------------------- */
/*  LIT API Client — fetch-based, zero extra dependencies                     */
/* -------------------------------------------------------------------------- */

const DEFAULT_BASE_URL =
  (import.meta.env && import.meta.env.VITE_PUBLIC_API_BASE_URL) ||
  (import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  'http://localhost:8000/api/v1'

function baseUrl() {
  try {
    const configured = JSON.parse(localStorage.getItem('lit-settings') || '{}').apiBaseUrl?.trim()
    return configured ? configured.replace(/\/$/, '') : DEFAULT_BASE_URL
  } catch {
    return DEFAULT_BASE_URL
  }
}

const DEFAULT_TIMEOUT_MS = 30_000

/* --------------------------------------------------------------------------- */
/*  ApiError                                                                    */
/* --------------------------------------------------------------------------- */

export class ApiError extends Error {
  /**
   * @param {string} message   – Human-readable summary
   * @param {number} status    – HTTP status code
   * @param {string} [detail]  – Server-provided detail string
   * @param {unknown} [body]   – Full parsed error body (for inspection)
   */
  constructor(message, status, detail, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail ?? ''
    this.body = body
  }
}

/* --------------------------------------------------------------------------- */
/*  Core request helper                                                        */
/* --------------------------------------------------------------------------- */

/**
 * Send a JSON request with automatic error parsing and a 30 s timeout.
 *
 * @param {string}  path        – e.g. "/precedent/search" (relative to BASE_URL)
 * @param {object}  options     – fetch options (method, body, …)
 * @returns {Promise<unknown>}  – Parsed JSON response
 */
export async function request(path, options = {}) {
  const url = path.startsWith('http') ? path : `${baseUrl()}${path}`

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)

  const defaults = {
    // A JSON header on GET requests forces an unnecessary CORS preflight.
    headers: options.body === undefined ? {} : { 'Content-Type': 'application/json' },
    signal: controller.signal,
  }

  const config = { ...defaults, ...options }

  let response
  try {
    response = await fetch(url, config)
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError('Request timed out (30 s)', 0, 'timeout')
    }
    throw new ApiError(err.message ?? 'Network error', 0, err.message)
  } finally {
    clearTimeout(timeoutId)
  }

  // ---------- error responses ----------
  if (!response.ok) {
    let parsed = {}
    try {
      parsed = await response.json()
    } catch {
      // body not JSON — ignore
    }

    const detail =
      parsed.detail ?? parsed.message ?? parsed.error ?? response.statusText

    throw new ApiError(
      detail || `Request failed with status ${response.status}`,
      response.status,
      detail,
      parsed,
    )
  }

  // ---------- success ----------
  // 204 No Content
  if (response.status === 204) return null

  return response.json()
}

/* --------------------------------------------------------------------------- */
/*  Precedent Search                                                            */
/* --------------------------------------------------------------------------- */

/**
 * Semantic search across precedents (FAISS) with optional Kanoon fallback.
 *
 * @param {{ query: string, topK?: number, useKanoon?: boolean, beforeDate?: string }} params
 * @returns {Promise<object>}  PrecedentSearchResponse
 */
export async function searchPrecedents({ query, topK = 5, useKanoon = true, beforeDate = null }) {
  return request('/precedent/search', {
    method: 'POST',
    body: JSON.stringify({ query, top_k: topK, use_kanoon: useKanoon, before_date: beforeDate }),
  })
}

/**
 * Fetch FAISS index statistics.
 *
 * @returns {Promise<{ total_documents: number, index_size_bytes: number }>}
 */
export async function getIndexStats() {
  return request('/precedent/index/stats')
}

/* --------------------------------------------------------------------------- */
/*  Fact Extraction                                                             */
/* --------------------------------------------------------------------------- */

/**
 * Extract a StructuredCaseProfile from raw case text.
 *
 * May return a 202 Accepted with `{ task_id }` when the model is warming up.
 *
 * @param {{ caseText: string, useModel?: boolean }} params
 * @returns {Promise<object>}  StructuredCaseProfile  |  { task_id: string, … }
 */
export async function extractFacts({ caseText, useModel = true }) {
  return request('/facts/extract', {
    method: 'POST',
    body: JSON.stringify({ case_text: caseText, use_model: useModel }),
  })
}

/**
 * Poll an async extraction task.
 *
 * @param {string} taskId
 * @returns {Promise<{ status: string, result?: object, error?: string }>}
 */
export async function checkTaskStatus(taskId) {
  return request(`/facts/status/${taskId}`)
}

/* --------------------------------------------------------------------------- */
/*  Graph                                                                       */
/* --------------------------------------------------------------------------- */

/**
 * Build an argument graph from a StructuredCaseProfile.
 *
 * @param {{ caseProfile: object, precedents?: object[] }} params
 * @returns {Promise<{ nodes: object[], edges: object[], weak_nodes: string[], node_count: number, edge_count: number }>}
 */
export async function buildGraph({ caseProfile, precedents = [] }) {
  return request('/graph/build', {
    method: 'POST',
    body: JSON.stringify({ case_profile: caseProfile, precedents }),
  })
}

/* --------------------------------------------------------------------------- */
/*  Simulation                                                                  */
/* --------------------------------------------------------------------------- */

/**
 * Predict a judicial outcome from a StructuredCaseProfile.
 *
 * @param {{ caseProfile: object, precedents?: object[], graphStats?: object | null, appellantType: string, filingDate: string }} params
 * @returns {Promise<{ result: object, processing_time_ms: number, timestamp: string }>}
 */
export async function runSimulation({ caseProfile, precedents = [], graphStats = null, appellantType, filingDate }) {
  return request('/simulation/predict', {
    method: 'POST',
    body: JSON.stringify({
      case_profile: caseProfile,
      precedents,
      graph_stats: graphStats,
      appellant_type: appellantType,
      filing_date: filingDate,
    }),
  })
}

/* --------------------------------------------------------------------------- */
/*  Health                                                                      */
/* --------------------------------------------------------------------------- */

/**
 * Root-level health check on the backend.
 * Strips the /api/v1 suffix so we hit the FastAPI root.
 *
 * @returns {Promise<{ app: string, version: string, status: string }>}
 */
export async function checkHealth() {
  const rootUrl = baseUrl().replace(/\/api\/v1$/, '')
  return request(`${rootUrl}/health`)
}
