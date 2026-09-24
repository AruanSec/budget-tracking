// Types mirroring docs/API.md — money is integer cents everywhere.

export type Member = { id: number; username: string; display_name: string }
export type Account = { id: number; name: string; type: string; archived: boolean }
export type Category = { id: number; name: string; parent_id: number | null }
export type IncomeSource = { id: number; name: string; member_id: number; active: boolean }

export type Split = { id: number; member_id: number; share_cents: number }

export type Transaction = {
  id: number
  type: 'income' | 'expense'
  amount_cents: number
  currency: string
  description: string
  occurred_on: string // YYYY-MM-DD
  account_id: number | null
  category_id: number | null
  income_source_id: number | null
  entered_by: number
  paid_by: number | null
  splits: Split[]
}

export type TransactionIn = {
  type: 'income' | 'expense'
  amount_cents: number
  occurred_on: string
  description?: string
  account_id?: number | null
  category_id?: number | null
  income_source_id?: number | null
  paid_by?: number | null
  splits?: { member_id: number; share_cents: number }[]
}

export type Budget = {
  id: number
  member_id: number
  category_id: number
  month: string // YYYY-MM-01
  amount_cents: number
}

export type MemberSpent = { member_id: number; spent_cents: number }

export type CategorySummary = {
  category_id: number | null
  name: string
  spent_cents: number
  budget_cents: number
  per_member: MemberSpent[]
}

export type MemberSummary = {
  member_id: number
  display_name: string
  income_cents: number
  expense_cents: number
  budget_cents: number
  budget_used_pct: number | null
}

export type DashboardSummary = {
  month: string
  household: {
    income_cents: number
    expense_cents: number
    net_cents: number
    budget_cents: number
    budget_used_pct: number | null
  }
  members: MemberSummary[]
  by_category: CategorySummary[]
}

export type TrendPoint = { month: string; income_cents: number; expense_cents: number }
