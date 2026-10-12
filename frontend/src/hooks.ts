import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type {
  Account,
  AdminStats,
  AdminUser,
  Budget,
  Category,
  DashboardSummary,
  IncomeSource,
  Member,
  Transaction,
  TransactionIn,
  TrendPoint,
} from './types'

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => api<Member>('/api/auth/me') })
}

export function useMembers() {
  return useQuery({ queryKey: ['members'], queryFn: () => api<Member[]>('/api/members') })
}

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/api/categories') })
}

export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/api/accounts') })
}

export function useIncomeSources() {
  return useQuery({
    queryKey: ['income-sources'],
    queryFn: () => api<IncomeSource[]>('/api/income-sources'),
  })
}

export function useTransactions(params: {
  month?: string
  type?: string
  member_id?: number
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ['transactions', params],
    queryFn: () => api<Transaction[]>('/api/transactions', { params }),
  })
}

export function useDashboard(month: string) {
  return useQuery({
    queryKey: ['dashboard', 'summary', month],
    queryFn: () => api<DashboardSummary>('/api/dashboard/summary', { params: { month } }),
  })
}

export function useTrend(months = 6) {
  return useQuery({
    queryKey: ['dashboard', 'trend', months],
    queryFn: () => api<TrendPoint[]>('/api/dashboard/trend', { params: { months } }),
  })
}

export function useBudgets(month: string) {
  return useQuery({
    queryKey: ['budgets', month],
    queryFn: () => api<Budget[]>('/api/budgets', { params: { month } }),
  })
}

/** Invalidates every list that a transaction/budget mutation could move. */
export function useInvalidateMoney() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['transactions'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['budgets'] })
  }
}

export function useCreateTransaction() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: (body: TransactionIn) =>
      api<Transaction>('/api/transactions', { method: 'POST', body }),
    onSuccess: invalidate,
  })
}

export function useUpdateTransaction() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<TransactionIn> }) =>
      api<Transaction>(`/api/transactions/${id}`, { method: 'PATCH', body }),
    onSuccess: invalidate,
  })
}

export function useDeleteTransaction() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/api/transactions/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
}

export function useUpsertBudget() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: (body: {
      member_id: number
      category_id: number
      month: string
      amount_cents: number
    }) => api<Budget>('/api/budgets', { method: 'PUT', body }),
    onSuccess: invalidate,
  })
}

export function useDeleteBudget() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/api/budgets/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; parent_id?: number | null }) =>
      api<Category>('/api/categories', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useDeleteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/api/categories/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  })
}

export function useCreateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; type?: string }) =>
      api<Account>('/api/accounts', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['accounts'] }),
  })
}

export function useCreateIncomeSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; member_id: number }) =>
      api<IncomeSource>('/api/income-sources', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['income-sources'] }),
  })
}

export function useUpdateIncomeSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: { name?: string; active?: boolean } }) =>
      api<IncomeSource>(`/api/income-sources/${id}`, { method: 'PATCH', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['income-sources'] }),
  })
}

// ---------- admin ----------

export function useAdminUsers() {
  return useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => api<AdminUser[]>('/api/admin/users'),
  })
}

export function useAdminStats() {
  return useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => api<AdminStats>('/api/admin/stats'),
    staleTime: 10_000,
  })
}

/** Every admin mutation touches the user list and the counts strip. */
function useInvalidateAdmin() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['admin'] })
    qc.invalidateQueries({ queryKey: ['members'] })
  }
}

export function useCreateAdminUser() {
  const invalidate = useInvalidateAdmin()
  return useMutation({
    mutationFn: (body: {
      username: string
      password: string
      display_name?: string | null
      role?: 'admin' | 'member'
    }) => api<AdminUser>('/api/admin/users', { method: 'POST', body }),
    onSuccess: invalidate,
  })
}

export function useUpdateAdminUser() {
  const invalidate = useInvalidateAdmin()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number
      body: { display_name?: string; role?: 'admin' | 'member'; is_active?: boolean }
    }) => api<AdminUser>(`/api/admin/users/${id}`, { method: 'PATCH', body }),
    onSuccess: invalidate,
  })
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: ({ id, newpw }: { id: number; newpw: string }) =>
      api<void>(`/api/admin/users/${id}/password`, { method: 'POST', body: { password: newpw } }),
  })
}

export function useDeleteAdminUser() {
  const invalidate = useInvalidateAdmin()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/api/admin/users/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
}
