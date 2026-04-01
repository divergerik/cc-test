#!/usr/bin/env python3
"""Run an agent against a trajectory eval with mock tool responses.

Uses the Claude Code SDK to execute an agent, intercepting tool calls
with a mock MCP server that returns controlled responses from the eval JSON.
Captures the full trajectory as a JSONL trace file.

Usage:
    python3 trajectory_runner.py --eval <eval.json> [--output <trace.jsonl>] [--max-turns 25] [--max-budget 0.10] [--timeout 120]

Requires: pip install claude-code-sdk
Output: JSON summary to stdout + JSONL trace file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def check_sdk_available():
    """Check if claude-code-sdk is installed."""
    try:
        import claude_code_sdk  # noqa: F401
        return True
    except ImportError:
        return False


def load_eval(eval_path: str) -> dict:
    """Load and validate an eval JSON file."""
    data = json.loads(Path(eval_path).read_text())
    required = {"test_name", "prompt", "mock_tools"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Eval file missing required fields: {', '.join(missing)}")
    return data


class MockToolRouter:
    """Routes tool calls to mock responses based on eval configuration.

    Supports three response patterns:
    - Static mapping: {"file_path": "content"} — looks up input key in map
    - Ordered sequence: [{"input_match": "...", "response": "..."}] — consumed in order
    - Default/wildcard: {"_default": "response"} — fallback for unmapped inputs
    - Error simulation: {"_error": "message"} — returns error to agent
    """

    def __init__(self, mock_tools: dict):
        self.mock_tools = mock_tools
        self.sequence_cursors: dict[str, int] = {}

    def resolve(self, tool_name: str, tool_input: dict) -> tuple[str, bool]:
        """Resolve a tool call to a mock response.

        Returns (response_text, is_error).
        """
        if tool_name not in self.mock_tools:
            return f"[Mock] Tool '{tool_name}' not configured in eval. No mock response available.", True

        config = self.mock_tools[tool_name]

        # Pattern: Ordered sequence (list of match/response pairs)
        if isinstance(config, list):
            return self._resolve_sequence(tool_name, config, tool_input)

        # Pattern: Static mapping (dict of key→value)
        if isinstance(config, dict):
            return self._resolve_mapping(tool_name, config, tool_input)

        return str(config), False

    def _resolve_sequence(self, tool_name: str, seq: list, tool_input: dict) -> tuple[str, bool]:
        """Resolve against an ordered sequence of match/response pairs."""
        cursor_key = tool_name
        cursor = self.sequence_cursors.get(cursor_key, 0)

        # Build a searchable string from the input
        input_str = json.dumps(tool_input)

        # Find matching entry starting from cursor
        for i in range(cursor, len(seq)):
            entry = seq[i]
            match_str = entry.get("input_match", "")
            match_mode = entry.get("match_mode", "substring")

            matched = False
            if match_mode == "regex":
                matched = bool(re.search(match_str, input_str))
            else:
                # Substring match (default)
                matched = match_str in input_str

            if matched:
                self.sequence_cursors[cursor_key] = i + 1
                response = entry.get("response", "")
                is_error = entry.get("exit_code", 0) != 0
                return response, is_error

        # If no match found but sequence has entries, use last one (sticky)
        if seq:
            last = seq[-1]
            response = last.get("response", "")
            is_error = last.get("exit_code", 0) != 0
            return response, is_error

        return f"[Mock] No matching response for {tool_name}", True

    def _resolve_mapping(self, tool_name: str, mapping: dict, tool_input: dict) -> tuple[str, bool]:
        """Resolve against a static key→value mapping."""
        # Try to find a matching key from the tool input
        # For Read: look up file_path; for Bash: look up command; for Glob: look up pattern
        lookup_keys = self._extract_lookup_keys(tool_input)

        for key in lookup_keys:
            if key in mapping:
                value = mapping[key]
                # Handle error simulation
                if isinstance(value, dict) and "_error" in value:
                    return value["_error"], True
                return str(value) if not isinstance(value, str) else value, False

        # Try default
        if "_default" in mapping:
            value = mapping["_default"]
            if isinstance(value, dict) and "_error" in value:
                return value["_error"], True
            return str(value) if not isinstance(value, str) else value, False

        return f"[Mock] No mock response for {tool_name} with input keys: {lookup_keys}", True

    def _extract_lookup_keys(self, tool_input: dict) -> list[str]:
        """Extract likely lookup keys from tool input."""
        keys = []
        # Common tool input fields to use as lookup keys
        for field in ["file_path", "command", "pattern", "query", "path", "url"]:
            if field in tool_input:
                keys.append(str(tool_input[field]))
        # Also try the first string value
        for v in tool_input.values():
            if isinstance(v, str) and v not in keys:
                keys.append(v)
                break
        return keys


class TraceRecorder:
    """Records trajectory entries to a JSONL file."""

    def __init__(self, output_path: str):
        self.output_path = output_path
        self.entries: list[dict] = []
        self.seq = 0
        self._file = open(output_path, "w")

    def record(self, entry_type: str, **kwargs):
        """Record a trace entry."""
        entry = {
            "seq": self.seq,
            "type": entry_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self.entries.append(entry)
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()
        self.seq += 1

    def close(self):
        self._file.close()


async def run_trajectory(eval_data: dict, output_path: str, max_turns: int,
                         max_budget: float, timeout: int) -> dict:
    """Execute the agent and capture its trajectory."""
    import claude_code_sdk as sdk

    mock_router = MockToolRouter(eval_data["mock_tools"])
    recorder = TraceRecorder(output_path)
    start_time = time.time()

    prompt = eval_data["prompt"]

    try:
        # Build options
        options = sdk.ClaudeCodeOptions(
            max_turns=max_turns,
        )

        # Run the agent
        async for message in sdk.query(
            prompt=prompt,
            options=options,
        ):
            if hasattr(message, "content"):
                # AssistantMessage — extract text and tool calls
                for block in message.content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            recorder.record("assistant_text", content=block.text[:500])
                        elif block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input if hasattr(block, "input") else {}

                            recorder.record("tool_use",
                                            tool=tool_name,
                                            input=tool_input,
                                            tool_use_id=block.id)

                            # Resolve mock response
                            response, is_error = mock_router.resolve(tool_name, tool_input)
                            recorder.record("tool_result",
                                            tool=tool_name,
                                            tool_use_id=block.id,
                                            output=response[:500],
                                            is_error=is_error)

            elif hasattr(message, "result"):
                # ResultMessage
                recorder.record("result",
                                subtype=getattr(message, "subtype", "unknown"),
                                cost_usd=getattr(message, "cost_usd", None),
                                usage=getattr(message, "usage", {}))

    except asyncio.TimeoutError:
        recorder.record("result", subtype="timeout", cost_usd=None, usage={})
    except Exception as e:
        recorder.record("result", subtype="error", error=str(e), cost_usd=None, usage={})

    duration = time.time() - start_time
    recorder.close()

    return {
        "test_name": eval_data["test_name"],
        "eval_file": str(Path(output_path).resolve()),
        "trace_file": str(Path(output_path).resolve()),
        "status": "completed",
        "total_entries": recorder.seq,
        "tool_calls": sum(1 for e in recorder.entries if e["type"] == "tool_use"),
        "duration_seconds": round(duration, 2),
    }


async def run_trajectory_mock_only(eval_data: dict, output_path: str, max_turns: int) -> dict:
    """Run trajectory in mock-only mode (no SDK) for testing the runner itself.

    Simulates what the agent MIGHT do by generating a minimal trajectory
    from the mock tools config. Useful for testing the pipeline without API costs.
    """
    mock_router = MockToolRouter(eval_data["mock_tools"])
    recorder = TraceRecorder(output_path)
    start_time = time.time()

    recorder.record("assistant_text",
                    content=f"[Mock-only mode] Simulating agent for: {eval_data['prompt'][:200]}")

    # Simulate one call to each mock tool
    for tool_name, config in eval_data["mock_tools"].items():
        # Generate a plausible input
        if isinstance(config, dict):
            # Use first non-default key
            for key in config:
                if key != "_default":
                    sample_input = {"file_path": key} if tool_name == "Read" else \
                                   {"command": key} if tool_name == "Bash" else \
                                   {"pattern": key} if tool_name in ("Glob", "Grep") else \
                                   {tool_name.lower(): key}
                    break
            else:
                sample_input = {"_default": True}
        elif isinstance(config, list) and config:
            match_str = config[0].get("input_match", "test")
            sample_input = {"command": match_str} if tool_name == "Bash" else {"query": match_str}
        else:
            sample_input = {}

        tool_use_id = f"mock_{tool_name.lower()}_{recorder.seq}"
        recorder.record("tool_use", tool=tool_name, input=sample_input, tool_use_id=tool_use_id)

        response, is_error = mock_router.resolve(tool_name, sample_input)
        recorder.record("tool_result", tool=tool_name, tool_use_id=tool_use_id,
                        output=response[:500], is_error=is_error)

    recorder.record("result", subtype="success", cost_usd=0.0,
                    usage={"input_tokens": 0, "output_tokens": 0})

    duration = time.time() - start_time
    recorder.close()

    return {
        "test_name": eval_data["test_name"],
        "eval_file": "mock-only",
        "trace_file": str(Path(output_path).resolve()),
        "status": "completed (mock-only)",
        "total_entries": recorder.seq,
        "tool_calls": sum(1 for e in recorder.entries if e["type"] == "tool_use"),
        "duration_seconds": round(duration, 2),
    }


def run_verification(eval_data: dict, sandbox_dir: Path) -> dict:
    """Run deterministic verification after agent execution in sandbox."""
    verification = eval_data.get("verification")
    if not verification:
        return {"status": "skipped", "detail": "No verification block in eval"}

    checks = []

    # Check: command exit code + stdout
    if "command" in verification:
        try:
            result = subprocess.run(
                verification["command"], shell=True, cwd=str(sandbox_dir),
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired:
            checks.append({"check": "command_run", "status": "failed",
                           "detail": "Verification command timed out (30s)"})
            result = None

        if result is not None:
            expected_code = verification.get("expected_exit_code", 0)
            if result.returncode == expected_code:
                checks.append({"check": "exit_code", "status": "passed",
                               "detail": f"Exit code {result.returncode} == {expected_code}"})
            else:
                checks.append({"check": "exit_code", "status": "failed",
                               "detail": f"Exit code {result.returncode} != {expected_code}"})

            for needle in verification.get("expected_stdout_contains", []):
                if needle in result.stdout:
                    checks.append({"check": f"stdout_contains", "status": "passed",
                                   "detail": f"Found '{needle}' in stdout"})
                else:
                    checks.append({"check": f"stdout_contains", "status": "failed",
                                   "detail": f"'{needle}' not found in stdout"})

    # Check: files changed (exist after execution)
    for fname in verification.get("expected_files_changed", []):
        fpath = sandbox_dir / fname
        if fpath.exists():
            checks.append({"check": f"file_exists_{fname}", "status": "passed"})
        else:
            checks.append({"check": f"file_exists_{fname}", "status": "failed",
                           "detail": f"{fname} does not exist after execution"})

    # Check: file contains string
    for fname, needle in verification.get("expected_file_contains", {}).items():
        fpath = sandbox_dir / fname
        if fpath.exists() and needle in fpath.read_text():
            checks.append({"check": f"file_contains_{fname}", "status": "passed",
                           "detail": f"Found '{needle}' in {fname}"})
        else:
            detail = f"{fname} not found" if not fpath.exists() else f"'{needle}' not in {fname}"
            checks.append({"check": f"file_contains_{fname}", "status": "failed",
                           "detail": detail})

    passed = sum(1 for c in checks if c["status"] == "passed")
    failed = sum(1 for c in checks if c["status"] == "failed")
    return {"status": "passed" if failed == 0 else "failed",
            "checks": checks, "passed": passed, "failed": failed}


def _record_messages(message, recorder):
    """Shared logic: extract text and tool calls from SDK messages into the recorder."""
    if hasattr(message, "content"):
        for block in message.content:
            if hasattr(block, "type"):
                if block.type == "text":
                    recorder.record("assistant_text", content=block.text[:500])
                elif block.type == "tool_use":
                    recorder.record("tool_use",
                                    tool=block.name,
                                    input=block.input if hasattr(block, "input") else {},
                                    tool_use_id=block.id)
    elif hasattr(message, "result"):
        recorder.record("result",
                        subtype=getattr(message, "subtype", "unknown"),
                        cost_usd=getattr(message, "cost_usd", None),
                        usage=getattr(message, "usage", {}))


async def run_trajectory_sandbox(eval_data: dict, output_path: str, max_turns: int,
                                 max_budget: float, timeout: int) -> dict:
    """Run agent with real tools in an isolated temp directory."""
    import claude_code_sdk as sdk

    sandbox_dir = Path(tempfile.mkdtemp(prefix="cc_test_sandbox_"))
    recorder = TraceRecorder(output_path)
    start_time = time.time()

    try:
        # 1. Populate sandbox with files from sandbox_files or mock_tools.Read
        files = eval_data.get("sandbox_files") or eval_data.get("mock_tools", {}).get("Read", {})
        for filename, content in files.items():
            if filename.startswith("_") or isinstance(content, dict):
                continue
            filepath = sandbox_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(str(content))

        recorder.record("sandbox_setup",
                        sandbox_dir=str(sandbox_dir),
                        files_created=sorted(str(p.relative_to(sandbox_dir))
                                             for p in sandbox_dir.rglob("*") if p.is_file()))

        # 2. Run agent with real tools, cwd = sandbox
        options = sdk.ClaudeCodeOptions(
            max_turns=max_turns,
            cwd=str(sandbox_dir),
        )

        async for message in sdk.query(prompt=eval_data["prompt"], options=options):
            _record_messages(message, recorder)

    except asyncio.TimeoutError:
        recorder.record("result", subtype="timeout", cost_usd=None, usage={})
    except Exception as e:
        recorder.record("result", subtype="error", error=str(e), cost_usd=None, usage={})

    # 3. Run verification
    verification_result = run_verification(eval_data, sandbox_dir)
    recorder.record("verification", **verification_result)

    duration = time.time() - start_time
    recorder.close()

    # 4. Cleanup
    shutil.rmtree(sandbox_dir, ignore_errors=True)

    return {
        "test_name": eval_data["test_name"],
        "eval_file": str(Path(output_path).resolve()),
        "trace_file": str(Path(output_path).resolve()),
        "status": "completed",
        "mode": "sandbox",
        "total_entries": recorder.seq,
        "tool_calls": sum(1 for e in recorder.entries if e["type"] == "tool_use"),
        "duration_seconds": round(duration, 2),
        "verification": verification_result,
    }


def main():
    parser = argparse.ArgumentParser(description="Run agent trajectory test with mock tools")
    parser.add_argument("--eval", required=True, help="Path to trajectory eval JSON")
    parser.add_argument("--output", help="Path for JSONL trace output (default: traces/<name>_<ts>.jsonl)")
    parser.add_argument("--max-turns", type=int, default=25, help="Max agent turns (default: 25)")
    parser.add_argument("--max-budget", type=float, default=0.10, help="Max budget in USD (default: 0.10)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (default: 120)")
    parser.add_argument("--mock-only", action="store_true",
                        help="Run in mock-only mode without the Claude SDK (for pipeline testing)")
    parser.add_argument("--sandbox", action="store_true",
                        help="Run with real tools in an isolated temp directory (requires SDK)")
    args = parser.parse_args()

    eval_path = Path(args.eval).resolve()
    if not eval_path.exists():
        json.dump({"error": f"Eval file not found: {eval_path}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    try:
        eval_data = load_eval(str(eval_path))
    except (json.JSONDecodeError, ValueError) as e:
        json.dump({"error": f"Invalid eval file: {e}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    # Use eval-level overrides if present
    max_turns = eval_data.get("max_turns", args.max_turns)
    max_budget = eval_data.get("max_budget_usd", args.max_budget)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        traces_dir = Path(__file__).parent.parent / "traces"
        traces_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        output_path = str(traces_dir / f"{eval_data['test_name']}_{ts}.jsonl")

    if args.mock_only:
        result = asyncio.run(run_trajectory_mock_only(eval_data, output_path, max_turns))
    elif args.sandbox:
        if not check_sdk_available():
            json.dump({
                "error": "claude-code-sdk not installed. Run: pip install claude-code-sdk",
                "hint": "Use --mock-only flag to test the pipeline without the SDK"
            }, sys.stdout, indent=2)
            print()
            sys.exit(1)

        result = asyncio.run(
            asyncio.wait_for(
                run_trajectory_sandbox(eval_data, output_path, max_turns, max_budget, args.timeout),
                timeout=args.timeout,
            )
        )
    else:
        if not check_sdk_available():
            json.dump({
                "error": "claude-code-sdk not installed. Run: pip install claude-code-sdk",
                "hint": "Use --mock-only flag to test the pipeline without the SDK"
            }, sys.stdout, indent=2)
            print()
            sys.exit(1)

        result = asyncio.run(
            asyncio.wait_for(
                run_trajectory(eval_data, output_path, max_turns, max_budget, args.timeout),
                timeout=args.timeout,
            )
        )

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
