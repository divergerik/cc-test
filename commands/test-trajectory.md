---
name: test-trajectory
description: >
  Run agent trajectory tests to evaluate how agents reason at runtime. Tests agent
  behavior with mock tool responses, checks for loops, correct tool selection, error
  recovery, and grades reasoning quality. Invoke with a path to a trajectory eval file,
  a directory of evals, or a plugin name.
user-invocable: true
---

You have been asked to run agent trajectory tests.

The plugin root is at `${CLAUDE_PLUGIN_ROOT}`. All tools are under `${CLAUDE_PLUGIN_ROOT}/tools/`.

## Resolve the target

Parse `$ARGUMENTS` to determine what to test:
- If it looks like a file path ending in `.json`: run that single eval
- If it looks like a directory path: find all `*.json` files in it and run each
- If it looks like a plugin name: use the discovery tool to find its trajectory evals:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/discover_plugins.py" --path "<plugin-path>"
  ```
  Look for `trajectory_evals` in the inventory.
- If `--sandbox` is in the arguments: run with real tools in isolated temp directory + deterministic verification
- If `--mock-only` is in the arguments: pass it to the runner (no SDK required)
- If `--quick` is in the arguments: skip LLM grading (deterministic only)
- If no arguments: look for `fixtures/trajectory-evals/*.json` in the current working directory

## Run the trajectory-tester skill

Follow the trajectory-tester skill steps:

1. **Run**: Execute `trajectory_runner.py --eval <file> [--mock-only|--sandbox]` for each eval
2. **Analyze**: Execute `trajectory_analyzer.py --trace <trace> --assertions <eval>` for each trace (includes verification results from sandbox mode)
3. **Grade** (unless `--quick`): Delegate to the `trajectory-grader` agent
4. **Report**: Output the structured report combining all results
