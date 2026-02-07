import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  onHubStatusUpdate: (callback: (data: any) => void) => {
    ipcRenderer.on("hub-status-updated", (_event, data) => callback(data));
  },
  onDashboardUpdate: (callback: (data: any) => void) => {
    ipcRenderer.on("dashboard-updated", (_event, data) => callback(data));
  },
  onHeartbeatUpdate: (callback: (payload: { path: string; data: any }) => void) => {
    ipcRenderer.on("heartbeat-updated", (_event, payload) => callback(payload));
  },
  readFile: (filePath: string) => ipcRenderer.invoke("read-file", filePath),
  readLogTail: (instanceId: string, lines?: number) => ipcRenderer.invoke("read-log-tail", instanceId, lines),
  listInstances: () => ipcRenderer.invoke("list-instances"),
});

