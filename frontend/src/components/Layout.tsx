import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { clearToken } from '../api'
import { useMe } from '../hooks'

const tabs = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/transactions', label: 'Activity', icon: '⇄' },
  { to: '/budgets', label: 'Budgets', icon: '◎' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
]

export default function Layout() {
  const navigate = useNavigate()
  const { data: me } = useMe()

  function logout() {
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      {/* Top bar */}
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <span className="text-sm font-semibold tracking-tight">Household Budget</span>
          <div className="flex items-center gap-3">
            {me && <span className="text-xs text-slate-400">{me.display_name}</span>}
            <button
              onClick={logout}
              className="rounded-md border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-500"
            >
              Sign out
            </button>
          </div>
        </div>
        {/* Desktop nav */}
        <nav className="mx-auto hidden max-w-5xl gap-1 px-4 pb-2 md:flex">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.to === '/'}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm ${
                  isActive
                    ? 'bg-slate-800 text-emerald-400'
                    : 'text-slate-400 hover:text-slate-200'
                }`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 pb-24 md:pb-8">
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-4 border-t border-slate-800 bg-slate-950/95 backdrop-blur md:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 py-2 text-[11px] ${
                isActive ? 'text-emerald-400' : 'text-slate-500'
              }`
            }
          >
            <span className="text-base leading-none">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
