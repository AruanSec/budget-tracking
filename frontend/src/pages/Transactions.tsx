import { useMemo, useState } from 'react'
import { errorText } from '../api'
import TransactionForm from '../components/TransactionForm'
import {
  useCategories,
  useDeleteTransaction,
  useIncomeSources,
  useMe,
  useMembers,
  useTransactions,
} from '../hooks'
import { centsToStr, currentMonth, monthLabel } from '../format'
import type { Transaction } from '../types'

export default function Transactions() {
  const [month, setMonth] = useState(currentMonth())
  const [typeFilter, setTypeFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: transactions, isLoading } = useTransactions({
    month,
    type: typeFilter || undefined,
    limit: 200,
  })
  const { data: categories } = useCategories()
  const { data: incomeSources } = useIncomeSources()
  const { data: members } = useMembers()
  const { data: me } = useMe()
  const deleteTx = useDeleteTransaction()

  const categoryName = useMemo(() => {
    const map = new Map<number, string>()
    for (const c of categories ?? []) {
      const parent = c.parent_id ? categories?.find((p) => p.id === c.parent_id) : null
      map.set(c.id, parent ? `${parent.name} › ${c.name}` : c.name)
    }
    return map
  }, [categories])

  const memberName = (id: number) => members?.find((m) => m.id === id)?.display_name ?? `#${id}`

  // Group by date, newest first (API already sorts desc)
  const groups = useMemo(() => {
    const out: { date: string; items: Transaction[] }[] = []
    for (const tx of transactions ?? []) {
      const last = out[out.length - 1]
      if (last && last.date === tx.occurred_on) last.items.push(tx)
      else out.push({ date: tx.occurred_on, items: [tx] })
    }
    return out
  }, [transactions])

  const totals = useMemo(() => {
    let income = 0
    let expense = 0
    for (const tx of transactions ?? []) {
      if (tx.type === 'income') income += tx.amount_cents
      else expense += tx.amount_cents
    }
    return { income, expense }
  }, [transactions])

  async function doDelete(id: number) {
    setError(null)
    try {
      await deleteTx.mutateAsync(id)
      setConfirmDelete(null)
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Activity</h1>
        <button
          onClick={() => {
            setEditing(null)
            setShowForm(true)
          }}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500"
        >
          + Add
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          type="month"
          value={month}
          onChange={(e) => e.target.value && setMonth(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-emerald-500 [color-scheme:dark]"
        />
        <div className="flex gap-1 rounded-lg bg-slate-900 p-1">
          {[
            ['', 'All'],
            ['expense', 'Out'],
            ['income', 'In'],
          ].map(([v, label]) => (
            <button
              key={v}
              onClick={() => setTypeFilter(v)}
              className={`rounded-md px-2.5 py-1 text-xs ${typeFilter === v ? 'bg-slate-700 text-slate-100' : 'text-slate-400'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-slate-500">
          <span className="text-emerald-400">+{centsToStr(totals.income)}</span>{' '}
          <span className="text-red-400">−{centsToStr(totals.expense)}</span>
        </span>
      </div>

      {(showForm || editing) && (
        <div className="mt-4">
          <TransactionForm
            editing={editing}
            onDone={() => {
              setShowForm(false)
              setEditing(null)
            }}
          />
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      {isLoading && <p className="mt-6 text-sm text-slate-400">Loading…</p>}

      {!isLoading && (transactions ?? []).length === 0 && (
        <p className="mt-6 text-sm text-slate-500">
          Nothing recorded in {monthLabel(month)} yet. Tap + Add for the first one.
        </p>
      )}

      <div className="mt-4 space-y-4">
        {groups.map((g) => (
          <section key={g.date}>
            <h2 className="text-xs font-medium uppercase tracking-wide text-slate-500">{g.date}</h2>
            <ul className="mt-1 divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
              {g.items.map((tx) => (
                <li key={tx.id} className="px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm">
                        {tx.description ||
                          (tx.type === 'expense'
                            ? (tx.category_id !== null && categoryName.get(tx.category_id)) || 'Expense'
                            : (incomeSources?.find((s) => s.id === tx.income_source_id)?.name ?? 'Income'))}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        {tx.type === 'expense' && tx.category_id !== null && categoryName.get(tx.category_id)}
                        {tx.type === 'income' &&
                          incomeSources?.find((s) => s.id === tx.income_source_id)?.name}
                        {tx.type === 'expense' && tx.splits.length > 0 && (
                          <span>
                            {' · '}
                            {tx.splits.length === 1 && tx.splits[0].member_id === me?.id
                              ? 'just me'
                              : tx.splits
                                  .map((s) => `${memberName(s.member_id)} ${centsToStr(s.share_cents)}`)
                                  .join(', ')}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span
                        className={`text-sm tabular-nums ${tx.type === 'income' ? 'text-emerald-400' : 'text-slate-200'}`}
                      >
                        {tx.type === 'income' ? '+' : '−'}
                        {centsToStr(tx.amount_cents)}
                      </span>
                      {confirmDelete === tx.id ? (
                        <span className="flex gap-1">
                          <button
                            onClick={() => doDelete(tx.id)}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="rounded bg-slate-700 px-2 py-1 text-xs"
                          >
                            Keep
                          </button>
                        </span>
                      ) : (
                        <span className="flex gap-1">
                          <button
                            onClick={() => {
                              setEditing(tx)
                              setShowForm(false)
                              window.scrollTo({ top: 0 })
                            }}
                            className="rounded px-1.5 py-1 text-xs text-slate-400 hover:text-slate-200"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => setConfirmDelete(tx.id)}
                            className="rounded px-1.5 py-1 text-xs text-slate-500 hover:text-red-400"
                          >
                            ✕
                          </button>
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
