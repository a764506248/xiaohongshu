import { api } from "./client";
export interface ModelConfiguration {
  id: string;
  owner_user_id: string | null;
  name: string;
  provider: string;
  model: string;
  capability: "image" | "image_to_video" | "text";
  protocol: string;
  base_url: string;
  has_api_key: boolean;
  is_system: boolean;
  enabled: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}
export interface ModelTestResult {
  status: string;
  model: string;
  output_url: string | null;
  output_text: string | null;
  latency_ms: number;
}
export const modelApi = {
  list: () => api<ModelConfiguration[]>("/models"),
  update: (id: string, data: { enabled: boolean; is_default: boolean }) =>
    api<ModelConfiguration>(`/models/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  create: (data: Record<string, unknown>) =>
    api<ModelConfiguration>("/models", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  edit: (id: string, data: Record<string, unknown>) =>
    api<ModelConfiguration>(`/models/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  remove: (id: string) => api<void>(`/models/${id}`, { method: "DELETE" }),
  test: (id: string, prompt: string) =>
    api<ModelTestResult>(`/models/${id}/test`, {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
};
