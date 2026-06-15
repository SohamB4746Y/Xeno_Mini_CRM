'use client'

import { SendHorizonal, RotateCcw, Sparkles, Wrench, CheckCircle2, XCircle, Rocket } from 'lucide-react'
import { useEffect, useRef, useState, useCallback } from 'react'
import { ChatMessage } from '@/components/ai-copilot/ChatMessage'
import { InsightCard } from '@/components/ai-copilot/InsightCard'
import { api } from '@/lib/api'
import type { ActionTaken, ChatMessage as ChatMessageType, ChatResponse, OpportunityCard } from '@/lib/types'

interface EnrichedMessage extends ChatMessageType {
  tools_used?: string[]
  actions_taken?: ActionTaken[]
}

const TOOL_LABELS: Record<string, string> = {
  get_dashboard_summary: 'Dashboard Overview',
  query_customers: 'Customer Query',
  query_orders: 'Order Analysis',
  query_customer_orders: 'Customer Orders',
  get_segment_list: 'Segments List',
  get_segment_detail: 'Segment Detail',
  get_campaign_list: 'Campaigns List',
  get_campaign_detail: 'Campaign Detail',
  create_segment: 'Created Segment',
  create_campaign: 'Created Campaign',
  launch_campaign: 'Launched Campaign',
  get_proactive_opportunities: 'Opportunity Scan',
  preview_segment: 'Segment Preview',
  get_customer_insights: 'Customer Insights',
  get_segment_insights: 'Segment Insights',
  get_campaign_performance: 'Campaign Performance',
  generate_executive_report: 'Executive Report',
}

function ToolBadge({ tool }: { tool: string }) {
  const label = TOOL_LABELS[tool] || tool.replace(/_/g, ' ')
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium text-indigo-300">
      <Wrench className="h-2.5 w-2.5" />
      {label}
    </span>
  )
}

function ActionCard({ action }: { action: ActionTaken }) {
  if (action.type === 'campaign_created' || action.type === 'create_campaign') {
    return (
      <div className="rounded-lg border border-green-500/30 bg-green-500/5 p-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-400" />
          <span className="text-xs font-semibold text-green-300">Campaign Created</span>
        </div>
        {action.campaign_name && <p className="mt-1 text-sm text-neutral-200">{action.campaign_name}</p>}
        {action.total_recipients != null && (
          <p className="mt-1 text-xs text-neutral-400">{action.total_recipients} recipients</p>
        )}
        {action.campaign_id && (
          <a
            href={`/campaigns/${action.campaign_id}`}
            className="mt-2 inline-block text-xs text-primary hover:underline"
          >
            View Campaign →
          </a>
        )}
      </div>
    )
  }

  if (action.type === 'segment_created' || action.type === 'create_segment') {
    return (
      <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-3">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-purple-400" />
          <span className="text-xs font-semibold text-purple-300">Segment Created</span>
        </div>
        {action.segment_name && <p className="mt-1 text-sm text-neutral-200">{action.segment_name}</p>}
        {action.customer_count != null && (
          <p className="mt-1 text-xs text-neutral-400">{action.customer_count} customers matched</p>
        )}
      </div>
    )
  }

  if (action.type === 'campaign_launched' || action.type === 'launch_campaign') {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
        <div className="flex items-center gap-2">
          <Rocket className="h-4 w-4 text-amber-400" />
          <span className="text-xs font-semibold text-amber-300">Campaign Launched</span>
        </div>
        {action.campaign_name && <p className="mt-1 text-sm text-neutral-200">{action.campaign_name}</p>}
      </div>
    )
  }

  return null
}

export function CopilotPanel() {
  const [messages, setMessages] = useState<EnrichedMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [insights, setInsights] = useState<OpportunityCard[]>([])
  const [insightsLoading, setInsightsLoading] = useState(true)
  const [conversationHistory, setConversationHistory] = useState<ChatMessageType[]>([])
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setInsightsLoading(true)
    api.ai
      .getInsights()
      .then((data: any) => {
        setInsights(data.opportunities || [])
      })
      .catch((err) => setError(err.message || 'Could not load AI insights'))
      .finally(() => setInsightsLoading(false))
  }, [])

  const handleExternalPrompt = useCallback((event: Event) => {
    const prompt = (event as CustomEvent<string>).detail
    if (prompt) sendMessage(prompt)
  }, [])

  useEffect(() => {
    window.addEventListener('zuri-ai-prompt', handleExternalPrompt)
    return () => window.removeEventListener('zuri-ai-prompt', handleExternalPrompt)
  }, [handleExternalPrompt])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(prompt?: string) {
    const text = (prompt || input).trim()
    if (!text || loading) return

    const userMsg: EnrichedMessage = { role: 'user', content: text }
    const nextMessages: EnrichedMessage[] = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError('')

    try {
      const response = (await api.ai.chat(text, conversationHistory)) as ChatResponse
      const assistantMsg: EnrichedMessage = {
        role: 'assistant',
        content: response.response,
        tools_used: response.tools_used || [],
        actions_taken: response.actions_taken || [],
      }
      setMessages([...nextMessages, assistantMsg])
      setConversationHistory(
        (response.conversation_history || [...conversationHistory, { role: 'user', content: text }, { role: 'assistant', content: response.response }])
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role, content: String(m.content || '') })),
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'AI request failed'
      setError(message)
      setMessages([
        ...nextMessages,
        { role: 'assistant', content: `I hit a snag: ${message}` },
      ])
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
      const assistantMsg: EnrichedMessage = {
        role: 'assistant',
        content: response.response,
        tools_used: response.tools_used || [],
        actions_taken: response.actions_taken || [],
      }
      setMessages([{ role: 'user', content: prompt }, assistantMsg])
      setConversationHistory(
        (response.conversation_history || [])
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role, content: String(m.content || '') })),
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Quick launch failed'
      setError(message)
      setMessages([{ role: 'assistant', content: `Quick launch failed: ${message}` }])
    } finally {
      setLoading(false)
    }
  }

  function resetConversation() {
    setMessages([])
    setConversationHistory([])
    setError('')
  }

  const showInsights = messages.length === 0

  return (
    <aside className="flex h-screen w-[380px] shrink-0 flex-col border-l border-border bg-[#111]">
      <div className="border-b border-border px-5 py-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-neutral-100">
              <Sparkles className="h-5 w-5 text-primary" />
              ZURI AI Copilot
            </h2>
            <p className="mt-1 text-xs text-neutral-500">Marketing Intelligence — AI drives, human approves</p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={resetConversation}
              className="rounded-lg p-2 text-neutral-500 hover:bg-surface hover:text-neutral-300"
              title="New conversation"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
        </div>
        <div className="mt-4 h-px bg-gradient-to-r from-primary via-indigo-400 to-transparent" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {showInsights ? (
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Proactive opportunities
            </div>
            {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">{error}</div>}
            {insightsLoading ? (
              [0, 1, 2].map((item) => (
                <div key={item} className="h-36 animate-pulse rounded-xl border border-border bg-surface" />
              ))
            ) : insights.length > 0 ? (
              insights.map((insight) => (
                <InsightCard
                  key={insight.id}
                  insight={insight}
                  onAsk={sendMessage}
                  onQuickLaunch={quickLaunch}
                  disabled={loading}
                />
              ))
            ) : !error ? (
              <p className="py-6 text-center text-xs text-neutral-500">No opportunities detected right now.</p>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`}>
                <ChatMessage message={message} />
                {message.role === 'assistant' && message.tools_used && message.tools_used.length > 0 && (
                  <div className="ml-1 mt-1.5 flex flex-wrap gap-1">
                    {message.tools_used.map((tool, i) => (
                      <ToolBadge key={`${tool}-${i}`} tool={tool} />
                    ))}
                  </div>
                )}
                {message.role === 'assistant' && message.actions_taken && message.actions_taken.length > 0 && (
                  <div className="ml-1 mt-2 space-y-2">
                    {message.actions_taken.map((action, i) => (
                      <ActionCard key={`action-${i}`} action={action} />
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-3">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:120ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:240ms]" />
                  <span className="ml-2 text-xs text-neutral-500">Analyzing CRM data...</span>
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
            placeholder="Ask ZURI AI anything..."
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
