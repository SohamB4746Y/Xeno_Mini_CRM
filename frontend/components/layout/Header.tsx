type HeaderProps = {
  title: string
}

export function Header({ title }: HeaderProps) {
  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-bg/95 px-8">
      <div>
        <h1 className="text-xl font-semibold text-neutral-100">{title}</h1>
      </div>
      <div className="flex items-center gap-5 text-sm">
        <div className="text-neutral-300">ZURI Fashion</div>
        <div className="flex items-center gap-2 rounded-full border border-green-500/25 bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-green-400" />
          AI Active
        </div>
      </div>
    </header>
  )
}
