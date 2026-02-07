# Project Index (Dataview)

## All Project Subfolders
```dataview
TABLE repo_path, relative_path, project
FROM "20_projects"
WHERE type = "project-subfolder"
SORT project, relative_path
```

## By Project
```dataview
TABLE relative_path, repo_path
FROM "20_projects"
WHERE type = "project-subfolder" AND project = "Gigatt Transport LLC"
SORT relative_path
```

## Project Hubs
```dataview
TABLE file.mtime as "Updated"
FROM "20_projects"
WHERE type = "core-project"
SORT file.name
```
