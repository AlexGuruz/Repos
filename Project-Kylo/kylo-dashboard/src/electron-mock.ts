// Mock Electron API for browser development
export function setupElectronMock() {
  if (typeof window !== 'undefined' && !(window as any).electronAPI) {
    (window as any).electronAPI = {
      listInstances: async () => ({
        success: true,
        instances: []
      }),
      onDashboardUpdate: (callback: any) => {
        // Mock empty callback
      },
      readLog: async () => ({ success: true, content: 'Mock log content' }),
      clearLog: async () => ({ success: true }),
      onLogUpdate: (callback: any) => {
        // Mock empty callback
      }
    };
  }
}
