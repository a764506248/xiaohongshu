export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
export const SERVER_BASE = API_BASE.replace(/\/api\/v1\/?$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const TOKEN_KEY = "content_admin_token";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function uploadApi<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "上传失败" }));
    throw new ApiError(response.status, body.detail ?? "上传失败");
  }
  return response.json() as Promise<T>;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init?.headers,
    },
  });
  if (response.status === 401 && !path.startsWith("/auth/")) {
    localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new Event("auth:expired"));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new ApiError(response.status, body.detail ?? "请求失败");
  }
  return response.json() as Promise<T>;
}

export interface StreamEvent {
  event: string;
  node?: string;
  message: string;
  namespace?: string[];
}

export async function streamApi(
  path: string,
  body: unknown,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const value = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new ApiError(response.status, value.detail ?? "请求失败");
  }
  if (!response.body) throw new Error("浏览器不支持流式响应");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const consumeFrames = () => {
    // SSE 允许 CRLF；统一换行后再按空行切帧，避免某些代理环境下无法解析。
    buffer = buffer.replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("\n");
      if (!data) continue;
      const event = JSON.parse(data) as StreamEvent;
      onEvent(event);
      if (event.event === "error") throw new Error(event.message);
    }
  };
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    consumeFrames();
    if (done) break;
  }
}
