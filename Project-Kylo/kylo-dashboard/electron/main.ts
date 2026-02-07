import { app, BrowserWindow, ipcMain } from "electron";
import * as path from "path";
import * as fs from "fs";
import chokidar from "chokidar";

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: "#1e1e1e", // Dark theme background
    titleBarStyle: "default",
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  // Find Kylo root (parent directory of kylo-dashboard)
  const kyloRoot = path.resolve(__dirname, "..", "..", ".kylo");
  if (!fs.existsSync(kyloRoot)) {
    console.warn(`Kylo root not found at ${kyloRoot}. File watching may not work.`);
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

// File watchers for Kylo JSON files
// Kylo root is parent of kylo-dashboard directory
const kyloRoot = path.resolve(__dirname, "..", "..", ".kylo");
let watchers: chokidar.FSWatcher[] = [];

function setupFileWatchers() {
  // Watch hub status
  const statusPath = path.join(kyloRoot, "hub", "status.json");
  const statusWatcher = chokidar.watch(statusPath, { persistent: true, ignoreInitial: false });
  statusWatcher.on("change", () => {
    try {
      const data = JSON.parse(fs.readFileSync(statusPath, "utf-8"));
      mainWindow?.webContents.send("hub-status-updated", data);
    } catch (e) {
      console.error("Error reading status.json:", e);
    }
  });
  watchers.push(statusWatcher);

  // Watch dashboard
  const dashboardPath = path.join(kyloRoot, "ops", "dashboard.json");
  const dashboardWatcher = chokidar.watch(dashboardPath, { persistent: true, ignoreInitial: false });
  dashboardWatcher.on("change", () => {
    try {
      const data = JSON.parse(fs.readFileSync(dashboardPath, "utf-8"));
      mainWindow?.webContents.send("dashboard-updated", data);
    } catch (e) {
      console.error("Error reading dashboard.json:", e);
    }
  });
  watchers.push(dashboardWatcher);

  // Watch all heartbeat files
  const heartbeatPattern = path.join(kyloRoot, "instances", "*", "health", "heartbeat.json");
  const heartbeatWatcher = chokidar.watch(heartbeatPattern, { persistent: true, ignoreInitial: false });
  heartbeatWatcher.on("change", (changedPath) => {
    try {
      const data = JSON.parse(fs.readFileSync(changedPath, "utf-8"));
      mainWindow?.webContents.send("heartbeat-updated", { path: changedPath, data });
    } catch (e) {
      console.error(`Error reading heartbeat ${changedPath}:`, e);
    }
  });
  watchers.push(heartbeatWatcher);
}

// IPC handlers
ipcMain.handle("read-file", async (_event, filePath: string) => {
  try {
    const fullPath = path.isAbsolute(filePath) ? filePath : path.join(kyloRoot, filePath);
    const content = fs.readFileSync(fullPath, "utf-8");
    return { success: true, data: JSON.parse(content) };
  } catch (e) {
    return { success: false, error: String(e) };
  }
});

ipcMain.handle("read-log-tail", async (_event, instanceId: string, lines: number = 1000) => {
  try {
    const logPath = path.join(kyloRoot, "instances", instanceId, "logs", "watcher.log");
    if (!fs.existsSync(logPath)) {
      return { success: false, error: "Log file not found" };
    }
    const content = fs.readFileSync(logPath, "utf-8");
    const allLines = content.split("\n");
    const tail = allLines.slice(-lines);
    return { success: true, lines: tail, totalLines: allLines.length };
  } catch (e) {
    return { success: false, error: String(e) };
  }
});

ipcMain.handle("list-instances", async () => {
  try {
    const dashboardPath = path.join(kyloRoot, "ops", "dashboard.json");
    if (!fs.existsSync(dashboardPath)) {
      return { success: true, instances: [] };
    }
    const data = JSON.parse(fs.readFileSync(dashboardPath, "utf-8"));
    return { success: true, instances: data.instances || [] };
  } catch (e) {
    return { success: false, error: String(e) };
  }
});

app.whenReady().then(() => {
  setupFileWatchers();
});

app.on("before-quit", () => {
  watchers.forEach((w) => w.close());
});

