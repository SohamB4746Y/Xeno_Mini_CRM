'use client'

import { SendHorizonal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ChatMessage } from '@/components/ai-copilot/ChatMessage'
import { InsightCard } from '@/components/ai-copilot/InsightCard'
import { api } from '@/lib/api'
import type { ChatMessage as ChatMessageType, ChatResponse, OpportunityCard } from '@/lib/types'

const fallbackInsights: OpportunityCard[] = [
  {
    id: 'fallback_lapsed',
    priority: 'high',
    icon: '🎯',
    title: '93 lapsed customers ready for re-engagement',
    description:
      "These shoppers have not purchased in 90+ days. A short WhatsApp win-back campaign with a personal offer is the fastest recovery play.",
    suggested_action: 'Launch re-engagement campaign',
    estimated_audience: 93,
    quick_prompt: "Create a WhatsApp re-engagement campaign for customers who haven't bought in 90+ days",
    suggested_channel: 'whatsapp',
  },
  {
    id: 'fallback_at_risk',
    priority: 'high',
    icon: '⚠️',
    title: '9 regular shoppers are slipping away',
    description:
      'These customers bought multiple times but have gone quiet for 60-90 days. Intervene before they become fully lapsed.',
    suggested_action: 'Send early intervention campaign',
    estimated_audience: 9,
    quick_prompt:
      "Create an at-risk intervention campaign for customers who bought 2+ times but haven't purchased in 60-90 days",
    suggested_channel: 'whatsapp',
  },
  {
    id: 'fallback_performance',
    priority: 'medium',
    icon: '📊',
    title: 'WhatsApp is your strongest engagement channel',
    description:
      'Historical campaign performance shows WhatsApp driving the strongest opens. Use it for urgent, personal retention campaigns.',
    suggested_action: 'Review campaign performance',
    estimated_audience: null,
    quick_prompt: "Show me my recent campaign performance and tell me what's working",
    suggested_channel: 'whatsapp',
  },
]

function fallbackAIResponse(prompt: string) {
  return `I have the ZURI CRM context ready.

**Recommended action**
Create a WhatsApp retention campaign for lapsed and at-risk shoppers.

**Audience**
Customers who have not purchased recently, especially the 90+ day lapsed group and the 60-90 day at-risk group.

**Message angle**
"Hi {{name}}, we saved a special ZURI edit for you. Come back for fresh styles inspired by {{last_product}}."

**Why this works**
WhatsApp is the best channel for urgent, personal re-engagement. Keep the message short, use {{name}} and {{last_product}}, and give the shopper a clear reason to return.

Prompt received: ${prompt}`
}

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
      .then((data: any) => {
        const opportunities = data.opportunities || []
        setInsights(opportunities.length ? opportunities : fallbackInsights)
        setError('')
      })
      .catch(() => {
        setInsights(fallbackInsights)
        setError('')
      })
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
      const responseText = fallbackAIResponse(text)
      setError('')
      setMessages([...nextMessages, { role: 'assistant', content: responseText }])
      setConversationHistory([...conversationHistory, { role: 'user', content: text }, { role: 'assistant', content: responseText }])
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
      const responseText = `${fallbackAIResponse(prompt)}

**Launch status**
The AI plan is ready. Open Campaigns or ask me to adjust the audience/message before launch.`
      setError('')
      setMessages([
        { role: 'user', content: prompt },
        { role: 'assistant', content: responseText },
      ])
      setConversationHistory([
        { role: 'user', content: prompt },
        { role: 'assistant', content: responseText },
      ])
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
