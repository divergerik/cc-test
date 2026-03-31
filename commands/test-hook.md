---
name: test-hook
description: Validate Claude Code hooks configuration (hooks.json) and hook scripts for structural correctness, valid events, handler types, and script executability. Optionally runs hook scripts against test fixtures. Invoke with a path to hooks.json or a plugin name.
user-invocable: true
---

You have been asked to validate Claude Code hooks.

The plugin root is at `${CLAUDE_PLUGIN_ROOT}`. All tools are under `${CLAUDE_PLUGIN_ROOT}/tools/`. Fixtures are under `${CLAUDE_PLUGIN_ROOT}/fixtures/hook-inputs/`.

## Resolve the target

Parse `$ARGUMENTS` to determine what to validate:
- If it looks like a file path to a hooks.json: use that path directly
- If it looks like a directory path: look for `hooks/hooks.json` inside it
- If it looks like a plugin name: use the discovery tool to find it:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/discover_plugins.py" --plugin "<plugin-name>"
  ```
  Then locate the hooks configuration in the inventory.
- If no arguments: look for `hooks/hooks.json` or `.claude/hooks/hooks.json` in the current working directory.

## Run validation

1. Run the hook schema validator:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/tools/validate_hook_schema.sh" "<resolved-hooks.json>"
   ```

2. For each command-type hook, find and validate the referenced script (exists, executable, no hardcoded paths).

3. Run each hook script against the appropriate fixture:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/tools/run_hook_test.sh" "<hook-script>" "${CLAUDE_PLUGIN_ROOT}/fixtures/hook-inputs/<event>.json"
   ```
   Map events to fixtures: PreToolUse→pre-tool-use.json, PostToolUse→post-tool-use.json, SessionStart→session-start.json, Stop→stop.json, UserPromptSubmit→user-prompt-submit.json.

4. Read each hook script and perform semantic review (safety, performance, error handling, infinite loop risk for Stop hooks).

5. Output the full validation report with schema checks, script checks, fixture test results, semantic review, and summary (PASS/WARN/FAIL).
