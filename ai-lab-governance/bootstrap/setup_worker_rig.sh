#!/usr/bin/env bash
# Setup worker rig (Linux): install governance and set env
# Usage: ./setup_worker_rig.sh [GovernanceRoot]
# Example: ./setup_worker_rig.sh /opt/ai/ai-lab-governance

set -e

GOV_ROOT="${1:-$AI_LAB_GOVERNANCE_ROOT}"
if [ -z "$GOV_ROOT" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  GOV_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

export AI_LAB_GOVERNANCE_ROOT="$GOV_ROOT"
export AI_LAB_MACHINE="worker"

CURSOR_RULES_SRC="$GOV_ROOT/cursor"
CURSOR_RULES_DEST="${HOME}/.cursor/rules"
PROMPTS_SRC="$GOV_ROOT/cursor/prompts"
PROMPTS_DEST="${HOME}/.cursor/governance-prompts"

mkdir -p "$CURSOR_RULES_DEST"
if [ -f "$CURSOR_RULES_SRC/cursor_rules.md" ]; then
  cp "$CURSOR_RULES_SRC/cursor_rules.md" "$CURSOR_RULES_DEST/governance.md"
  echo "Installed Cursor rule: governance.md"
fi

if [ -d "$PROMPTS_SRC" ]; then
  mkdir -p "$PROMPTS_DEST"
  cp -r "$PROMPTS_SRC"/* "$PROMPTS_DEST/"
  echo "Installed prompts to: $PROMPTS_DEST"
fi

# Verify
if [ -x "$GOV_ROOT/bootstrap/verify_governance.py" ]; then
  python3 "$GOV_ROOT/bootstrap/verify_governance.py" || exit $?
fi

echo "Worker rig setup done. Add to .bashrc or .profile:"
echo "  export AI_LAB_GOVERNANCE_ROOT=\"$GOV_ROOT\""
echo "  export AI_LAB_MACHINE=worker"
