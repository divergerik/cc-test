#!/usr/bin/env bash
# Validate a hooks.json file against the Claude Code hook schema.
#
# Usage: validate_hook_schema.sh <path/to/hooks.json>
# Output: JSON with validation results to stdout.
# Exit: 0 = all passed, 1 = failures found.

set -euo pipefail

VALID_EVENTS=(
  "SessionStart" "SessionEnd"
  "InstructionsLoaded"
  "UserPromptSubmit"
  "PreToolUse" "PostToolUse" "PostToolUseFailure"
  "PermissionRequest"
  "Notification"
  "SubagentStart" "SubagentStop"
  "TaskCreated" "TaskCompleted"
  "Stop" "StopFailure"
  "TeammateIdle"
  "ConfigChange"
  "CwdChanged"
  "FileChanged"
  "WorktreeCreate" "WorktreeRemove"
  "PreCompact" "PostCompact"
  "Elicitation" "ElicitationResult"
)

VALID_TYPES=("command" "prompt" "agent" "http")

FILE="${1:-}"

if [[ -z "$FILE" ]]; then
  echo '{"error": "Usage: validate_hook_schema.sh <hooks.json>"}'
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "{\"error\": \"File not found: $FILE\"}"
  exit 1
fi

# Check if jq is available
if ! command -v jq &>/dev/null; then
  echo '{"error": "jq is required but not installed"}'
  exit 1
fi

checks="[]"
has_failure=false

add_check() {
  local check="$1" status="$2" detail="${3:-}"
  if [[ -n "$detail" ]]; then
    checks=$(echo "$checks" | jq --arg c "$check" --arg s "$status" --arg d "$detail" \
      '. + [{"check": $c, "status": $s, "detail": $d}]')
  else
    checks=$(echo "$checks" | jq --arg c "$check" --arg s "$status" \
      '. + [{"check": $c, "status": $s}]')
  fi
  if [[ "$status" == "failed" ]]; then
    has_failure=true
  fi
}

# Check valid JSON
if ! jq empty "$FILE" 2>/dev/null; then
  add_check "valid_json" "failed" "File is not valid JSON"
  passed=$(echo "$checks" | jq '[.[] | select(.status=="passed")] | length')
  failed=$(echo "$checks" | jq '[.[] | select(.status=="failed")] | length')
  warnings=$(echo "$checks" | jq '[.[] | select(.status=="warning")] | length')
  jq -n --arg f "$FILE" --argjson c "$checks" --argjson p "$passed" --argjson fl "$failed" --argjson w "$warnings" \
    '{file: $f, checks: $c, passed: $p, failed: $fl, warnings: $w}'
  exit 1
fi
add_check "valid_json" "passed"

# Check root structure — should have "hooks" key or be the hooks object directly
has_hooks_key=$(jq 'has("hooks")' "$FILE")
if [[ "$has_hooks_key" == "true" ]]; then
  hooks_path=".hooks"
else
  hooks_path="."
fi

# Validate event names
events=$(jq -r "$hooks_path | keys[]" "$FILE" 2>/dev/null || echo "")
valid_events_str=$(printf '%s\n' "${VALID_EVENTS[@]}")

for event in $events; do
  if echo "$valid_events_str" | grep -qx "$event"; then
    add_check "event_name_${event}" "passed"
  else
    add_check "event_name_${event}" "failed" "Unknown hook event: $event"
  fi
done

if [[ -z "$events" ]]; then
  add_check "has_events" "warning" "No hook events defined"
fi

# Validate each hook entry structure
for event in $events; do
  matchers=$(jq -r "$hooks_path[\"$event\"] | length" "$FILE" 2>/dev/null || echo "0")
  for (( i=0; i<matchers; i++ )); do
    matcher_path="$hooks_path[\"$event\"][$i]"

    # Check hooks array exists
    has_hooks=$(jq "$matcher_path | has(\"hooks\")" "$FILE" 2>/dev/null || echo "false")
    if [[ "$has_hooks" != "true" ]]; then
      add_check "matcher_hooks_${event}_${i}" "failed" "$event[$i]: missing 'hooks' array"
      continue
    fi

    hook_count=$(jq "$matcher_path.hooks | length" "$FILE" 2>/dev/null || echo "0")
    for (( j=0; j<hook_count; j++ )); do
      hook_path="$matcher_path.hooks[$j]"
      hook_type=$(jq -r "$hook_path.type // \"missing\"" "$FILE")

      if [[ "$hook_type" == "missing" ]]; then
        add_check "hook_type_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: missing 'type' field"
        continue
      fi

      type_valid=false
      for vt in "${VALID_TYPES[@]}"; do
        if [[ "$hook_type" == "$vt" ]]; then
          type_valid=true
          break
        fi
      done

      if [[ "$type_valid" == "false" ]]; then
        add_check "hook_type_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: invalid type '$hook_type'"
        continue
      fi
      add_check "hook_type_${event}_${i}_${j}" "passed"

      # Type-specific validation
      case "$hook_type" in
        command)
          cmd=$(jq -r "$hook_path.command // \"missing\"" "$FILE")
          if [[ "$cmd" == "missing" ]]; then
            add_check "hook_command_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: command hook missing 'command' field"
          else
            add_check "hook_command_${event}_${i}_${j}" "passed"
            # Check for hardcoded absolute paths (should use ${CLAUDE_PLUGIN_ROOT})
            if echo "$cmd" | grep -qE '^/' && ! echo "$cmd" | grep -q 'CLAUDE_'; then
              add_check "hook_no_hardcoded_path_${event}_${i}_${j}" "warning" \
                "$event[$i].hooks[$j]: hardcoded absolute path detected, use \${CLAUDE_PLUGIN_ROOT} instead"
            fi
          fi
          ;;
        prompt)
          prompt=$(jq -r "$hook_path.prompt // \"missing\"" "$FILE")
          if [[ "$prompt" == "missing" ]]; then
            add_check "hook_prompt_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: prompt hook missing 'prompt' field"
          else
            add_check "hook_prompt_${event}_${i}_${j}" "passed"
          fi
          ;;
        http)
          url=$(jq -r "$hook_path.url // \"missing\"" "$FILE")
          if [[ "$url" == "missing" ]]; then
            add_check "hook_url_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: http hook missing 'url' field"
          else
            add_check "hook_url_${event}_${i}_${j}" "passed"
          fi
          ;;
        agent)
          prompt=$(jq -r "$hook_path.prompt // \"missing\"" "$FILE")
          if [[ "$prompt" == "missing" ]]; then
            add_check "hook_agent_prompt_${event}_${i}_${j}" "failed" "$event[$i].hooks[$j]: agent hook missing 'prompt' field"
          else
            add_check "hook_agent_prompt_${event}_${i}_${j}" "passed"
          fi
          ;;
      esac

      # Timeout validation
      timeout=$(jq "$hook_path.timeout // null" "$FILE")
      if [[ "$timeout" != "null" ]]; then
        if ! [[ "$timeout" =~ ^[0-9]+$ ]] || [[ "$timeout" -lt 1 ]] || [[ "$timeout" -gt 600 ]]; then
          add_check "hook_timeout_${event}_${i}_${j}" "warning" \
            "$event[$i].hooks[$j]: timeout $timeout outside recommended range (1-600)"
        fi
      fi
    done
  done
done

# Output results
passed=$(echo "$checks" | jq '[.[] | select(.status=="passed")] | length')
failed=$(echo "$checks" | jq '[.[] | select(.status=="failed")] | length')
warnings=$(echo "$checks" | jq '[.[] | select(.status=="warning")] | length')

jq -n --arg f "$FILE" --argjson c "$checks" --argjson p "$passed" --argjson fl "$failed" --argjson w "$warnings" \
  '{file: $f, checks: $c, passed: $p, failed: $fl, warnings: $w}'

if [[ "$has_failure" == "true" ]]; then
  exit 1
fi
exit 0
