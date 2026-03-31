---
name: test-agent
description: Validate a Claude Code agent definition (.md file) for structural correctness, frontmatter fields, system prompt quality, and tool configuration. Invoke with a path to an agent .md file or a plugin:agent reference.
user-invocable: true
---

You have been asked to validate a Claude Code agent definition.

The plugin root is at `${CLAUDE_PLUGIN_ROOT}`. All tools are under `${CLAUDE_PLUGIN_ROOT}/tools/`.

## Resolve the target

Parse `$ARGUMENTS` to determine what to validate:
- If it looks like a file path (contains `/` or ends in `.md`): use that path directly
- If it looks like `plugin-name:agent-name`: use the discovery tool to find it:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/discover_plugins.py" --plugin "<plugin-name>"
  ```
  Then locate the agent by name in the inventory.
- If no arguments: look for agent .md files in `.claude/agents/` in the current working directory.

## Run validation

1. Run the deterministic validator:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/validate_frontmatter.py" --type agent "<resolved-path>"
   ```

2. Read the agent file and perform semantic quality checks:
   - Role definition clarity ("You are a [specific role]...")
   - Output format specification (structured output expectations)
   - Tool usage guidance (how/when to use each allowed tool)
   - Constraint definition (boundaries on what NOT to do)
   - Description examples (`<example>` blocks for delegation matching)
   - Isolation appropriateness (worktree needed if writing files?)

3. Output the full validation report with structural checks, semantic checks, and summary (PASS/WARN/FAIL).
