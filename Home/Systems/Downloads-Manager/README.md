# Downloads-Manager

Watches your Downloads folder and moves files to organized destinations (Images by type, PreRecycleBin for installers, Documents, Archives, Other). Uses Python + watchdog.

## Config

Edit `config/config.yaml`: `watch_folder` (default: your user Downloads), `destination_root` (default: `%USERPROFILE%\OrganizedDownloads`), `stable_seconds`.

## Run

- **Dry run** (scan once, log what would be moved; no moves):  
  `.\run_downloads_manager.ps1 -DryRun`
- **Run once** (scan and move existing files, then exit):  
  `.\run_downloads_manager.ps1 -RunOnce`
- **Watch continuously**:  
  `.\run_downloads_manager.ps1`

Requires Python and `pip install -r requirements.txt` (or use a venv).

## Run at startup

Task Scheduler: Trigger "At log on", Action:  
`powershell -ExecutionPolicy Bypass -File "E:\Repos\Home\Systems\Downloads-Manager\run_downloads_manager.ps1"`  
Or put a shortcut to the .ps1 in your Startup folder.
