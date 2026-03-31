#!/usr/bin/env bash
# Pipe JSON fixture into a hook script and capture results.
#
# Usage:
#   run_hook_test.sh <hook-script> <fixture.json>
#   run_hook_test.sh --create-sample <event-type>
#
# Output: JSON with exit code, stdout, stderr, duration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$(dirname "$SCRIPT_DIR")/fixtures/hook-inputs"

# Create sample fixture mode
if [[ "${1:-}" == "--create-sample" ]]; then
  event="${2:-PreToolUse}"
  fixture_file="$FIXTURES_DIR/$(echo "$event" | tr '[:upper:]' '[:lower:]' | sed 's/\([a-z]\)\([A-Z]\)/\1-\2/g').json"

  case "$event" in
    PreToolUse)
      cat > "$fixture_file" <<'FIXTURE'
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "echo hello"
  }
}
FIXTURE
      ;;
    PostToolUse)
      cat > "$fixture_file" <<'FIXTURE'
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "echo hello"
  },
  "tool_response": "hello\n"
}
FIXTURE
      ;;
    SessionStart)
      cat > "$fixture_file" <<'FIXTURE'
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
FIXTURE
      ;;
    Stop)
      cat > "$fixture_file" <<'FIXTURE'
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "Stop",
  "stop_hook_active": false
}
FIXTURE
      ;;
    UserPromptSubmit)
      cat > "$fixture_file" <<'FIXTURE'
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Help me refactor the auth module"
}
FIXTURE
      ;;
    *)
      echo "{\"error\": \"Unknown event type: $event. Supported: PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit\"}"
      exit 1
      ;;
  esac

  echo "{\"created\": \"$fixture_file\"}"
  exit 0
fi

# Test execution mode
HOOK_SCRIPT="${1:-}"
FIXTURE="${2:-}"

if [[ -z "$HOOK_SCRIPT" ]] || [[ -z "$FIXTURE" ]]; then
  echo '{"error": "Usage: run_hook_test.sh <hook-script> <fixture.json>"}'
  exit 1
fi

if [[ ! -f "$HOOK_SCRIPT" ]]; then
  echo "{\"error\": \"Hook script not found: $HOOK_SCRIPT\"}"
  exit 1
fi

if [[ ! -x "$HOOK_SCRIPT" ]]; then
  echo "{\"error\": \"Hook script not executable: $HOOK_SCRIPT (run: chmod +x $HOOK_SCRIPT)\"}"
  exit 1
fi

if [[ ! -f "$FIXTURE" ]]; then
  echo "{\"error\": \"Fixture not found: $FIXTURE\"}"
  exit 1
fi

# Run the hook
STDOUT_FILE=$(mktemp)
STDERR_FILE=$(mktemp)
trap 'rm -f "$STDOUT_FILE" "$STDERR_FILE"' EXIT

START_TIME=$(python3 -c 'import time; print(time.time())')

set +e
cat "$FIXTURE" | "$HOOK_SCRIPT" > "$STDOUT_FILE" 2> "$STDERR_FILE"
EXIT_CODE=$?
set -e

END_TIME=$(python3 -c 'import time; print(time.time())')
DURATION=$(python3 -c "print(round($END_TIME - $START_TIME, 3))")

STDOUT_CONTENT=$(cat "$STDOUT_FILE")
STDERR_CONTENT=$(cat "$STDERR_FILE")

# Validate stdout is valid JSON (if non-empty)
stdout_valid_json="null"
if [[ -n "$STDOUT_CONTENT" ]]; then
  if echo "$STDOUT_CONTENT" | jq empty 2>/dev/null; then
    stdout_valid_json="true"
  else
    stdout_valid_json="false"
  fi
fi

# Determine pass/fail
# Exit 0 = allow, Exit 2 = block (both are valid hook responses)
# Any other exit code is unexpected
if [[ "$EXIT_CODE" -eq 0 ]] || [[ "$EXIT_CODE" -eq 2 ]]; then
  status="passed"
  status_detail="Exit code $EXIT_CODE is a valid hook response"
else
  status="failed"
  status_detail="Exit code $EXIT_CODE is unexpected (expected 0=allow or 2=block)"
fi

# Build result JSON
jq -n \
  --arg hook "$HOOK_SCRIPT" \
  --arg fixture "$FIXTURE" \
  --argjson exit_code "$EXIT_CODE" \
  --arg stdout "$STDOUT_CONTENT" \
  --arg stderr "$STDERR_CONTENT" \
  --argjson duration "$DURATION" \
  --argjson stdout_valid_json "$stdout_valid_json" \
  --arg status "$status" \
  --arg status_detail "$status_detail" \
  '{
    hook_script: $hook,
    fixture: $fixture,
    exit_code: $exit_code,
    stdout: $stdout,
    stderr: $stderr,
    duration_seconds: $duration,
    stdout_valid_json: $stdout_valid_json,
    status: $status,
    detail: $status_detail
  }'
