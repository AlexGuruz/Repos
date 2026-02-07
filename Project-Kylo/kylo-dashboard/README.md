# Kylo Hub Dashboard

Electron desktop app for monitoring and managing Kylo watcher instances.

## Features

- **Nested Company/Year Navigation**: Dropdowns to filter instances by company and year
- **Real-time Log Viewer**: Tail logs from each watcher instance with search and auto-scroll
- **Metrics Graphs**: Company-level graphs showing tick duration, error rates, and posting success
- **Status Display**: Real-time instance status cards with health indicators
- **Budget Foundation**: Placeholder for future budget/projection UI integration

## Setup

1. Install dependencies:
```bash
cd kylo-dashboard
npm install
```

2. Run in development mode:
```bash
npm run electron:dev
```

This will:
- Start Vite dev server on port 5173
- Launch Electron window
- Watch for file changes and hot-reload

## Building

Build for production:
```bash
npm run build
```

This creates a Windows `.exe` installer in the `dist/` directory.

## Project Structure

- `electron/` - Electron main process and preload scripts
- `src/` - React application
  - `components/` - UI components
  - `hooks/` - React hooks for file watching and log tailing
  - `services/` - Data aggregation utilities
  - `types/` - TypeScript type definitions

## How It Works

The dashboard reads JSON files from `.kylo/` directory:
- `.kylo/ops/dashboard.json` - Aggregated instance health
- `.kylo/hub/status.json` - Hub supervisor status
- `.kylo/instances/<ID>/health/heartbeat.json` - Per-instance heartbeat data
- `.kylo/instances/<ID>/logs/watcher.log` - Instance logs

File watchers (using `chokidar`) detect changes and update the UI in real-time via IPC.

## Future Enhancements

- Budget/projection UI integration with Google Sheets
- More detailed metrics and historical data
- Instance control (start/stop/restart) from UI
- Export logs and metrics

