#!/usr/bin/env python3
"""Deterministic analysis of agent trajectory traces.

Reads a JSONL trace file and computes metrics: step count, tool selection,
loop detection, error rate, divergence. Optionally validates against assertions.

Usage:
    python3 trajectory_analyzer.py --trace <trace.jsonl>
    python3 trajectory_analyzer.py --trace <trace.jsonl> --assertions <eval.json>

Output: JSON with metrics and assertion results to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_trace(trace_path: str) -> list[dict]:
    """Load JSONL trace file into a list of entries."""
    entries = []
    with open(trace_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"type": "parse_error", "line": line_num, "raw": line[:200]})
    return entries


def load_assertions(assertions_path: str) -> dict:
    """Load assertions from an eval JSON file or standalone assertions file."""
    data = json.loads(Path(assertions_path).read_text())
    # Support both standalone assertions and eval files with nested assertions
    if "assertions" in data:
        return data["assertions"]
    return data


def compute_metrics(entries: list[dict]) -> dict:
    """Compute all trajectory metrics from trace entries."""
    tool_uses = [e for e in entries if e.get("type") == "tool_use"]
    tool_results = [e for e in entries if e.get("type") == "tool_result"]
    result_entry = next((e for e in entries if e.get("type") == "result"), None)

    # Step count
    total_steps = len(tool_uses)

    # Tool selection
    tool_names = [e["tool"] for e in tool_uses]
    unique_tools = sorted(set(tool_names))
    tool_call_sequence = tool_names

    # Tool frequency
    tool_frequency = {}
    for name in tool_names:
        tool_frequency[name] = tool_frequency.get(name, 0) + 1

    # Error rate
    error_results = [e for e in tool_results if e.get("is_error", False)]
    error_count = len(error_results)
    error_rate = error_count / len(tool_results) if tool_results else 0.0

    # Loop detection (sliding window)
    loops = detect_loops(tool_uses, window_size=3)

    # Token/cost from result entry
    usage = {}
    cost_usd = None
    if result_entry:
        usage = result_entry.get("usage", {})
        cost_usd = result_entry.get("cost_usd")

    total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    return {
        "total_steps": total_steps,
        "tool_calls": total_steps,
        "unique_tools": unique_tools,
        "tool_call_sequence": tool_call_sequence,
        "tool_frequency": tool_frequency,
        "loops_detected": loops,
        "error_count": error_count,
        "error_rate": round(error_rate, 3),
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "result_subtype": result_entry.get("subtype") if result_entry else None,
    }


def normalize_input(tool_input: dict) -> str:
    """Normalize tool input for comparison (sort keys, strip whitespace)."""
    try:
        return json.dumps(tool_input, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(tool_input)


def detect_loops(tool_uses: list[dict], window_size: int = 3) -> list[dict]:
    """Detect repeated (tool, input) patterns using a sliding window."""
    if len(tool_uses) < window_size:
        return []

    loops = []
    for i in range(len(tool_uses) - window_size + 1):
        window = tool_uses[i:i + window_size]
        signatures = [
            (e.get("tool", ""), normalize_input(e.get("input", {})))
            for e in window
        ]
        # Check if all entries in window are identical
        if all(sig == signatures[0] for sig in signatures):
            loops.append({
                "tool": window[0].get("tool"),
                "input_preview": str(window[0].get("input", {}))[:100],
                "consecutive_count": window_size,
                "start_index": i,
            })

    # Deduplicate overlapping windows (keep the first occurrence)
    if loops:
        deduped = [loops[0]]
        for loop in loops[1:]:
            prev = deduped[-1]
            if loop["start_index"] > prev["start_index"] + prev["consecutive_count"] - 1:
                deduped.append(loop)
            else:
                # Extend the previous loop's count
                deduped[-1]["consecutive_count"] = (
                    loop["start_index"] + loop["consecutive_count"] - prev["start_index"]
                )
        loops = deduped

    return loops


def compute_divergence(tool_uses: list[dict], relevant_tools: list[str]) -> float:
    """Compute divergence ratio: off-scope tool calls / total calls."""
    if not tool_uses or not relevant_tools:
        return 0.0
    relevant_set = set(relevant_tools)
    off_scope = sum(1 for e in tool_uses if e.get("tool") not in relevant_set)
    return round(off_scope / len(tool_uses), 3)


def run_assertions(metrics: dict, assertions: dict, tool_uses: list[dict]) -> list[dict]:
    """Run assertion checks against computed metrics."""
    checks = []

    # max_steps
    if "max_steps" in assertions:
        max_steps = assertions["max_steps"]
        actual = metrics["total_steps"]
        if actual <= max_steps:
            checks.append({"check": "max_steps", "status": "passed",
                           "detail": f"{actual} <= {max_steps}"})
        else:
            checks.append({"check": "max_steps", "status": "failed",
                           "detail": f"{actual} > {max_steps} (exceeded by {actual - max_steps})"})

    # must_use_tools
    if "must_use_tools" in assertions:
        required = set(assertions["must_use_tools"])
        used = set(metrics["unique_tools"])
        missing = required - used
        if not missing:
            checks.append({"check": "must_use_tools", "status": "passed",
                           "detail": f"All required tools used: {', '.join(sorted(required))}"})
        else:
            checks.append({"check": "must_use_tools", "status": "failed",
                           "detail": f"Missing tools: {', '.join(sorted(missing))}"})

    # must_not_use_tools
    if "must_not_use_tools" in assertions:
        forbidden = set(assertions["must_not_use_tools"])
        used = set(metrics["unique_tools"])
        violated = forbidden & used
        if not violated:
            checks.append({"check": "must_not_use_tools", "status": "passed",
                           "detail": "No forbidden tools used"})
        else:
            checks.append({"check": "must_not_use_tools", "status": "failed",
                           "detail": f"Forbidden tools used: {', '.join(sorted(violated))}"})

    # no_loops
    if assertions.get("no_loops", False):
        if not metrics["loops_detected"]:
            checks.append({"check": "no_loops", "status": "passed",
                           "detail": "No loops detected"})
        else:
            loop_desc = "; ".join(
                f"{l['tool']}x{l['consecutive_count']} at step {l['start_index']}"
                for l in metrics["loops_detected"]
            )
            checks.append({"check": "no_loops", "status": "failed",
                           "detail": f"Loops detected: {loop_desc}"})

    # max_error_rate
    if "max_error_rate" in assertions:
        max_rate = assertions["max_error_rate"]
        actual = metrics["error_rate"]
        if actual <= max_rate:
            checks.append({"check": "max_error_rate", "status": "passed",
                           "detail": f"Error rate {actual} <= {max_rate}"})
        else:
            checks.append({"check": "max_error_rate", "status": "failed",
                           "detail": f"Error rate {actual} > {max_rate}"})

    # max_divergence
    if "max_divergence" in assertions and "relevant_tools" in assertions:
        max_div = assertions["max_divergence"]
        actual_div = compute_divergence(tool_uses, assertions["relevant_tools"])
        if actual_div <= max_div:
            checks.append({"check": "max_divergence", "status": "passed",
                           "detail": f"Divergence {actual_div} <= {max_div}"})
        else:
            checks.append({"check": "max_divergence", "status": "failed",
                           "detail": f"Divergence {actual_div} > {max_div}"})

    # result subtype check
    subtype = metrics.get("result_subtype")
    if subtype:
        if subtype == "success":
            checks.append({"check": "completion", "status": "passed",
                           "detail": "Agent completed successfully"})
        elif subtype == "error_max_turns":
            checks.append({"check": "completion", "status": "failed",
                           "detail": "Agent hit max turns limit"})
        else:
            checks.append({"check": "completion", "status": "warning",
                           "detail": f"Agent ended with subtype: {subtype}"})

    return checks


def main():
    parser = argparse.ArgumentParser(description="Analyze agent trajectory traces")
    parser.add_argument("--trace", required=True, help="Path to JSONL trace file")
    parser.add_argument("--assertions", help="Path to eval JSON or assertions JSON file")
    args = parser.parse_args()

    if not Path(args.trace).exists():
        json.dump({"error": f"Trace file not found: {args.trace}"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    entries = load_trace(args.trace)
    if not entries:
        json.dump({"error": "Trace file is empty"}, sys.stdout, indent=2)
        print()
        sys.exit(1)

    metrics = compute_metrics(entries)
    tool_uses = [e for e in entries if e.get("type") == "tool_use"]

    result = {
        "trace_file": args.trace,
        "metrics": metrics,
    }

    if args.assertions:
        assertions = load_assertions(args.assertions)
        checks = run_assertions(metrics, assertions, tool_uses)
        passed = sum(1 for c in checks if c["status"] == "passed")
        failed = sum(1 for c in checks if c["status"] == "failed")
        warnings = sum(1 for c in checks if c["status"] == "warning")
        result["assertions"] = checks
        result["passed"] = passed
        result["failed"] = failed
        result["warnings"] = warnings

    json.dump(result, sys.stdout, indent=2)
    print()
    sys.exit(1 if result.get("failed", 0) > 0 else 0)


if __name__ == "__main__":
    main()
