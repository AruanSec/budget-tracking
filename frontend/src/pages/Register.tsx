import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, errorText, setToken } from '../api'

type RegisterResponse = { access_token: string }

const fieldCls =
  'mt-1 w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-slate-100 outline-none focus:border-emerald-500'

/** Self-service signup. New accounts join as regular members and land
 *  straight in the app — except on a brand-new install with no admin,
 *  where the first registrant becomes the admin (server decides). */
export default function Register() {
  const [username, setUsername] = useState('')
  const [display, setDisplay] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (pw.length < 8) return setError('Password must be at least 8 characters')
    if (pw !== pw2) return setError('Passwords do not match')
    setBusy(true)
    try {
      const r = await api<RegisterResponse>('/api/auth/register', {
        method: 'POST',
        body: {
          username: username.trim(),
          display_name: display.trim() || null,
          password: pw,
        },
      })
      setToken(r.access_token)
      window.location.href = '/'
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-slate-800 bg-slate-900 p-6"
      >
        <h1 className="text-lg font-semibold text-slate-100">Create account</h1>
        <p className="mt-1 text-xs text-slate-500">
          Household members only — this app is reachable from the tailnet.
        </p>
        <label className="mt-4 block text-sm text-slate-300">
          Username
          <input
            className={fieldCls}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            minLength={2}
            required
          />
        </label>
        <label className="mt-3 block text-sm text-slate-300">
          Display name <span className="text-slate-500">(optional)</span>
          <input
            className={fieldCls}
            value={display}
            onChange={(e) => setDisplay(e.target.value)}
          />
        </label>
        <label className="mt-3 block text-sm text-slate-300">
          Password
          <input
            type="password"
            className={fieldCls}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        <label className="mt-3 block text-sm text-slate-300">
          Repeat password
          <input
            type="password"
            className={fieldCls}
            value={pw2}
            onChange={(e) => setPw2(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-md bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {busy ? 'Creating…' : 'Create account'}
        </button>
        <p className="mt-3 text-center text-xs text-slate-500">
          Already registered?{' '}
          <Link to="/login" className="text-emerald-400 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </main>
  )
}
