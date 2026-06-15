'use client'

import { SendHorizonal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ChatMessage } from '@/components/ai-copilot/ChatMessage'
import { InsightCard } from '@/components/ai-copilot/InsightCard'
import { api } from '@/lib/api'
import type { ChatMessage as ChatMessageType, ChatResponse, OpportunityCard } from '@/lib/types'

export function CopilotPanel() {
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [insights, setInsights] = useState<OpportunityCard[]>([])
  const [conversationHistory, setConversationHistory] = useState<ChatMessageType[]>([])
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    api.ai
      .getInsights()
      .then((data: any) => setInsights(data.opportunities || []))
      .catch((err) => setError(err.message || 'Could not load AI insights'))
  }, [])

  useEffect(() => {
    const handler = (event: Event) => {
      const prompt = (event as CustomEvent<string>).detail
      if (prompt) sendMessage(prompt)
    }
    window.addEventListener('zuri-ai-prompt', handler)
    return () => window.removeEventListener('zuri-ai-prompt', handler)
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(prompt?: string) {
    const text = (prompt || input).trim()
    if (!text || loading) return

    const nextMessages: ChatMessageType[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError('')

    try {
      const response = (await api.ai.chat(text, conversationHistory)) as ChatResponse
      setMessages([...nextMessages, { role: 'assistant', content: response.response }])
      setConversationHistory(
        (response.conversation_history || [...conversationHistory, { role: 'user', content: text }, { role: 'assistant', content: response.response }])
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({ role: message.role, content: String(message.content || '') })),
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'AI request failed'
      setError(message)
      setMessages([...nextMessages, { role: 'assistant', content: `I hit a snag: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  async function quickLaunch(prompt: string) {
    if (loading) return
    setLoading(true)
    setError('')
    setMessages([{ role: 'user', content: prompt }])
    try {
      const response = (await api.ai.quickLaunch(prompt)) as ChatResponse
      setMessages([
        { role: 'user', content: prompt },
        { role: 'assistant', content: response.response },
      ])
      setConversationHistory(
        (response.conversation_history || [])
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({ role: message.role, content: String(message.content || '') })),
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Quick launch failed'
      setError(message)
      setMessages([{ role: 'assistant', content: `Quick launch failed: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  const showInsights = messages.length === 0

  return (
    <aside className="flex h-screen w-[380px] shrink-0 flex-col border-l border-border bg-[#111]">
      <div className="border-b border-border px-5 py-5">
        <h2 className="text-lg font-semibold text-neutral-100">ZURI AI Copilot</h2>
        <p className="mt-1 text-xs text-neutral-500">Marketing Intelligence</p>
        <div className="mt-4 h-px bg-gradient-to-r from-primary via-indigo-400 to-transparent" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {showInsights ? (
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Proactive opportunities
            </div>
            {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">{error}</div>}
            {!insights.length && !error
              ? [0, 1, 2].map((item) => (
                  <div key={item} className="h-36 animate-pulse rounded-xl border border-border bg-surface" />
                ))
              : insights.map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    onAsk={sendMessage}
                    onQuickLaunch={quickLaunch}
                    disabled={loading}
                  />
                ))}
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <ChatMessage key={`${message.role}-${index}`} message={message} />
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="flex gap-1 rounded-xl border border-border bg-surface px-3 py-3">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:120ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:240ms]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="border-t border-border p-4">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            sendMessage()
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask ZURI AI..."
            className="h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 text-sm text-neutral-100 outline-none ring-primary/40 placeholder:text-neutral-600 focus:ring-2"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <SendHorizonal className="h-4 w-4" />
          </button>
        </form>
      </div>
    </aside>
  )
}
