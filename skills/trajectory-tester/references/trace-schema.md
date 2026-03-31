# Trajectory Trace JSONL Schema

Each line in the trace file is a JSON object with these fields:

## Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `seq` | integer | Sequential entry number (0-based) |
| `type` | string | Entry type (see below) |
| `ts` | string | ISO 8601 timestamp |

## Entry Types

### `assistant_text`
Agent's reasoning/thinking text.
```json
{"seq": 0, "type": "assistant_text", "content": "I'll read the file...", "ts": "..."}
```

### `tool_use`
Agent initiates a tool call.
```json
{"seq": 1, "type": "tool_use", "tool": "Read", "input": {"file_path": "auth.py"}, "tool_use_id": "toolu_xxx", "ts": "..."}
```

### `tool_result`
Response from the tool (real or mocked).
```json
{"seq": 2, "type": "tool_result", "tool": "Read", "tool_use_id": "toolu_xxx", "output": "file content...", "is_error": false, "ts": "..."}
```

### `result`
Final outcome of the agent run.
```json
{"seq": 8, "type": "result", "subtype": "success", "cost_usd": 0.012, "usage": {"input_tokens": 1200, "output_tokens": 450}, "ts": "..."}
```

**Result subtypes**: `success`, `error_max_turns`, `timeout`, `error`

## Correlating Tool Calls

`tool_use_id` links a `tool_use` entry to its corresponding `tool_result`. This enables tracking individual tool call latency and outcomes.

## Trajectory Sequence Pattern

A typical trajectory follows this pattern:
```
assistant_text → tool_use → tool_result → assistant_text → tool_use → tool_result → ... → result
```

The agent alternates between thinking (text) and acting (tool calls), with each tool call producing a result that informs the next thought.
