# SKILL.md Frontmatter Schema Reference

## Required Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | string | kebab-case, 3-64 chars, starts with letter |

## Recommended Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `description` | string | 50+ chars, contains trigger phrases describing when to use |

## Optional Fields

| Field | Type | Valid Values |
|-------|------|-------------|
| `disable-model-invocation` | boolean | `true` / `false` — prevents Claude from auto-invoking |
| `user-invocable` | boolean | `true` / `false` — shows in `/` menu |
| `allowed-tools` | string | Comma-separated tool names (e.g., `Read, Grep, Bash`) |
| `context` | string | `fork` (run in isolated subagent) or omit |
| `agent` | string | Subagent type when `context: fork` (e.g., `Explore`) |
| `paths` | string | Glob patterns for path-specific activation |
| `effort` | string | `low`, `medium`, `high`, `max` |
| `model` | string | `sonnet`, `opus`, `haiku`, or model ID |

## Valid Tool Names

Read, Edit, Write, Glob, Grep, Bash, Agent, Skill, WebFetch, WebSearch, TodoWrite, AskUserQuestion, ToolSearch, NotebookEdit, EnterPlanMode, ExitPlanMode

## String Substitutions

| Variable | Description |
|----------|-------------|
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Path to skill directory |
| `$ARGUMENTS` | All arguments passed to the skill |
| `$0`, `$1`, `$2`... | Positional arguments |

## Body Guidelines

- Max 500 lines (guideline, not hard limit)
- Should contain clear, actionable instructions
- Use reference files for large content (references/ subdirectory)
- Include examples for complex workflows
