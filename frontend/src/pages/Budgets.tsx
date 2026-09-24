import { useEffect, useMemo, useState } from 'react'
import { errorText } from '../api'
import { useBudgets, useCategories, useDashboard, useDeleteBudget, useMembers, useUpsertBudget } from '../hooks'
import { centsToStr, currentMonth, monthLabel, strToCents } from '../format'

type CellKey = string // `${memberId}:${categoryId}`

export default function Budgets() {
  const [month, setMonth] = useState(currentMonth())
  const [drafts, setDrafts] = useState<Record<CellKey, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<CellKey | null>(null)

  const { data: budgets } = useBudgets(month)
  const { data: categories } = useCategories()
  const { data: members } = useMembers()
  const { data: summary } = useDashboard(month)
  const upsert = useUpsertBudget()
  const remove = useDeleteBudget()

  const budgetByCell = useMemo(() => {
    const map = new Map<CellKey, { id: number; amount_cents: number }>()
    for (const b of budgets ?? []) map.set(`${b.member_id}:${b.category_id}`, b)
    return map
  }, [budgets])

  // Spent per (member, category) from the dashboard read model
  const spentByCell = useMemo(() => {
    const map = new Map<CellKey, number>()
    for (const c of summary?.by_category ?? []) {
      if (c.category_id === null) continue
      for (const pm of c.per_member) map.set(`${pm.member_id}:${c.category_id}`, pm.spent_cents)
    }
    return map
  }, [summary])

  // Seed drafts when server data arrives; a cell being edited keeps its draft.
  useEffect(() => {
    setDrafts((prev) => {
      const next: Record<CellKey, string> = { ...prev }
      for (const [key, b] of budgetByCell) {
        if (next[key] === undefined) next[key] = centsToStr(b.amount_cents)
      }
      return next
    })
  }, [budgetByCell, month])

  useEffect(() => {
    setDrafts({})
  }, [month])

  // Categories: parents first, then children indented
  const orderedCategories = useMemo(() => {
    const cats = categories ?? []
    const tops = cats.filter((c) => c.parent_id === null)
    const out: { id: number; label: string }[] = []
    for (const t of tops) {
      out.push({ id: t.id, label: t.name })
      for (const child of cats.filter((c) => c.parent_id === t.id)) {
        out.push({ id: child.id, label: `  ↳ ${child.name}` })
      }
    }
    return out
  }, [categories])

  async function saveCell(memberId: number, categoryId: number, key: CellKey) {
    setError(null)
    const raw = (drafts[key] ?? '').trim()
    const existing = budgetByCell.get(key)
    const cents = raw === '' ? null : strToCents(raw)
    if (raw !== '' && cents === null) {
      setError('Budget amounts must be non-negative numbers')
      return
    }
    if (existing && cents === existing.amount_cents) return // no change
    setSaving(key)
    try {
      if (cents === null) {
        if (existing) await remove.mutateAsync(existing.id)
      } else {
        await upsert.mutateAsync({
          member_id: memberId,
          category_id: categoryId,
          month: `${month}-01`,
          amount_cents: cents,
        })
      }
      setDrafts((d) => ({ ...d, [key]: cents === null ? '' : centsToStr(cents) }))
    } catch (err) {
      setError(errorText(err))
    } finally {
      setSaving(null)
    }
  }

  const inputCls =
    'w-24 rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-right text-sm tabular-nums text-slate-100 outline-none focus:border-emerald-500'

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Budgets</h1>
        <input
          type="month"
          value={month}
          onChange={(e) => e.target.value && setMonth(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-emerald-500 [color-scheme:dark]"
        />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Per-person monthly budgets · {monthLabel(month)} · changes save when you leave the field
      </p>
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-2.5 font-medium">Category</th>
              {(members ?? []).map((m) => (
                <th key={m.id} className="px-4 py-2.5 text-right font-medium">
                  {m.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {orderedCategories.map((c) => (
              <tr key={c.id}>
                <td className="whitespace-pre px-4 py-2 text-slate-300">{c.label}</td>
                {(members ?? []).map((m) => {
                  const key = `${m.id}:${c.id}`
                  const spent = spentByCell.get(key) ?? 0
                  const budget = budgetByCell.get(key)?.amount_cents ?? 0
                  const over = budget > 0 && spent > budget
                  return (
                    <td key={key} className="px-4 py-2 text-right">
                      <input
                        className={inputCls}
                        inputMode="decimal"
                        placeholder="—"
                        value={drafts[key] ?? ''}
                        disabled={saving === key}
                        onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
                        onBlur={() => saveCell(m.id, c.id, key)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                        }}
                      />
                      {spent > 0 && (
                        <p className={`mt-0.5 text-[11px] tabular-nums ${over ? 'text-red-400' : 'text-slate-500'}`}>
                          spent {centsToStr(spent)}
                        </p>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
            {orderedCategories.length === 0 && (
              <tr>
                <td colSpan={(members?.length ?? 0) + 1} className="px-4 py-6 text-center text-slate-500">
                  No categories yet — add them in Settings.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
