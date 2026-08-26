import { api } from "./client";
export interface PromptVersion {
  id: string;
  version_number: number;
  system_prompt: string;
  user_prompt_template: string;
  variables_json: string;
  change_note: string;
  created_by: string | null;
  created_at: string;
}
export interface PromptTemplate {
  id: string;
  owner_user_id: string | null;
  name: string;
  prompt_key: string;
  tags: string[];
  scene: string;
  model_capability: string;
  description: string;
  status: string;
  is_default: boolean;
  is_system: boolean;
  current_version: PromptVersion | null;
  created_at: string;
  updated_at: string;
}
export const promptApi = {
  list: () => api<PromptTemplate[]>("/prompts"),
  create: (data: Record<string, unknown>) =>
    api<PromptTemplate>("/prompts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Record<string, unknown>) =>
    api<PromptTemplate>(`/prompts/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  versions: (id: string) => api<PromptVersion[]>(`/prompts/${id}/versions`),
  rollback: (id: string, version_number: number) =>
    api<PromptTemplate>(`/prompts/${id}/rollback`, {
      method: "POST",
      body: JSON.stringify({ version_number }),
    }),
  remove: (id: string) => api<void>(`/prompts/${id}`, { method: "DELETE" }),
};
