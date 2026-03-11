export type TaskStatus = 'pending' | 'completed' | 'dropped' | 'deferred'
export type TaskSource = 'today' | 'carried_over' | 'suggested' | 'negotiation' | 'ad_hoc'
export type TaskPriority = 'high' | 'normal' | 'low'
export type DayStatus = 'no_draft' | 'draft' | 'active' | 'completed'

export interface NewsItem {
  id: string
  topic: string
  headline: string
  summary: string
  url: string
  published: string
  relevance: number
}

export interface CalendarEvent {
  id: string
  title: string
  time_start?: string
  time_end?: string
  location?: string
  all_day: boolean
}

export interface CalendarTomorrowEvent {
  title: string
  start?: string
  all_day: boolean
}

export interface Task {
  id: string
  text: string
  source: TaskSource
  priority: TaskPriority
  status: TaskStatus
  notes?: string
  drop_reason?: string
  deferred_to?: string
  completed_at?: string
}

export interface Training {
  summary: string
  plan_reference?: string
}

export interface Draft {
  schema_version: number
  date: string
  generated_at: string
  news: NewsItem[]
  schedule: CalendarEvent[]
  tomorrow_preview: CalendarTomorrowEvent[]
  tasks: Task[]
  training: Training
  agent_suggestions: string[]
}

export interface DayTasks {
  date: string
  tasks: Task[]
}

export interface DayStats {
  completed: number
  remaining: number
  deferred: number
  dropped: number
}

export interface Freshness {
  calendar: boolean
  news: boolean
  age_minutes?: number
}

export interface ApiResponseNoDraft {
  status: 'no_draft'
}

export interface ApiResponseDraft {
  status: 'draft'
  draft: Draft
  freshness: Freshness
  tasks?: DayTasks  // Tasks added during negotiation via POST /api/tasks
}

export interface ApiResponseActive {
  status: 'active'
  plan: Draft
  schedule: CalendarEvent[]
  tasks: DayTasks
  stats: DayStats
}

export interface ApiResponseCompleted {
  status: 'completed'
}

export type ApiResponseToday = ApiResponseNoDraft | ApiResponseDraft | ApiResponseActive | ApiResponseCompleted

export interface NegotiateRequest {
  text: string
}

export interface NegotiateResponse {
  message: string
  draft: Draft
  decisions: unknown[]
}

export interface ApproveResponse {
  status: 'approved'
  note_path: string
  tasks: DayTasks
}

export interface TaskActionRequest {
  action: 'complete' | 'drop' | 'defer'
  reason?: string
  defer_to?: string
  notes?: string
}

export interface TaskResponse {
  tasks: DayTasks
}

export interface AddTaskRequest {
  text: string
  priority: TaskPriority
}

export interface StatusResponse {
  calendar_fresh: boolean
  news_fresh: boolean
  day_status: DayStatus
  last_fetch: string
  errors: string[]
}
