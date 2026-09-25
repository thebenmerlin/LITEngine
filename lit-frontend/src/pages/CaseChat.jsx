import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown, MessageCircle, LoaderCircle, Paperclip, Plus, SendHorizontal } from 'lucide-react'
import { EmptyPanel, ErrorNotice, PageHeading } from '../components/workspace/Primitives'
import { SAMPLE_CASES } from '../data/sampleCases'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { askCaseChat, uploadCaseFile } from '../lib/api'

const ACCEPTED_EXTENSIONS = '.txt,.docx,.pdf'

function ChatBubble({ message }) {
  const isUser = message.role === 'user'
  return <div className={`chat-bubble ${isUser ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>
    <span className="chat-bubble-role">{isUser ? 'You' : 'Case assistant'}</span>
    <p>{message.content}</p>
    {message.sources?.length > 0 && <details className="chat-sources">
      <summary>{message.sources.length} source excerpt{message.sources.length > 1 ? 's' : ''} {message.method === 'extractive' && '(model unavailable — showing raw excerpt)'}</summary>
      <ol className="chat-sources-list">
        {message.sources.map((source) => <li key={source.index}><span className="chat-source-tag">S{source.index}</span><p>{source.text}</p></li>)}
      </ol>
    </details>}
  </div>
}

function CaseNameSelect() {
  const { caseText, setCaseText, setAppellantType, setFilingDate, setChatMessages } = useWorkspace()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const matched = SAMPLE_CASES.find((sample) => sample.text === caseText)
  const currentLabel = matched ? matched.label : caseText.trim() ? 'Custom case' : 'Select a case'

  function pick(sample) {
    setCaseText(sample.text)
    setAppellantType(sample.appellantType)
    setFilingDate(sample.filingDate)
    setChatMessages([])
    setOpen(false)
  }

  return <div className="sample-menu case-name-select" ref={rootRef}>
    <button type="button" className="case-name-trigger" onClick={() => setOpen((value) => !value)} aria-haspopup="menu" aria-expanded={open}>
      <span>{currentLabel}</span> <ChevronDown size={14} />
    </button>
    {open && <ul className="sample-menu-list" role="menu">
      {SAMPLE_CASES.map((sample) => (
        <li key={sample.id} role="none">
          <button type="button" role="menuitem" onClick={() => pick(sample)}>{sample.label}</button>
        </li>
      ))}
    </ul>}
  </div>
}

function UploadCaseButton({ compact = false }) {
  const { setCaseText, setChatMessages } = useWorkspace()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(null)
  const inputId = useId()

  async function onFileChosen(event) {
    const file = event.target.files?.[0]
    event.target.value = '' // allow re-selecting the same file later
    if (!file) return
    setError(null)
    setUploading(true)
    try {
      const result = await uploadCaseFile(file)
      setCaseText(result.text)
      setChatMessages([]) // a newly uploaded case starts a fresh conversation
      setLoaded({ filename: result.filename, wordCount: result.word_count })
    } catch (err) {
      setError(err)
    } finally {
      setUploading(false)
    }
  }

  return <div className="upload-case">
    <input type="file" accept={ACCEPTED_EXTENSIONS} onChange={onFileChosen} disabled={uploading} className="sr-only" id={inputId} />
    <label htmlFor={inputId} className={`upload-case-trigger ${compact ? 'compact' : ''} ${uploading ? 'disabled' : ''}`}>
      {uploading ? <LoaderCircle size={compact ? 16 : 15} className="spin" /> : compact ? <Plus size={16} /> : <><Paperclip size={15} /> Upload case file</>}
    </label>
    {loaded && !uploading && <span className="upload-case-status muted">Loaded {loaded.filename} ({loaded.wordCount.toLocaleString()} words)</span>}
    <ErrorNotice message={error?.detail || error?.message} title="Couldn't read this file" />
  </div>
}

export default function CaseChat() {
  const { caseText, chatMessages: messages, setChatMessages: setMessages } = useWorkspace()
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const threadRef = useRef(null)

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  async function send() {
    const question = draft.trim()
    if (!question || sending || !caseText.trim()) return
    setError(null)
    setDraft('')
    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((current) => [...current, { role: 'user', content: question }])
    setSending(true)
    try {
      const response = await askCaseChat({ caseText, question, history })
      setMessages((current) => [...current, { role: 'assistant', content: response.answer, sources: response.sources, method: response.method }])
    } catch (err) {
      setError(err)
    } finally {
      setSending(false)
    }
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  return <div className="page-stack">
    <PageHeading eyebrow="CASE MATERIAL" title="Ask the case" description="Ask follow-up questions about the loaded case. Answers are grounded only in this case's own text, with source excerpts you can check." />
    <div className="case-chat-controls">
      <CaseNameSelect />
      <UploadCaseButton />
    </div>

    {!caseText.trim() && <EmptyPanel icon={MessageCircle} title="Load a case to start asking questions" body="Pick a sample case or upload a .txt, .docx or .pdf, then ask anything about its facts, reasoning or outcome." />}

    {caseText.trim() && <div className="panel chat-panel">
      <div className="chat-thread" ref={threadRef}>
        {messages.length === 0 && !sending && <p className="muted chat-empty-hint">Ask something like "What was the appellant convicted of?" or "Why did the court dismiss the appeal?"</p>}
        {messages.map((message, index) => <ChatBubble key={index} message={message} />)}
        {sending && <div className="chat-bubble chat-bubble-assistant chat-bubble-pending"><span className="chat-bubble-role">Case assistant</span><span className="loading-line"><LoaderCircle size={14} className="spin" /> Reading the case…</span></div>}
      </div>
      <ErrorNotice message={error?.detail || error?.message} title="Couldn't get an answer" />
      <div className="chat-input-row">
        <UploadCaseButton compact />
        <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={onKeyDown}
          placeholder="Ask a question about this case…" disabled={sending} rows={2} />
        <button className="button button-primary" onClick={send} disabled={sending || !draft.trim()}>
          {sending ? <LoaderCircle size={16} className="spin" /> : <SendHorizontal size={16} />}
        </button>
      </div>
    </div>}
  </div>
}
