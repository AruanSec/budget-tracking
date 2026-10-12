import { useEffect, useMemo, useState } from 'react'
import { errorText } from '../api'
import {
  useAccounts,
  useCategories,
  useCreateTransaction,
  useIncomeSources,
  useMe,
  useMembers,
  useUpdateTransaction,
} from '../hooks'
import { centsToStr, evenSplit, strToCents, today } from '../format'
import type { Transaction } from '../types'

type SplitDraft = Record<number, string> // member_id -> dollars string

export default function TransactionForm({
  editing,
  onDone,
}: {
  editing: Transaction | null
  onDone: () => void
}) {
  const { data: me } = useMe()
  const { data: members } = useMembers()
  const { data: categories } = useCategories()
  const { data: accounts } = useAccounts()
  const { data: incomeSources } = useIncomeSources()
  const create = useCreateTransaction()
  const update = useUpdateTransaction()

  const [type, setType] = useState<'expense' | 'income'>('expense')
  const [amount, setAmount] = useState('')
  const [occurredOn, setOccurredOn] = useState(today())
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState<number | ''>('')
  const [incomeSourceId, setIncomeSourceId] = useState<number | ''>('')
  const [accountId, setAccountId] = useState<number | ''>('')
  const [paidBy, setPaidBy] = useState<number | ''>('')
  const [splitMode, setSplitMode] = useState<'solo' | 'shared'>('solo')
  const [splits, setSplits] = useState<SplitDraft>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!editing) return
    setType(editing.type)
    setAmount(centsToStr(editing.amount_cents))
    setOccurredOn(editing.occurred_on)
    setDescription(editing.description)
    setCategoryId(editing.category_id ?? '')
    setIncomeSourceId(editing.income_source_id ?? '')
    setAccountId(editing.account_id ?? '')
    setPaidBy(editing.paid_by ?? '')
    if (editing.type === 'expense') {
      const mine = me && editing.splits.length === 1 && editing.splits[0].member_id === me.id
      setSplitMode(mine ? 'solo' : 'shared')
      setSplits(
        Object.fromEntries(editing.splits.map((s) => [s.member_id, centsToStr(s.share_cents)])),
      )
    }
  }, [editing, me])

  const amountCents = amount ? strToCents(amount) : null
  const activeMembers = useMemo(() => {
    const rows = [...(members ?? [])]
    for (const split of editing?.splits ?? []) {
      if (!rows.some((m) => m.id === split.member_id)) {
        rows.push({ id: split.member_id, username: "", display_name: `Member #${split.member_id} (inactive)`, role: "member" })
      }
    }
    return rows
  }, [members, editing])

  const splitRows = useMemo(() => {
    if (type !== 'expense') return []
    if (splitMode === 'solo') {
      return me ? [{ member_id: me.id, share_cents: amountCents ?? 0 }] : []
    }
    return activeMembers.map((m) => ({
      member_id: m.id,
      share_cents: strToCents(splits[m.id] ?? '') ?? 0,
    }))
  }, [type, splitMode, me, activeMembers, splits, amountCents])

  const splitSum = splitRows.reduce((acc, s) => acc + s.share_cents, 0)
  const splitsBalanced = type === 'income' || (amountCents !== null && splitSum === amountCents)

  function splitEvenly() {
    if (amountCents === null || activeMembers.length === 0) return
    const shares = evenSplit(amountCents, activeMembers.length)
    setSplits(
      Object.fromEntries(activeMembers.map((m, i) => [m.id, centsToStr(shares[i])])),
    )
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (amountCents === null || amountCents <= 0) {
      setError('Enter a positive amount')
      return
    }
    const base = {
      type,
      amount_cents: amountCents,
      occurred_on: occurredOn,
      description,
      account_id: accountId === '' ? null : accountId,
    }
    const body =
      type === 'expense'
        ? {
            ...base,
            category_id: categoryId === '' ? null : categoryId,
            paid_by: paidBy === '' ? null : paidBy,
            splits: splitRows.filter((s) => s.share_cents > 0).map((s) => ({ member_id: s.member_id, share_cents: s.share_cents })),
          }
        : { ...base, income_source_id: incomeSourceId === '' ? null : incomeSourceId }

    try {
      if (editing) {
        await update.mutateAsync({ id: editing.id, body })
      } else {
        await create.mutateAsync(body)
      }
      onDone()
    } catch (err) {
      setError(errorText(err))
    }
  }

  const inputCls =
    'w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500'
  const busy = create.isPending || update.isPending

  return (
    <form onSubmit={submit} className="rounded-xl border border-slate-700 bg-slate-900 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{editing ? 'Edit transaction' : 'New transaction'}</h3>
        <button type="button" onClick={onDone} className="text-xs text-slate-400 hover:text-slate-200">
          Cancel
        </button>
      </div>

      {/* Type toggle */}
      <div className="mt-3 grid grid-cols-2 gap-1 rounded-lg bg-slate-800 p-1">
        {(['expense', 'income'] as const).map((t) => (
          <button
            key={t}
            type="button"
            disabled={!!editing}
            onClick={() => setType(t)}
            className={`rounded-md py-1.5 text-sm capitalize disabled:opacity-40 ${
              type === t
                ? t === 'expense'
                  ? 'bg-red-500/20 text-red-300'
                  : 'bg-emerald-500/20 text-emerald-300'
                : 'text-slate-400'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="block text-xs text-slate-400">
          Amount
          <input
            className={inputCls}
            inputMode="decimal"
            placeholder="0.00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label className="block text-xs text-slate-400">
          Date
          <input
            type="date"
            className={`${inputCls} [color-scheme:dark]`}
            value={occurredOn}
            onChange={(e) => setOccurredOn(e.target.value)}
            required
          />
        </label>
      </div>

      <label className="mt-3 block text-xs text-slate-400">
        Description
        <input
          className={inputCls}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={type === 'expense' ? 'Groceries at…' : 'Salary'}
          maxLength={255}
        />
      </label>

      {type === 'expense' ? (
        <label className="mt-3 block text-xs text-slate-400">
          Category
          <select
            className={inputCls}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value === '' ? '' : Number(e.target.value))}
            required
          >
            <option value="" disabled>
              Select category…
            </option>
            {(categories ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.parent_id
                  ? `${categories?.find((p) => p.id === c.parent_id)?.name ?? ''} › ${c.name}`
                  : c.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="mt-3 block text-xs text-slate-400">
          Income source
          <select
            className={inputCls}
            value={incomeSourceId}
            onChange={(e) =>
              setIncomeSourceId(e.target.value === '' ? '' : Number(e.target.value))
            }
            required
          >
            <option value="" disabled>
              Select source…
            </option>
            {(incomeSources ?? [])
              .filter((s) => s.active)
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({members?.find((m) => m.id === s.member_id)?.display_name})
                </option>
              ))}
          </select>
        </label>
      )}

      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="block text-xs text-slate-400">
          Account <span className="text-slate-600">(optional)</span>
          <select
            className={inputCls}
            value={accountId}
            onChange={(e) => setAccountId(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value="">None</option>
            {(accounts ?? [])
              .filter((a) => !a.archived)
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
          </select>
        </label>
        {type === 'expense' && (
          <label className="block text-xs text-slate-400">
            Paid by <span className="text-slate-600">(optional)</span>
            <select
              className={inputCls}
              value={paidBy}
              onChange={(e) => setPaidBy(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">Unspecified</option>
              {activeMembers.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {/* Splits (expenses only) */}
      {type === 'expense' && (
        <div className="mt-4 rounded-lg border border-slate-800 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Who does this hit?</span>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => setSplitMode('solo')}
                className={`rounded-md px-2 py-1 text-xs ${splitMode === 'solo' ? 'bg-slate-700 text-slate-100' : 'text-slate-400'}`}
              >
                Just me
              </button>
              <button
                type="button"
                onClick={() => {
                  setSplitMode('shared')
                  splitEvenly()
                }}
                className={`rounded-md px-2 py-1 text-xs ${splitMode === 'shared' ? 'bg-slate-700 text-slate-100' : 'text-slate-400'}`}
              >
                Split
              </button>
            </div>
          </div>
          {splitMode === 'solo' ? (
            <p className="mt-2 text-xs text-slate-500">
              100% to {me?.display_name ?? 'you'}
              {amountCents !== null && ` · ${centsToStr(amountCents)}`}
            </p>
          ) : (
            <div className="mt-2 space-y-2">
              {activeMembers.map((m) => (
                <label key={m.id} className="flex items-center gap-2 text-xs text-slate-400">
                  <span className="w-24 truncate">{m.display_name}</span>
                  <input
                    className={inputCls}
                    inputMode="decimal"
                    placeholder="0.00"
                    value={splits[m.id] ?? ''}
                    onChange={(e) => setSplits((s) => ({ ...s, [m.id]: e.target.value }))}
                  />
                </label>
              ))}
              <div className="flex items-center justify-between text-xs">
                <button type="button" onClick={splitEvenly} className="text-emerald-400 hover:underline">
                  Even split
                </button>
                <span className={splitsBalanced ? 'text-slate-500' : 'text-red-400'}>
                  {centsToStr(splitSum)} of {amountCents !== null ? centsToStr(amountCents) : '0.00'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      {!splitsBalanced && amountCents !== null && (
        <p className="mt-2 text-xs text-amber-400">Split shares must add up to the amount.</p>
      )}

      <button
        type="submit"
        disabled={busy || !splitsBalanced}
        className="mt-4 w-full rounded-md bg-emerald-600 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {busy ? 'Saving…' : editing ? 'Save changes' : 'Add transaction'}
      </button>
    </form>
  )
}
