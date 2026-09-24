import { useState } from 'react'
import { currentMonth, centsToStr, monthLabel } from '../format'
import { useDashboard, useMembers, useTrend } from '../hooks'

function ProgressBar({ usedPct }: { usedPct: number | null }) {
  if (usedPct === null) return <span className="text-xs text-slate-500">no budget</span>
  const over = usedPct > 100
  const width = Math.min(usedPct, 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full ${over ? 'bg-red-500' : usedPct > 80 ? 'bg-amber-400' : 'bg-emerald-500'}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className={`w-14 shrink-0 text-right text-xs tabular-nums ${over ? 'text-red-400' : 'text-slate-400'}`}>
        {usedPct.toFixed(0)}%
      </span>
    </div>
  )
}

function StatCard({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${tone ?? 'text-slate-100'}`}>{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonth())
  const { data: summary, isLoading } = useDashboard(month)
  const { data: trend } = useTrend(6)
  const { data: members } = useMembers()

  const memberName = (id: number) =>
    members?.find((m) => m.id === id)?.display_name ?? `#${id}`

  const trendMax = Math.max(1, ...(trend ?? []).flatMap((p) => [p.income_cents, p.expense_cents]))

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Dashboard</h1>
        <input
          type="month"
          value={month}
          onChange={(e) => e.target.value && setMonth(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-emerald-500 [color-scheme:dark]"
        />
      </div>

      {isLoading && <p className="mt-6 text-sm text-slate-400">Loading…</p>}

      {summary && (
        <>
          {/* Household headline */}
          <section className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Income" value={centsToStr(summary.household.income_cents)} tone="text-emerald-400" />
            <StatCard label="Expenses" value={centsToStr(summary.household.expense_cents)} tone="text-red-400" />
            <StatCard
              label="Net"
              value={centsToStr(summary.household.net_cents)}
              tone={summary.household.net_cents >= 0 ? 'text-slate-100' : 'text-red-400'}
            />
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">Budget used</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">
                {summary.household.budget_used_pct === null
                  ? '—'
                  : `${summary.household.budget_used_pct.toFixed(0)}%`}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">
                of {centsToStr(summary.household.budget_cents)} budgeted
              </p>
            </div>
          </section>

          {/* Per-member drill-down */}
          <section className="mt-6">
            <h2 className="text-sm font-medium text-slate-300">Members</h2>
            <div className="mt-2 grid gap-3 md:grid-cols-2">
              {summary.members.map((m) => (
                <div key={m.member_id} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm font-medium">{m.display_name}</span>
                    <span className="text-xs text-slate-500">
                      in {centsToStr(m.income_cents)} · out {centsToStr(m.expense_cents)}
                    </span>
                  </div>
                  <div className="mt-3">
                    <ProgressBar usedPct={m.budget_used_pct} />
                  </div>
                  <p className="mt-1.5 text-[11px] text-slate-500">
                    {centsToStr(m.expense_cents)} of {centsToStr(m.budget_cents)} budget
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Spend by category */}
          <section className="mt-6">
            <h2 className="text-sm font-medium text-slate-300">
              Spend by category <span className="text-slate-500">· {monthLabel(summary.month)}</span>
            </h2>
            {summary.by_category.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">No spending recorded yet.</p>
            ) : (
              <ul className="mt-2 divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
                {summary.by_category.map((c) => (
                  <li key={c.category_id ?? 'none'} className="px-4 py-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm">{c.name}</span>
                      <span className="text-sm tabular-nums text-slate-300">
                        {centsToStr(c.spent_cents)}
                        {c.budget_cents > 0 && (
                          <span className="text-xs text-slate-500"> / {centsToStr(c.budget_cents)}</span>
                        )}
                      </span>
                    </div>
                    <div className="mt-2">
                      <ProgressBar
                        usedPct={c.budget_cents > 0 ? (c.spent_cents / c.budget_cents) * 100 : null}
                      />
                    </div>
                    {c.per_member.length > 1 && (
                      <p className="mt-1.5 text-[11px] text-slate-500">
                        {c.per_member
                          .map((pm) => `${memberName(pm.member_id)} ${centsToStr(pm.spent_cents)}`)
                          .join(' · ')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Trend */}
          {trend && trend.length > 0 && (
            <section className="mt-6">
              <h2 className="text-sm font-medium text-slate-300">Last {trend.length} months</h2>
              <div className="mt-2 rounded-xl border border-slate-800 bg-slate-900 p-4">
                <div className="flex h-32 items-end gap-3">
                  {trend.map((p) => (
                    <div key={p.month} className="flex flex-1 flex-col items-center gap-1">
                      <div className="flex h-full w-full items-end justify-center gap-1">
                        <div
                          className="w-1/3 rounded-t bg-emerald-500/80"
                          style={{ height: `${(p.income_cents / trendMax) * 100}%` }}
                          title={`Income ${centsToStr(p.income_cents)}`}
                        />
                        <div
                          className="w-1/3 rounded-t bg-red-500/80"
                          style={{ height: `${(p.expense_cents / trendMax) * 100}%` }}
                          title={`Expenses ${centsToStr(p.expense_cents)}`}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500">{p.month.slice(5)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 flex gap-4 text-[11px] text-slate-500">
                  <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-500/80" />Income</span>
                  <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-red-500/80" />Expenses</span>
                </p>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
