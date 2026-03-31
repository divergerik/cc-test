---
name: test-skill
description: Validate a Claude Code skill (SKILL.md) for structural correctness, frontmatter quality, description triggers, and eval coverage. Invoke with a path to a SKILL.md file or a plugin:skill reference.
user-invocable: true
---

You have been asked to validate a Claude Code skill.

The plugin root is at `${CLAUDE_PLUGIN_ROOT}`. All tools are under `${CLAUDE_PLUGIN_ROOT}/tools/`.

## Resolve the target

Parse `$ARGUMENTS` to determine what to validate:
- If it looks like a file path (contains `/` or ends in `.md`): use that path directly
- If it looks like `plugin-name:skill-name`: use the discovery tool to find it:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/discover_plugins.py" --plugin "<plugin-name>"
  ```
  Then locate the skill by name in the inventory.
- If it looks like just a plugin name: list all skills in that plugin and ask which to validate.
- If no arguments: look for SKILL.md files in the current working directory.

## Run validation

1. Run the deterministic validator:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/validate_frontmatter.py" --type skill "<resolved-path>"
   ```

2. Read the SKILL.md file and perform semantic quality checks:
   - Description trigger quality (specific user phrases vs generic)
   - Instruction clarity (step-by-step, unambiguous)
   - Progressive disclosure (references/ for large content)
   - Tool restrictions match (allowed-tools vs actual usage)
   - Example coverage for complex skills
   - $ARGUMENTS handling if applicable

3. Check for `evals/evals.json` in the skill's directory.

4. Output the full validation report with structural checks, semantic checks, eval coverage, and summary (PASS/WARN/FAIL).
