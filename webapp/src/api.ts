import type {
  ApiResponseToday,
  NegotiateRequest,
  NegotiateResponse,
  ApproveResponse,
  TaskActionRequest,
  TaskResponse,
  AddTaskRequest,
  StatusResponse,
} from './types'

const API_BASE = '/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const error = await res.text()
    throw new Error(`API error ${res.status}: ${error}`)
  }
  return res.json()
}

export const api = {
  async getToday(): Promise<ApiResponseToday> {
    const res = await fetch(`${API_BASE}/today`)
    return handleResponse(res)
  },

  async negotiate(text: string): Promise<NegotiateResponse> {
    const res = await fetch(`${API_BASE}/negotiate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text } as NegotiateRequest),
    })
    return handleResponse(res)
  },

  async approve(): Promise<ApproveResponse> {
    const res = await fetch(`${API_BASE}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    return handleResponse(res)
  },

  async updateTask(taskId: string, action: string, details?: Record<string, unknown>): Promise<TaskResponse> {
    const body: TaskActionRequest = {
      action: action as any,
      ...details,
    }
    const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return handleResponse(res)
  },

  async addTask(text: string, priority: string): Promise<TaskResponse> {
    const res = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, priority } as AddTaskRequest),
    })
    return handleResponse(res)
  },

  async getStatus(): Promise<StatusResponse> {
    const res = await fetch(`${API_BASE}/status`)
    return handleResponse(res)
  },
}
