import { useState } from 'react'
import { errorText } from '../api'
import {
  useAdminStats,
  useAdminUsers,
  useCreateAdminUser,
  useDeleteAdminUser,
  useMe,
  useResetUserPassword,
  useUpdateAdminUser,
} from '../hooks'
import type { AdminUser } from '../types'
import { centsToStr } from '../format'

const inputCls =
  'rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-emerald-500'
const btnCls =
  'rounded-md bg-slate-700 px-3 py-1.5 text-sm text-slate-100 hover:bg-slate-600 disabled:opacity-50'

function Stats() {
  const { data: s } = useAdminStats()
  if (!s) return null
  const cells: [string, string | number][] = [
    ['Users', `${s.users_active}/${s.users_total} active`],
    ['Admins', s.admins_active],
    ['Transactions', s.transactions_total],
    ['This month', `$${centsToStr(s.transactions_this_month_cents)}`],
    ['Categories', s.categories_total],
    ['Accounts', s.accounts_total],
    ['Income sources', s.income_sources_total],
    ['Budget lines', s.budgets_total],
  ]
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {cells.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-slate-800 bg-slate-900 p-3">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
          <div className="mt-1 text-sm font-medium text-slate-100">{value}</div>
        </div>
      ))}
    </div>
  )
}

function UserRow({ user, isSelf, onError }: { user: AdminUser; isSelf: boolean; onError: (m: string) => void }) {
  const update = useUpdateAdminUser()
  const reset = useResetUserPassword()
  const del = useDeleteAdminUser()

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn()
    } catch (err) {
      onError(errorText(err))
    }
  }

  function resetPw() {
    const value = window.prompt(`New password for ${user.username} (min 8 chars):`)
    if (!value) return
    if (value.length < 8) return onError('New password must be at least 8 characters')
    act(() => reset.mutateAsync({ id: user.id, newpw: value }))
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 py-3 text-sm last:border-0">
      <div className="min-w-36 flex-1">
        <span className="font-medium text-slate-100">{user.display_name}</span>
        {isSelf && <span className="ml-2 text-[11px] text-emerald-400">you</span>}
        <div className="text-xs text-slate-500">
          @{user.username} · joined {new Date(user.created_at).toLocaleDateString()}
        </div>
      </div>
      <span
        className={`rounded-full px-2 py-0.5 text-[11px] ${
          user.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
        }`}
      >
        {user.is_active ? 'active' : 'disabled'}
      </span>
      <select
        className={inputCls}
        value={user.role}
        disabled={isSelf || update.isPending}
        title={isSelf ? 'You cannot change your own role' : 'Role'}
        onChange={(e) => act(() => update.mutateAsync({ id: user.id, body: { role: e.target.value as AdminUser['role'] } }))}
      >
        <option value="member">member</option>
        <option value="admin">admin</option>
      </select>
      <button
        onClick={() => act(() => update.mutateAsync({ id: user.id, body: { is_active: !user.is_active } }))}
        disabled={isSelf || update.isPending}
        title={isSelf ? 'You cannot deactivate yourself' : user.is_active ? 'Disable login' : 'Re-enable login'}
        className={btnCls}
      >
        {user.is_active ? 'Disable' : 'Enable'}
      </button>
      <button onClick={resetPw} disabled={reset.isPending} className={btnCls} title="Set a new password">
        Reset pw
      </button>
      <button
        onClick={() => {
          if (!window.confirm(`Delete ${user.username} entirely? Only works if they have no transaction history.`)) return
          act(() => del.mutateAsync(user.id))
        }}
        disabled={isSelf || del.isPending}
        className="rounded-md border border-red-900 px-3 py-1.5 text-sm text-red-400 hover:bg-red-950 disabled:opacity-40"
      >
        Delete
      </button>
    </div>
  )
}

function AddUser({ onError }: { onError: (m: string) => void }) {
  const create = useCreateAdminUser()
  const [username, setUsername] = useState('')
  const [display, setDisplay] = useState('')
  const [pw, setPw] = useState('')
  const [role, setRole] = useState<'admin' | 'member'>('member')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (pw.length < 8) return onError('Password must be at least 8 characters')
    try {
      await create.mutateAsync({
        username: username.trim(),
        display_name: display.trim() || null,
        password: pw,
        role,
      })
      setUsername('')
      setDisplay('')
      setPw('')
      setRole('member')
    } catch (err) {
      onError(errorText(err))
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap gap-2">
      <input className={`${inputCls} min-w-32 flex-1`} placeholder="username" value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} />
      <input className={`${inputCls} min-w-32 flex-1`} placeholder="display name (optional)" value={display} onChange={(e) => setDisplay(e.target.value)} />
      <input className={`${inputCls} min-w-32 flex-1`} type="password" autoComplete="new-password" placeholder="initial password" value={pw} onChange={(e) => setPw(e.target.value)} required />
      <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value as 'admin' | 'member')}>
        <option value="member">member</option>
        <option value="admin">admin</option>
      </select>
      <button type="submit" disabled={create.isPending} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
        Add user
      </button>
    </form>
  )
}

export default function Admin() {
  const { data: me } = useMe()
  const { data: users } = useAdminUsers()
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold tracking-tight">Admin</h1>
      {error && (
        <p className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}
      <Stats />
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-sm font-medium text-slate-200">Users</h2>
        <div className="mt-2">
          {(users ?? []).map((u) => (
            <UserRow key={u.id} user={u} isSelf={u.id === me?.id} onError={setError} />
          ))}
        </div>
        <div className="mt-4 border-t border-slate-800 pt-4">
          <AddUser onError={setError} />
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Guards: you cannot disable, demote, or delete your own account, and the last active
          admin can never be removed. Self-service signup lives at /register.
        </p>
      </section>
    </div>
  )
}
