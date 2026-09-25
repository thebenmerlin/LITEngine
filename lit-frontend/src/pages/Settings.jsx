import { useState } from 'react'
import { Check, RotateCcw } from 'lucide-react'
import { PageHeading } from '../components/workspace/Primitives'
import { useSettings } from '../hooks/useSettings.jsx'
import { useTheme } from '../hooks/useTheme'
import { checkHealth } from '../lib/api'

export default function Settings() {
  const { settings, updateSetting, resetSettings } = useSettings()
  const { dark, toggle } = useTheme()
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)

  const testConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      await checkHealth()
      setTestResult({ ok: true, text: 'Backend connected' })
    } catch (error) {
      setTestResult({ ok: false, text: error.message || 'Connection failed' })
    } finally {
      setTesting(false)
    }
  }

  return <div className="page-stack">
    <PageHeading eyebrow="WORKSPACE / PREFERENCES" title="Settings" description="Set the research defaults for this browser. Changes apply to new analyses." />
    <div className="settings-layout">
      <section className="panel settings-panel"><div className="settings-panel-head"><span className="eyebrow">01 / APPEARANCE</span><h2>Reading environment</h2></div><div className="setting-row"><div><strong>Dark appearance</strong><p>Choose the canvas that works best for long research sessions.</p></div><button className={`switch ${dark ? 'on' : ''}`} onClick={toggle} role="switch" aria-checked={dark} aria-label="Dark appearance"><span /></button></div></section>
      <section className="panel settings-panel"><div className="settings-panel-head"><span className="eyebrow">02 / RESEARCH DEFAULTS</span><h2>Search and extraction</h2></div><div className="setting-row"><div><strong>Use InLegalBERT when available</strong><p>The backend may fall back to rule-based extraction.</p></div><button className={`switch ${settings.useAiModel ? 'on' : ''}`} onClick={() => updateSetting('useAiModel', !settings.useAiModel)} role="switch" aria-checked={settings.useAiModel} aria-label="Use InLegalBERT"><span /></button></div><div className="setting-row"><div><strong>Include live Kanoon results</strong><p>Supplement the local index with live judgments.</p></div><button className={`switch ${settings.includeKanoon ? 'on' : ''}`} onClick={() => updateSetting('includeKanoon', !settings.includeKanoon)} role="switch" aria-checked={settings.includeKanoon} aria-label="Include live Kanoon results"><span /></button></div><div className="setting-row"><div><strong>Default result count</strong><p>Number of precedents requested during a case analysis.</p></div><select value={settings.defaultResultCount} onChange={(event) => updateSetting('defaultResultCount', Number(event.target.value))}><option value={3}>3 results</option><option value={5}>5 results</option><option value={10}>10 results</option></select></div></section>
      <section className="panel settings-panel"><div className="settings-panel-head"><span className="eyebrow">03 / CONNECTION</span><h2>Backend endpoint</h2></div><label className="settings-field"><strong>API base URL</strong><span>Leave blank to use the environment default. Include /api/v1 for a custom endpoint.</span><input type="url" value={settings.apiBaseUrl} onChange={(event) => { updateSetting('apiBaseUrl', event.target.value); setTestResult(null) }} placeholder="http://localhost:8000/api/v1" /></label><div className="settings-actions"><button className="button button-outline" onClick={testConnection} disabled={testing}>{testing ? 'Testing…' : 'Test connection'}</button>{testResult && <span className={testResult.ok ? 'settings-success' : 'settings-failure'}>{testResult.ok && <Check size={15} />}{testResult.text}</span>}</div></section>
      <button className="text-button settings-reset" onClick={() => { resetSettings(); setTestResult(null) }}><RotateCcw size={15} /> Reset research defaults</button>
    </div>
  </div>
}
