/* -------------------------------------------------------------------------- */
/*  What-If Calculator — pure client-side heuristic recalculation             */
/* -------------------------------------------------------------------------- */

const PROB_MIN = 0.05
const PROB_MAX = 0.95

// Default tweaks (used for diffing)
export const DEFAULT_TWEAKS = {
  additionalEvidence: 0,
  evidenceQuality: 'moderate',   // 'weak' | 'moderate' | 'strong'
  additionalIpcSections: 0,
  jurisdiction: 'same',          // 'same' | 'high' | 'supreme' | 'district'
  resolvedWeakArgs: [],          // array of node ids
  additionalPrecedents: 0,
  precedentSimilarity: 'medium', // 'low' | 'medium' | 'high'
}

/**
 * Recalculate win_probability from a base result + user tweaks.
 *
 * @param {number} baseProb – The original win_probability (0–1)
 * @param {object} tweaks   – Current tweak values
 * @returns {{ adjusted: number, delta: number, changelog: string[] }}
 */
export function recalculate(baseProb, tweaks) {
  let delta = 0
  const changelog = []

  // --- Evidence ---
  const evCount = tweaks.additionalEvidence ?? 0
  if (evCount > 0) {
    delta += evCount * 0.03
    changelog.push(`✓ Added ${evCount} evidence piece${evCount > 1 ? 's' : ''} (+${(evCount * 3)}%)`)
  }

  const quality = tweaks.evidenceQuality ?? 'moderate'
  const qualityDelta = { weak: -0.05, moderate: 0, strong: 0.05 }[quality] ?? 0
  if (qualityDelta !== 0) {
    delta += qualityDelta
    const label = { weak: 'Weak', strong: 'Strong' }[quality]
    changelog.push(`${qualityDelta > 0 ? '✓' : '✗'} Evidence quality: ${label} (${qualityDelta > 0 ? '+' : ''}${Math.round(qualityDelta * 100)}%)`)
  }

  // --- Statutes ---
  const ipcCount = tweaks.additionalIpcSections ?? 0
  if (ipcCount > 0) {
    delta += ipcCount * 0.02
    changelog.push(`✓ Added ${ipcCount} IPC section${ipcCount > 1 ? 's' : ''} (+${(ipcCount * 2)}%)`)
  }

  // --- Jurisdiction ---
  const jurDelta = {
    same: 0,
    high: 0.03,
    supreme: -0.08,
    district: 0.08,
  }[tweaks.jurisdiction] ?? 0
  if (jurDelta !== 0) {
    delta += jurDelta
    const jurLabel = { high: 'High Court', supreme: 'Supreme Court', district: 'District Court' }[tweaks.jurisdiction]
    changelog.push(`${jurDelta > 0 ? '✓' : '✗'} Moved to ${jurLabel} (${jurDelta > 0 ? '+' : ''}${Math.round(jurDelta * 100)}%)`)
  }

  // --- Weak arguments resolved ---
  const resolvedCount = (tweaks.resolvedWeakArgs ?? []).length
  if (resolvedCount > 0) {
    delta += resolvedCount * 0.04
    changelog.push(`✓ Resolved ${resolvedCount} weak argument${resolvedCount > 1 ? 's' : ''} (+${(resolvedCount * 4)}%)`)
  }

  // --- Precedents ---
  const precCount = tweaks.additionalPrecedents ?? 0
  const precDelta = { low: 0.01, medium: 0.025, high: 0.045 }[tweaks.precedentSimilarity] ?? 0
  if (precCount > 0) {
    const precTotal = precCount * precDelta
    delta += precTotal
    const simLabel = { low: 'Low', medium: 'Medium', high: 'High' }[tweaks.precedentSimilarity]
    changelog.push(`✓ Added ${precCount} precedent${precCount > 1 ? 's' : ''} (${simLabel} similarity, +${Math.round(precTotal * 100)}%)`)
  }

  // Clamp
  const adjusted = Math.max(PROB_MIN, Math.min(PROB_MAX, baseProb + delta))

  return {
    adjusted: Math.round(adjusted * 10000) / 10000,
    delta: Math.round(delta * 10000) / 10000,
    changelog,
  }
}

/**
 * Map probability to risk level.
 */
export function riskLevel(prob) {
  if (prob >= 0.7) return { level: 'Favorable', color: 'green' }
  if (prob >= 0.5) return { level: 'Uncertain', color: 'amber' }
  return { level: 'Unfavorable', color: 'red' }
}
