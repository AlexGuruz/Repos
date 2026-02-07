---
project_name: cog-allocation-system
type: core-project
status: active
created: 2026-02-06
updated: 2026-02-06
---

# cog-allocation-system

## Overview
Sales CSV to daily Cost of Goods (COG) per brand to Google Sheets (NUGZ COG, PUFFIN COG, EMPIRE COG, DROP DOWN HELPER).

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/cog-allocation-system/lib]]
- [[20_projects/cog-allocation-system/config]]
- [[20_projects/cog-allocation-system/data/csv_dump]]
- [[20_projects/cog-allocation-system/data/logs]]
- [[20_projects/cog-allocation-system/data/state]]
- [[20_projects/cog-allocation-system/data]]
- [[20_projects/cog-allocation-system/scripts]]
- [[20_projects/cog-allocation-system/docs]]
## Repo Structure



<!-- REPO_STRUCTURE_START -->
|-- config
|   |-- config.example.yaml
|   +-- config.yaml
|-- data
|   |-- csv_dump
|   |   +-- .gitkeep
|   |-- logs
|   |   +-- .gitkeep
|   +-- state
|       +-- .gitkeep
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
|-- .gitignore
|-- README.md
|-- requirements.txt
+-- run_drive_watcher.ps1
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[index|Projects Index]]
