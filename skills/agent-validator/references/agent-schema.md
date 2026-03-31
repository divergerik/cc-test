# Agent .md Frontmatter Schema Reference

## Required Fields

| Field | Type | Constraints |
|-------|------|-------------|
| `name` | string | kebab-case, 3-64 chars, starts with letter |
| `description` | string | Explains when Claude should delegate to this agent. Should include `<example>` blocks. |

## Optional Fields

| Field | Type | Valid Values |
|-------|------|-------------|
| `tools` | string/array | Comma-separated or array of tool names. Restricts available tools. |
| `disallowedTools` | string/array | Tools to explicitly deny from inherited set |
| `model` | string | `sonnet`, `opus`, `haiku`, `inherit` |
| `permissionMode` | string | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | integer | Max agentic turns before stopping |
| `skills` | array | Skills to inject into agent context |
| `mcpServers` | object | MCP servers scoped to this agent |
| `hooks` | object | Lifecycle hooks for this agent |
| `memory` | string | `user`, `project`, or `local` |
| `background` | boolean | Run as background task |
| `isolation` | string | `worktree` for git worktree isolation |
| `initialPrompt` | string | Auto-submitted first turn |
| `effort` | string | `low`, `medium`, `high`, `max` |

## Tool Restriction Patterns

```yaml
# Allow specific tools only
tools: Read, Glob, Grep

# Allow Agent tool for specific subagents only
tools: Agent(worker, researcher), Read, Bash

# Deny specific tools
disallowedTools: Write, Edit
```

## System Prompt Best Practices

1. Start with role definition: "You are a [specific expertise]..."
2. Define clear boundaries and constraints
3. Specify output format expectations
4. Include error handling guidance
5. Keep under 500 lines
