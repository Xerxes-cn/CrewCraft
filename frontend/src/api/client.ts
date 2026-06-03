const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface Crew {
  id: number;
  name: string;
  description: string | null;
  workflow_type: string;
  workflow_config: Record<string, unknown> | null;
  created_at: string;
  agents: Agent[];
}

export interface Agent {
  id: number;
  crew_id: number;
  name: string;
  role: string;
  system_prompt: string | null;
  tools: unknown[] | null;
  llm_config: Record<string, unknown> | null;
  order: number;
  depends_on: number[] | null;
}

export interface Task {
  id: number;
  crew_id: number;
  status: string;
  input: string;
  messages: unknown[] | null;
  result: string | null;
  created_at: string;
}

export const api = {
  // Crews
  listCrews: () => request<Crew[]>('/crews'),
  getCrew: (id: number) => request<Crew>(`/crews/${id}`),
  createCrew: (data: Partial<Crew>) => request<Crew>('/crews', { method: 'POST', body: JSON.stringify(data) }),
  updateCrew: (id: number, data: Partial<Crew>) => request<Crew>(`/crews/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteCrew: (id: number) => request<void>(`/crews/${id}`, { method: 'DELETE' }),

  // Agents
  createAgent: (crewId: number, data: Partial<Agent>) =>
    request<Agent>(`/crews/${crewId}/agents`, { method: 'POST', body: JSON.stringify(data) }),
  updateAgent: (id: number, data: Partial<Agent>) =>
    request<Agent>(`/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAgent: (id: number) => request<void>(`/agents/${id}`, { method: 'DELETE' }),

  // Prompt
  generatePrompt: (data: { role: string; crew_name: string; crew_description: string | null; workflow_type: string }) =>
    request<{ prompt: string }>('/generate-prompt', { method: 'POST', body: JSON.stringify(data) }),

  // Tasks
  runTask: (crewId: number, input: string) =>
    request<Task>(`/crews/${crewId}/run`, { method: 'POST', body: JSON.stringify({ input }) }),
  listTasks: (crewId: number) => request<Task[]>(`/crews/${crewId}/tasks`),
  getTask: (taskId: number) => request<Task>(`/tasks/${taskId}`),
};
