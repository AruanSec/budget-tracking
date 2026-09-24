import { useQuery } from '@tanstack/react-query'

type Health = { status: string }

export default function Dashboard() {
  const { data, isError, isLoading } = useQuery<Health>({
    queryKey: ['health'],
    queryFn: async () => {
      const r = await fetch('/api/health')
      if (!r.ok) throw new Error(`health check failed: ${r.status}`)
      return r.json()
    },
  })

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-semibold tracking-tight">
          Household Budget
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Income vs. expenses — combined dashboard, per-person budgets.
        </p>

        <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Phase 1 scaffold
          </h2>
          <p className="mt-2 text-sm text-slate-300">
            API status:{' '}
            <span
              className={
                isLoading
                  ? 'text-amber-400'
                  : isError
                    ? 'text-red-400'
                    : 'text-emerald-400'
              }
            >
              {isLoading ? 'checking…' : isError ? 'unreachable' : data?.status}
            </span>
          </p>
          <p className="mt-4 text-xs text-slate-500">
            Dashboard widgets (income vs. expenses, budget progress,
            per-member drill-down) land in Phase 2.
          </p>
        </section>
      </div>
    </main>
  )
}
