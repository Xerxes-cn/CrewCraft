import { create } from 'zustand';
import type { Crew } from '../api/client';

interface CrewStore {
  crews: Crew[];
  setCrews: (crews: Crew[]) => void;
  selectedCrew: Crew | null;
  setSelectedCrew: (crew: Crew | null) => void;
}

export const useCrewStore = create<CrewStore>((set) => ({
  crews: [],
  setCrews: (crews) => set({ crews }),
  selectedCrew: null,
  setSelectedCrew: (crew) => set({ selectedCrew: crew }),
}));

interface TaskStore {
  messages: Array<{ agent_name: string; agent_role: string; content: string }>;
  addMessage: (msg: { agent_name: string; agent_role: string; content: string }) => void;
  setMessages: (msgs: Array<{ agent_name: string; agent_role: string; content: string }>) => void;
  running: boolean;
  setRunning: (running: boolean) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  running: false,
  setRunning: (running) => set({ running }),
}));
