// Minimal fetch wrapper: attaches the JWT, normalizes errors, and bounces
// to /login on 401 (except for the login call itself).

export const TOKEN_KEY = 'budget_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `API error ${status}`)
    this.status = status
    this.detail = detail
  }
}

/** Human-readable message from any thrown error (FastAPI details included). */
export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (typeof err.detail === 'string') return err.detail
    if (Array.isArray(err.detail)) {
      return err.detail.map((d: { msg?: string }) => d?.msg ?? JSON.stringify(d)).join('; ')
    }
    return JSON.stringify(err.detail)
  }
  return err instanceof Error ? err.message : 'Request failed'
}

type Opts = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  params?: Record<string, string | number | boolean | undefined | null>
}

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  let url = path
  if (opts.params) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(opts.params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    }
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'

  const r = await fetch(url, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })

  if (r.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/register') {
    clearToken()
    window.location.href = '/login'
    throw new ApiError(401, 'Session expired')
  }
  if (!r.ok) {
    let detail: unknown = r.statusText
    try {
      detail = (await r.json()).detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(r.status, detail)
  }
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}
