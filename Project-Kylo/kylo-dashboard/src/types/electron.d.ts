export interface ElectronAPI {
  onHubStatusUpdate: (callback: (data: any) => void) => void;
  onDashboardUpdate: (callback: (data: any) => void) => void;
  onHeartbeatUpdate: (callback: (payload: { path: string; data: any }) => void) => void;
  readFile: (filePath: string) => Promise<{ success: boolean; data?: any; error?: string }>;
  readLogTail: (instanceId: string, lines?: number) => Promise<{ success: boolean; lines?: string[]; totalLines?: number; error?: string }>;
  listInstances: () => Promise<{ success: boolean; instances?: any[]; error?: string }>;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

