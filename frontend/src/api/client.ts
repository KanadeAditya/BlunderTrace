// The one place screens get data from. Uses the in-browser mock until the backend exists
// (set VITE_API_MOCK=false to call the real API at /api).
import { mockApi } from './mock'

import type { ApiError, Game, Player, Report, StartReportRequest, StartReportResponse } from './types'

export class ApiRequestError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ApiError | null
    throw new ApiRequestError(res.status, body?.error ?? 'request_failed', body?.detail ?? res.statusText)
  }
  return (await res.json()) as T
}

const httpApi = {
  getPlayer: (username: string) => request<Player>(`/players/${encodeURIComponent(username)}`),
  startReport: (body: StartReportRequest) =>
    request<StartReportResponse>('/reports', { method: 'POST', body: JSON.stringify(body) }),
  getReport: (id: string) => request<Report>(`/reports/${encodeURIComponent(id)}`),
  getGame: (reportId: string, gameId: string) =>
    request<Game>(`/reports/${encodeURIComponent(reportId)}/games/${encodeURIComponent(gameId)}`),
}

/** Turns the mock's errors into the same ApiRequestError the real API throws. */
function wrapMock<T extends Record<string, (...args: never[]) => Promise<unknown>>>(api: T): T {
  const wrapped = {} as T
  for (const name of Object.keys(api) as (keyof T)[]) {
    wrapped[name] = (async (...args: never[]) => {
      try {
        return await api[name](...args)
      } catch (e) {
        const err = e as { status?: number; error?: string; message: string }
        throw new ApiRequestError(err.status ?? 500, err.error ?? 'request_failed', err.message)
      }
    }) as T[keyof T]
  }
  return wrapped
}

export const api = import.meta.env.VITE_API_MOCK === 'false' ? httpApi : wrapMock(mockApi)
