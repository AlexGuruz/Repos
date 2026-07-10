---
project_name: cog-allocation-system
type: core-project
status: active
created: 2026-02-06
updated: 2026-05-28
---

# cog-allocation-system

## Overview
Sales CSV to daily Cost of Goods (COG) per brand to Google Sheets (NUGZ COG, PUFFIN COG, EMPIRE COG, DROP DOWN HELPER).

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/cog-allocation-system/config|config]]
- [[20_projects/cog-allocation-system/data|data]]
- [[20_projects/cog-allocation-system/docs|docs]]
- [[20_projects/cog-allocation-system/lib|lib]]
- [[20_projects/cog-allocation-system/scripts|scripts]]
- [[20_projects/cog-allocation-system/tools|tools]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Repo Structure







<!-- REPO_STRUCTURE_START -->
|-- config
|   |-- config.example.yaml
|   +-- config.yaml
|-- data
|   |-- csv_dump
|   |   |-- .gitkeep
|   |   |-- Nugz Dispensary - 01-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 01-27-2026 - OrderItems.csv
|   |   |-- Nugz Dispensary - 01-28-2026 - OrderItems (1).csv
|   |   |-- Nugz Dispensary - 01-29-2026 - OrderItems (2).csv
|   |   |-- Nugz Dispensary - 01-30-2026 - OrderItems (3).csv
|   |   |-- Nugz Dispensary - 01-31-2026 - OrderItems (4).csv
|   |   |-- Nugz Dispensary - 02-09-2026 - OrderItems.csv
|   |   |-- Nugz Dispensary - 02-12-2026 - OrderItems.csv
|   |   |-- Nugz Dispensary - 02-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 03-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 04-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 05-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 06-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 07-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 08-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 09-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 10-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 11-2025 - OrderItems.csv
|   |   |-- Nugz Dispensary - 12-2025 - OrderItems.csv
|   |   +-- Nugz Dispensary 1-01-2026 - 02-08-2026 - OrderItems.csv
|   |-- logs
|   |   +-- .gitkeep
|   +-- state
|       |-- .gitkeep
|       +-- drive_watcher_state.json
|-- docs
|   |-- PIPELINE_AND_SHEETS.md
|   |-- RECREATION_SPEC.md
|   +-- SALES_CSV_EXPECTED.md
|-- lib
|   |-- __init__.py
|   |-- config_loader.py
|   +-- sheets_helper.py
|-- scripts
|   |-- calculate_daily_cog.py
|   |-- drive_watcher.py
|   |-- extract_unique_brands.py
|   +-- populate_categories.py
|-- tools
|-- .gitignore
|-- README.md
|-- requirements.txt
+-- run_drive_watcher.ps1
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[20_projects/index|Projects Index]]
