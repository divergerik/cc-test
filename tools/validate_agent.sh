#!/usr/bin/env bash
# Validate a Claude Code agent .md file structure.
#
# Usage: validate_agent.sh <path/to/agent.md>
# Output: JSON with validation results to stdout.
# Exit: 0 = all passed, 1 = failures found.

set -euo pipefail

FILE="${1:-}"

if [[ -z "$FILE" ]]; then
  echo '{"error": "Usage: validate_agent.sh <agent.md>"}'
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "{\"error\": \"File not found: $FILE\"}"
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo '{"error": "jq is required but not installed"}'
  exit 1
fi

# Delegate to validate_frontmatter.py for the core checks
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/validate_frontmatter.py" --type agent "$FILE"
