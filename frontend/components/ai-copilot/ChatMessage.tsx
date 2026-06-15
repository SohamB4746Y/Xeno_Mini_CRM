import clsx from 'clsx'
import type { ChatMessage as ChatMessageType } from '@/lib/types'

function renderAIText(text: string) {
  return text.split('\n').map((line, index) => {
    if (line.trim().startsWith('─') || line.trim() === '---') {
      return <hr key={index} className="my-3 border-border" />
    }

    const parts = line.split(/(\*\*[^*]+\*\*)/g)
    return (
      <p key={index} className="mb-1 whitespace-pre-wrap leading-relaxed">
        {parts.map((part, partIndex) =>
          part.startsWith('**') && part.endsWith('**') ? (
            <strong key={partIndex} className="font-semibold text-neutral-50">
              {part.slice(2, -2)}
            </strong>
          ) : (
            <span
              key={partIndex}
              className={partIndex === 0 && /^[^\w\s]/.test(part) ? 'text-base' : undefined}
            >
              {part}
            </span>
          ),
        )}
      </p>
    )
  })
}

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[86%] rounded-xl px-3 py-2 text-sm',
          isUser
            ? 'bg-primary text-white'
            : 'border border-border bg-surface text-neutral-200',
        )}
      >
        {isUser ? <p>{message.content}</p> : renderAIText(message.content)}
      </div>
    </div>
  )
}
