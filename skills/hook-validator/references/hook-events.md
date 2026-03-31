# Claude Code Hook Events Reference

## All Valid Hook Events (24 total)

| Event | When It Fires | Input Fields |
|-------|---------------|-------------|
| `SessionStart` | Session begins/resumes | `source` ("startup", "resume", "clear", "compact") |
| `SessionEnd` | Session terminates | — |
| `InstructionsLoaded` | CLAUDE.md or rules loaded | — |
| `UserPromptSubmit` | User submits prompt | `prompt` |
| `PreToolUse` | Before tool executes | `tool_name`, `tool_input` |
| `PostToolUse` | After tool succeeds | `tool_name`, `tool_input`, `tool_response` |
| `PostToolUseFailure` | After tool fails | `tool_name`, `tool_input`, `error` |
| `PermissionRequest` | Permission dialog about to show | `tool_name`, `tool_input` |
| `Notification` | Notification sent | `message` |
| `SubagentStart` | Subagent spawned | agent type |
| `SubagentStop` | Subagent finishes | agent type |
| `TaskCreated` | Task created | task info |
| `TaskCompleted` | Task complete | task info |
| `Stop` | Claude finishes responding | `stop_hook_active` |
| `StopFailure` | Turn ends due to error | error type |
| `TeammateIdle` | Teammate about to idle | — |
| `ConfigChange` | Settings file changes | `source` |
| `CwdChanged` | Directory changes | new cwd |
| `FileChanged` | Watched file changes | `file_path` (basename) |
| `WorktreeCreate` | Worktree created | — |
| `WorktreeRemove` | Worktree removed | — |
| `PreCompact` | Before context compaction | — |
| `PostCompact` | After context compaction | — |
| `Elicitation` | MCP server requests input | — |
| `ElicitationResult` | User responds to elicitation | — |

## Common Input Fields (all events)

```json
{
  "session_id": "string",
  "cwd": "string",
  "hook_event_name": "string"
}
```

## Handler Types

| Type | Required Fields | Description |
|------|----------------|-------------|
| `command` | `command` | Shell script/command |
| `prompt` | `prompt` | Single-turn LLM evaluation |
| `agent` | `prompt` | Multi-turn agent with tool access |
| `http` | `url` | POST to HTTP endpoint |

## Exit Code Contract

| Code | Meaning | Behavior |
|------|---------|----------|
| `0` | Success/Allow | Process stdout JSON; action proceeds |
| `2` | Block/Deny | Stderr fed to Claude; action prevented |
| Other | Error | Logged; action proceeds (non-blocking) |

## Matcher Syntax

| Event Type | Matches Against | Example |
|------------|----------------|---------|
| Tool events | Tool name (regex) | `Bash`, `Edit\|Write`, `mcp__.*` |
| SessionStart | Source type | `startup`, `resume` |
| FileChanged | Filename basename | `.env`, `.envrc` |
| ConfigChange | Config source | `user_settings`, `project_settings` |
