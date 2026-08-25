export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
export const SERVER_BASE = API_BASE.replace(/\/api\/v1\/?$/, '')

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export async function uploadApi<T>(path: string, file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', body: form })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '上传失败' }))
    throw new ApiError(response.status, body.detail ?? '上传失败')
  }
  return response.json() as Promise<T>
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new ApiError(response.status, body.detail ?? '请求失败')
  }
  return response.json() as Promise<T>
}
