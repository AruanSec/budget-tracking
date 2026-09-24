import { useState } from 'react'
import { errorText } from '../api'
import {
  useAccounts,
  useCategories,
  useCreateAccount,
  useCreateCategory,
  useCreateIncomeSource,
  useDeleteCategory,
  useIncomeSources,
  useMembers,
  useUpdateIncomeSource,
} from '../hooks'

const inputCls =
  'rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-emerald-500'
const btnCls =
  'rounded-md bg-slate-700 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-600 disabled:opacity-50'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <h2 className="text-sm font-medium text-slate-200">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Categories() {
  const { data: categories } = useCategories()
  const create = useCreateCategory()
  const remove = useDeleteCategory()
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState<number | ''>('')
  const [error, setError] = useState<string | null>(null)

  const cats = categories ?? []
  const tops = cats.filter((c) => c.parent_id === null)

  async function add(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await create.mutateAsync({ name: name.trim(), parent_id: parentId === '' ? null : parentId })
      setName('')
    } catch (err) {
      setError(errorText(err))
    }
  }

  async function del(id: number) {
    setError(null)
    try {
      await remove.mutateAsync(id)
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <Section title="Categories">
      <form onSubmit={add} className="flex flex-wrap gap-2">
        <input
          className={`${inputCls} min-w-40 flex-1`}
          placeholder="New category…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <select
          className={inputCls}
          value={parentId}
          onChange={(e) => setParentId(e.target.value === '' ? '' : Number(e.target.value))}
        >
          <option value="">Top level</option>
          {tops.map((c) => (
            <option key={c.id} value={c.id}>
              under {c.name}
            </option>
          ))}
        </select>
        <button type="submit" disabled={create.isPending} className={btnCls}>
          Add
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
      <ul className="mt-3 space-y-1">
        {tops.map((t) => (
          <li key={t.id}>
            <Row label={t.name} onDelete={() => del(t.id)} />
            <ul className="ml-5 space-y-1 border-l border-slate-800 pl-3">
              {cats
                .filter((c) => c.parent_id === t.id)
                .map((c) => (
                  <li key={c.id}>
                    <Row label={c.name} onDelete={() => del(c.id)} />
                  </li>
                ))}
            </ul>
          </li>
        ))}
      </ul>
    </Section>
  )
}

function Row({ label, right, onDelete }: { label: string; right?: React.ReactNode; onDelete?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1 text-sm text-slate-300">
      <span className="truncate">{label}</span>
      <span className="flex shrink-0 items-center gap-2">
        {right}
        {onDelete && (
          <button onClick={onDelete} className="text-xs text-slate-500 hover:text-red-400">
            ✕
          </button>
        )}
      </span>
    </div>
  )
}

function Accounts() {
  const { data: accounts } = useAccounts()
  const create = useCreateAccount()
  const [name, setName] = useState('')
  const [type, setType] = useState('checking')
  const [error, setError] = useState<string | null>(null)

  async function add(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await create.mutateAsync({ name: name.trim(), type })
      setName('')
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <Section title="Accounts">
      <form onSubmit={add} className="flex flex-wrap gap-2">
        <input
          className={`${inputCls} min-w-40 flex-1`}
          placeholder="New account…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
          {['checking', 'savings', 'cash', 'credit', 'other'].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button type="submit" disabled={create.isPending} className={btnCls}>
          Add
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
      <ul className="mt-3">
        {(accounts ?? []).map((a) => (
          <li key={a.id}>
            <Row
              label={`${a.name} · ${a.type}`}
              right={a.archived ? <span className="text-[11px] text-slate-500">archived</span> : undefined}
            />
          </li>
        ))}
      </ul>
    </Section>
  )
}

function IncomeSources() {
  const { data: sources } = useIncomeSources()
  const { data: members } = useMembers()
  const create = useCreateIncomeSource()
  const update = useUpdateIncomeSource()
  const [name, setName] = useState('')
  const [memberId, setMemberId] = useState<number | ''>('')
  const [error, setError] = useState<string | null>(null)

  async function add(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (memberId === '') return
    try {
      await create.mutateAsync({ name: name.trim(), member_id: memberId })
      setName('')
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <Section title="Income sources">
      <form onSubmit={add} className="flex flex-wrap gap-2">
        <input
          className={`${inputCls} min-w-40 flex-1`}
          placeholder="New income source…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <select
          className={inputCls}
          value={memberId}
          onChange={(e) => setMemberId(e.target.value === '' ? '' : Number(e.target.value))}
          required
        >
          <option value="" disabled>
            Member…
          </option>
          {(members ?? []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </select>
        <button type="submit" disabled={create.isPending} className={btnCls}>
          Add
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
      <ul className="mt-3">
        {(sources ?? []).map((s) => (
          <li key={s.id}>
            <Row
              label={`${s.name} · ${members?.find((m) => m.id === s.member_id)?.display_name ?? `#${s.member_id}`}`}
              right={
                <button
                  onClick={() => update.mutate({ id: s.id, body: { active: !s.active } })}
                  className={`rounded-full px-2 py-0.5 text-[11px] ${
                    s.active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  {s.active ? 'active' : 'inactive'}
                </button>
              }
            />
          </li>
        ))}
      </ul>
    </Section>
  )
}

export default function Settings() {
  return (
    <div>
      <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Categories />
        <div className="grid gap-4">
          <Accounts />
          <IncomeSources />
        </div>
      </div>
    </div>
  )
}
