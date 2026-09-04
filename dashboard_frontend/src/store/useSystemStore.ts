import { create } from 'zustand';
import { Position, SystemStatus, LogEntry } from '../lib/types';
import { mockPositions, mockSystemStatus, mockLogs } from '../lib/mockData';

interface SystemState {
  status: SystemStatus;
  positions: Position[];
  logs: LogEntry[];
  
  // Actions
  toggleBot: () => void;
  closePosition: (id: string) => void;
  addLog: (log: Omit<LogEntry, "id">) => void;
  
  // For initial load
  setPositions: (positions: Position[]) => void;
  setStatus: (status: SystemStatus) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  status: mockSystemStatus,
  positions: mockPositions,
  logs: mockLogs,
  
  toggleBot: () => set((state) => ({
    status: {
      ...state.status,
      botStatus: state.status.botStatus === 'running' ? 'paused' : 'running'
    }
  })),
  
  closePosition: (id: string) => set((state) => {
    const positionToClose = state.positions.find(p => p.id === id);
    if (positionToClose) {
      state.addLog({
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `Manually closed position ${id} on ${positionToClose.symbol}`
      });
    }
    return {
      positions: state.positions.filter(p => p.id !== id)
    };
  }),
  
  addLog: (log) => set((state) => ({
    logs: [{ ...log, id: `log-${Date.now()}` }, ...state.logs].slice(0, 100) // Keep last 100
  })),
  
  setPositions: (positions) => set({ positions }),
  setStatus: (status) => set({ status })
}));
