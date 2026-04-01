# cc-test

A meta-testing plugin for Claude Code. Validates and evaluates the primitives that compose other plugins: **skills**, **agents**, **hooks**, and **tools/MCP servers**.

---

## Why this plugin exists

The Claude Code ecosystem relies on four building blocks: skills (SKILL.md), agents (.md with frontmatter), hooks (hooks.json + scripts), and MCP tools. When you build a plugin that uses these primitives, there is no standard way to verify that they are well-formed, that their descriptions will trigger correctly, or that the agent behind them reasons well at runtime.

The industry divides agent quality assurance into three pillars:

| Pillar | What it catches | How cc-test addresses it |
|--------|----------------|--------------------------|
| **Static validation** | Malformed frontmatter, missing fields, invalid tool names, broken hook scripts | Deterministic Python/Bash validators that run instantly with zero API cost |
| **LLM-as-a-Judge** | Vague descriptions, unclear instructions, weak eval assertions | Claude reads the definition and scores quality dimensions semantically |
| **Trajectory testing** | Infinite loops, wrong tool selection, failure to recover from errors, inability to reach the goal | A runner executes the agent with mock tools, captures every Thought-Action-Observation step, and grades the reasoning |

Most existing solutions (LangSmith, Langfuse, TruEra) focus on one or two of these. cc-test covers all three from within Claude Code itself, so you never leave your development environment to test your plugin.

---

## Installation

Clone or copy this repository into your plugins directory, or point Claude Code at it:

```bash
# From your project directory
claude plugins install /path/to/cc-test
```

For trajectory testing (pillar 3), install the Python dependency:

```bash
pip install -r /path/to/cc-test/requirements.txt
```

This installs `claude-code-sdk`, which is only needed by `trajectory_runner.py`. All other tools use Python stdlib and Bash only.

---

## Quick start

Once installed, four slash commands become available:

```
/cc-test:test-skill <target>         Validate a SKILL.md file
/cc-test:test-agent <target>         Validate an agent definition
/cc-test:test-hook <target>          Validate hooks.json and its scripts
/cc-test:test-trajectory <target>    Run trajectory tests on an agent
```

Each `<target>` can be:
- A **file path**: `/cc-test:test-skill ./skills/my-skill/SKILL.md`
- A **directory**: `/cc-test:test-hook ./my-plugin/` (finds hooks.json inside)
- A **plugin name**: `/cc-test:test-skill bdd-ts-plugin:bdd-unit`

### Example: validate a skill

```
/cc-test:test-skill ./skills/deploy/SKILL.md
```

Produces a report like:

```
## Skill Validation: deploy

### Structural Checks
| Check              | Status  | Detail                                  |
|--------------------|---------|------------------------------------------|
| name_present       | passed  |                                          |
| name_format        | passed  |                                          |
| description_present| passed  |                                          |
| description_length | warning | 38 chars (recommended: 50+)              |
| body_present       | passed  |                                          |
| line_count         | passed  |                                          |
| evals_present      | info    | No evals/evals.json found                |

### Semantic Checks
| Dimension                | Score   | Notes                                   |
|--------------------------|---------|-----------------------------------------|
| Description trigger quality | warning | Too generic, add user phrases          |
| Instruction clarity      | passed  |                                          |
| Tool restrictions        | passed  |                                          |

### Summary
Passed: 6 | Warnings: 2 | Failed: 0 | Overall: WARN
```

### Example: run a trajectory test

```
/cc-test:test-trajectory ./fixtures/trajectory-evals/fix-auth-bug.json
```

This will:
1. Execute the agent with mocked tools (Read returns fake file content, Bash returns controlled output)
2. Capture every tool call into a JSONL trace
3. Analyze the trace for loops, step count, tool selection, error rate
4. Grade reasoning quality with LLM-as-a-Judge (5 dimensions, 1-5 each)

### Testing pyramid: three execution modes

Trajectory tests support three modes, forming a testing pyramid:

```
        /  --sandbox  \        Slow, real tools, deterministic verification
       /    (real)     \       Highest confidence, highest cost
      /________________\
     /   default (mock) \      SDK + mock tools, tests agent reasoning
    /____________________\     Medium cost, high reproducibility
   /   --mock-only        \    No SDK, no API, tests pipeline only
  /________________________\   Zero cost, fast, for CI smoke tests
```

**Mock mode** (default) — agent with mocked tool responses, fast and cheap:

```
/cc-test:test-trajectory ./fixtures/trajectory-evals/fix-auth-bug.json
```

**Sandbox mode** (`--sandbox`) — real tools in an isolated temp directory. After the agent runs, deterministic verification checks whether the goal was actually achieved (files changed, content correct, tests pass):

```
/cc-test:test-trajectory ./fixtures/trajectory-evals/fix-auth-bug.json --sandbox
```

**Mock-only mode** (`--mock-only`) — no SDK, no API calls, tests the pipeline:

```
/cc-test:test-trajectory ./fixtures/trajectory-evals/fix-auth-bug.json --mock-only
```

Add `--quick` to any mode to skip LLM grading (deterministic assertions only):

```
/cc-test:test-trajectory ./fixtures/trajectory-evals/fix-auth-bug.json --quick
```

---

## How it works

### Project structure

```
cc-test/
├── commands/                          User-invocable slash commands
│   ├── test-skill.md
│   ├── test-agent.md
│   ├── test-hook.md
│   └── test-trajectory.md
│
├── skills/                            Core validation and orchestration logic
│   ├── skill-validator/
│   │   ├── SKILL.md                   Structural + semantic skill validation
│   │   └── references/
│   │       ├── frontmatter-schema.md  Valid frontmatter fields reference
│   │       └── quality-rubric.md      Scoring criteria
│   ├── agent-validator/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── agent-schema.md
│   ├── hook-validator/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── hook-events.md         All 24 hook events documented
│   └── trajectory-tester/
│       ├── SKILL.md                   Run -> Analyze -> Grade -> Report
│       └── references/
│           ├── trace-schema.md        JSONL trace format
│           └── grading-rubric.md      5 grading dimensions (1-5)
│
├── agents/
│   └── trajectory-grader.md           LLM-as-a-Judge for reasoning quality
│
├── tools/                             Deterministic scripts (Python/Bash)
│   ├── discover_plugins.py            Enumerate plugins and their components
│   ├── validate_frontmatter.py        Parse and validate YAML frontmatter
│   ├── validate_hook_schema.sh        Validate hooks.json structure
│   ├── validate_agent.sh              Validate agent .md structure
│   ├── run_hook_test.sh               Pipe JSON fixtures into hook scripts
│   ├── trajectory_runner.py           Execute agent with mock MCP tools
│   └── trajectory_analyzer.py         Deterministic trace analysis
│
├── fixtures/
│   ├── hook-inputs/                   Sample hook event payloads (5 events)
│   └── trajectory-evals/              Sample trajectory test scenarios
│       ├── fix-auth-bug.json          Bug fix happy path
│       ├── explore-codebase.json      Read-only exploration
│       └── error-recovery.json        Recovery from tool failures
│
├── traces/                            Generated trace files (gitignored)
├── requirements.txt                   claude-code-sdk (for trajectory runner)
└── .claude-plugin/plugin.json         Plugin manifest
```

### Tools can run standalone

Every tool under `tools/` is a self-contained script. You do not need the full plugin or Claude Code to use them:

```bash
# Validate a skill's frontmatter
python3 tools/validate_frontmatter.py --type skill /path/to/SKILL.md

# Validate a hooks.json
bash tools/validate_hook_schema.sh /path/to/hooks.json

# Pipe a fixture into a hook script and check exit codes
bash tools/run_hook_test.sh /path/to/hook.sh fixtures/hook-inputs/pre-tool-use.json

# Analyze a trajectory trace
python3 tools/trajectory_analyzer.py --trace /path/to/trace.jsonl --assertions /path/to/eval.json

# Run trajectory test in mock-only mode (no API)
python3 tools/trajectory_runner.py --eval /path/to/eval.json --mock-only

# Run trajectory test in sandbox mode (real tools + verification)
python3 tools/trajectory_runner.py --eval /path/to/eval.json --sandbox

# Discover what components a plugin has
python3 tools/discover_plugins.py --path /path/to/plugin
```

---

## Warnings and limitations

### API costs

- **Static validation** (test-skill, test-agent, test-hook): the deterministic tools cost nothing. The LLM-assisted semantic checks run within your normal Claude Code session.
- **Trajectory testing with the SDK**: each `test-trajectory` run calls the Claude API to execute the agent. Budget defaults to **$0.10 per test**. A plugin with 5 evals could cost ~$0.50 per full run. Use `--mock-only` or `--quick` to limit costs during development.
- **LLM grading**: the trajectory-grader agent makes additional API calls. Skip with `--quick`.

### Sandbox mode vs. mock mode

The trajectory runner has two main execution modes:

**Mock mode** (default) uses `MockToolRouter` to return controlled responses. The agent never touches your real filesystem. However, mocks can be fragile — substring matching on `input_match` may miss if the agent phrases a command differently than expected.

**Sandbox mode** (`--sandbox`) creates a real temp directory, populates it with files from the eval, and lets the agent run with real tools. After execution, deterministic verification checks whether files were correctly modified. The sandbox is cleaned up automatically.

Neither mode is a container or security sandbox:
- In mock mode, tools without mock entries return errors, but the agent may attempt workarounds via the SDK.
- In sandbox mode, the agent has real tool access. The temp directory provides filesystem isolation, but network access and system commands are not restricted.
- For production-grade isolation, run trajectory tests inside a Docker container or CI environment.

### Non-determinism in trajectory tests

Agents are non-deterministic. The same eval may produce different trajectories on different runs. Design your assertions to tolerate variation:

- Use `max_steps: 10` not `exact_steps: 6`
- Use `must_use_tools: ["Read", "Edit"]` rather than asserting the exact sequence
- The `no_loops` assertion is reliable (a loop is always a bug)
- LLM grading scores may vary by 0.5-1.0 between runs

### Frontmatter parser limitations

The `validate_frontmatter.py` tool uses a simple regex-based YAML parser (no PyYAML dependency). It handles the flat key-value pairs that Claude Code frontmatter uses, but it does **not** support:

- Nested YAML objects
- Multi-line values with `|` or `>`
- YAML anchors and aliases

If your frontmatter uses these features, the parser may miss or misinterpret fields. The structural check will still catch missing `---` markers and required fields.

### Plugin discovery depends on installation state

The `discover_plugins.py` tool reads `~/.claude/plugins/installed_plugins.json` to find installed plugins. If a plugin is not formally installed (e.g., you are developing it locally), use `--path /path/to/plugin` instead of `--plugin name`.

---

## Extending cc-test

The plugin is designed to be extended. Each primitive (skill, agent, tool, fixture) follows a consistent pattern that you can replicate.

### Add a new validator skill

To validate a new kind of component (for example, MCP server configurations):

1. Create the skill directory:

```
skills/mcp-validator/
├── SKILL.md
└── references/
    └── mcp-schema.md
```

2. Write the SKILL.md with frontmatter:

```yaml
---
name: mcp-validator
description: Validate MCP server configuration files (.mcp.json) for correct transport types, required fields, and server connectivity. Use when auditing MCP configurations before publishing a plugin.
allowed-tools: Read, Bash, Glob, Grep
---
```

3. Structure the body in steps: resolve target, run deterministic checks, run semantic checks, report. Follow the pattern in `skills/skill-validator/SKILL.md`.

4. If you need a deterministic script, add it to `tools/` and make it emit JSON to stdout with the `{checks: [{check, status, detail}], passed, failed, warnings}` format.

5. Create a command wrapper in `commands/test-mcp.md` pointing to the new skill.

### Add a new trajectory eval

To test a specific agent behavior scenario:

1. Create a JSON file in `fixtures/trajectory-evals/`:

```json
{
  "test_name": "refactor-extract-method",
  "description": "Agent should extract a long function into smaller helpers",
  "prompt": "Refactor the process_order function in orders.py. It is too long. Extract the validation logic into a separate validate_order function.",
  "mock_tools": {
    "Read": {
      "orders.py": "def process_order(order):\n    # 50 lines of validation\n    if not order.items:\n        raise ValueError('Empty')\n    # ... more validation ...\n    # 30 lines of processing\n    total = sum(i.price for i in order.items)\n    return total\n"
    },
    "Edit": {
      "_default": "File edited successfully"
    },
    "Bash": [
      {"input_match": "pytest", "response": "3 passed in 0.4s", "exit_code": 0}
    ]
  },
  "assertions": {
    "max_steps": 12,
    "must_use_tools": ["Read", "Edit"],
    "must_not_use_tools": ["WebSearch"],
    "no_loops": true,
    "goal_achieved": "The agent should split process_order into two functions: validate_order and process_order, where process_order calls validate_order"
  },
  "verification": {
    "expected_files_changed": ["orders.py"],
    "expected_file_contains": {
      "orders.py": "def validate_order"
    }
  },
  "max_turns": 15,
  "max_budget_usd": 0.10
}
```

The `verification` block is used in sandbox mode (`--sandbox`) to deterministically check whether the agent achieved its goal. It supports four check types:

| Check | Format | What it verifies |
|-------|--------|-----------------|
| `command` + `expected_exit_code` | `"command": "pytest", "expected_exit_code": 0` | Run a shell command in the sandbox and check exit code |
| `expected_stdout_contains` | `["passed"]` | Substrings that must appear in the command's stdout |
| `expected_files_changed` | `["auth.py"]` | Files that must exist after the agent runs |
| `expected_file_contains` | `{"auth.py": "return user"}` | Strings that must appear in file contents after execution |

In mock mode (no `--sandbox`), the verification block is ignored and goal achievement falls back to LLM-as-a-Judge evaluation.

The mock tools support three patterns:

| Pattern | Format | Use case |
|---------|--------|----------|
| **Static mapping** | `{"file.py": "content"}` | Read, Glob: fixed responses per input key |
| **Ordered sequence** | `[{"input_match": "pytest", "response": "FAIL"}, ...]` | Bash: different results on successive calls |
| **Wildcard** | `{"_default": "response"}` | Fallback for any unmapped input |
| **Error simulation** | `{"path": {"_error": "Permission denied"}}` | Force a tool error to test recovery |

The `input_match` field uses **substring matching** by default (the match string just needs to appear somewhere in the tool input). For precise control, add `"match_mode": "regex"`.

### Add a new hook fixture

To test hooks for a new event type:

1. Create a JSON file in `fixtures/hook-inputs/` following the event's input schema:

```json
{
  "session_id": "test-session-001",
  "cwd": "/tmp/test-project",
  "hook_event_name": "FileChanged",
  "file_path": ".env"
}
```

2. Reference the complete event schemas in `skills/hook-validator/references/hook-events.md` for all 24 supported events and their fields.

3. Test your hook script with:

```bash
bash tools/run_hook_test.sh /path/to/your-hook.sh fixtures/hook-inputs/file-changed.json
```

The runner captures exit code (0 = allow, 2 = block), stdout, stderr, and execution time.

### Add a new grading dimension

To add a grading dimension to the trajectory grader (for example, "security awareness"):

1. Edit `agents/trajectory-grader.md` and add a new section under **Grading Dimensions**:

```markdown
### 6. Security Awareness
- **5**: Identified and avoided all security risks (secrets in code, unsafe commands)
- **4**: Caught most security issues
- **3**: Missed some obvious risks
- **2**: Ignored security implications
- **1**: Introduced or worsened security issues
```

2. Update the output format section to include the new dimension.

3. Document the scoring criteria in `skills/trajectory-tester/references/grading-rubric.md`.

4. Update the overall score calculation in `skills/trajectory-tester/SKILL.md` (average now divides by 6 instead of 5).

### Add a new deterministic metric to the analyzer

To track a new metric (for example, "time between tool calls"):

1. Edit `tools/trajectory_analyzer.py`. Add a function:

```python
def compute_tool_latency(entries: list[dict]) -> dict:
    """Compute time gaps between consecutive tool calls."""
    tool_uses = [e for e in entries if e["type"] == "tool_use" and "ts" in e]
    if len(tool_uses) < 2:
        return {"avg_gap_seconds": 0, "max_gap_seconds": 0}
    # parse timestamps and compute gaps
    ...
```

2. Call it from `compute_metrics()` and add the result to the metrics dict.

3. If you want an assertion for it, add a check in `run_assertions()`:

```python
if "max_tool_latency" in assertions:
    max_lat = assertions["max_tool_latency"]
    actual = metrics["tool_latency"]["max_gap_seconds"]
    if actual <= max_lat:
        checks.append({"check": "max_tool_latency", "status": "passed", ...})
    else:
        checks.append({"check": "max_tool_latency", "status": "failed", ...})
```

4. Use the new assertion in your eval JSON:

```json
"assertions": {
  "max_tool_latency": 5.0
}
```

### Wire everything into a full audit

When you have validators for all component types, create an orchestrator agent in `agents/plugin-auditor.md` that:

1. Calls `discover_plugins.py --path <plugin>` to find all components
2. Delegates to each validator skill in parallel
3. Runs trajectory evals if they exist
4. Collects all results into a unified report

Then create `commands/test-all.md` as the user-facing entry point:

```
/cc-test:test-all my-plugin
```

---

## License

MIT
