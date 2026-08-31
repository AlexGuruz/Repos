# Example env for scheduled company inbox cleaner (copy to C:\secrets\email_sorter_env.ps1).
# Do not commit real secrets. Absolute paths recommended on worker-node.

# Shared OAuth client (Desktop app JSON)
$env:GOOGLE_CREDENTIALS_FILE = "E:\Repos\ai-lab\secrets\gmail\credentials.json"

# Worker-node Ollama (local). On Acheron tunnel use http://127.0.0.1:11435
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "llama3.1:8b"

# Toast delivery: when cleaner runs on worker-node, SSH to Acheron for popup
$env:ACHERON_SSH = "zacle@acheron"
$env:ACHERON_TOAST_SCRIPT = "E:\Repos\ai-lab\scripts\show_email_toast.ps1"
# If running the cleaner on Acheron itself:
# $env:ACHERON_TOAST_LOCAL = "1"

# Optional Slack mirror
# $env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
